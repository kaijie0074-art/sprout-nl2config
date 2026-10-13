"""研究用 golden 详细采集器：逐对记录每轮违规历史、耗时、最终配置。

用法（真实 LLM，凭证走环境变量）：
  NL2CONFIG_API_KEY=... python3 evidence/collect_golden_detail.py out.json [--model glm-5.3-flash] [--max-retries 3] [--pairs 01,05]

不改变管线行为，仅旁路观测。"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nl2config.api import generate_config  # noqa: E402
from nl2config.golden import load_pairs  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--model", default=os.environ.get("NL2CONFIG_MODEL", "glm-4-flash"))
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--pairs", default="", help="逗号分隔的 pair 名前缀过滤")
    args = ap.parse_args()

    os.environ["NL2CONFIG_MODEL"] = args.model
    pairs = load_pairs()
    if args.pairs:
        keys = [k.strip() for k in args.pairs.split(",")]
        pairs = [p for p in pairs if any(p["name"].startswith(k) for k in keys)]

    records = []
    for pair in pairs:
        t0 = time.time()
        result = generate_config(pair["requirement"], max_retries=args.max_retries)
        dt = time.time() - t0
        records.append({
            "name": pair["name"],
            "status": result.status,
            "attempts": result.attempts,
            "wall_seconds": round(dt, 1),
            "violation_history": result.violation_history,
            "config": result.config,
            "degraded_reasons": result.degraded_reasons,
        })
        print(f"[{pair['name']}] {result.status} attempts={result.attempts} {dt:.0f}s", flush=True)

    summary = {
        "model": args.model,
        "max_retries": args.max_retries,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "converged_rate": sum(r["status"] == "ok" for r in records) / (len(records) or 1),
        "first_pass_rate": sum(r["attempts"] == 1 for r in records) / (len(records) or 1),
        "failed": [r["name"] for r in records if r["status"] != "ok"],
        "records": records,
    }
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "records"},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
