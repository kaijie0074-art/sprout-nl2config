"""Q8 微基准：结构格式保真度采样（不经校验-修复循环，只看第 1 轮裸输出）。

对同一复合需求采样 N 次，统计每代模型的第 1 轮：
  - 可解析 JSON 率
  - 结构合法率（validate_structure 全绿）
  - 深层合法率（+ run_all 全绿）
  - visible 布尔率 / trackParams 格式率（逐字段格式保真）

用法：NL2CONFIG_API_KEY=... python3 evidence/fmt_fidelity_bench.py out.json --model glm-4-flash --n 10
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nl2config.llm import OpenAICompatLLM  # noqa: E402
from nl2config.schema import validate_structure  # noqa: E402
from nl2config.validators import run_all  # noqa: E402
from nl2config.registry import TRACK_PARAM_PATTERN  # noqa: E402

REQUIREMENT = (
    "做一个三页视频社区站：首页带视频播放、搜索、导航和横幅广告；社区页带论坛和短视频流；"
    "个人页带商城和优惠券。需要微信与抖音双渠道投放追踪。"
)


def first_pass_stats(config):
    comps = [c for p in (config.get("pages") or []) if isinstance(p, dict)
             for c in (p.get("components") or []) if isinstance(c, dict)]
    visible_bool = sum(isinstance(c.get("visible"), bool) for c in comps)
    tp = config.get("trackParams") or {}
    tp_ok = sum(bool(re.match(TRACK_PARAM_PATTERN, k)) for k in tp)
    return {
        "components": len(comps),
        "visible_bool": visible_bool,
        "track_keys": len(tp),
        "track_keys_wellformed": tp_ok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()
    os.environ.setdefault("NL2CONFIG_MODEL", args.model)

    llm = OpenAICompatLLM()
    samples = []
    for i in range(args.n):
        t0 = time.time()
        try:
            cfg = llm.generate(REQUIREMENT)
            parse_ok = True
        except ValueError:
            cfg, parse_ok = None, False
        dt = time.time() - t0
        struct = [] if not parse_ok else validate_structure(cfg)
        deep = [] if struct else run_all(cfg)
        rec = {
            "i": i + 1, "parse_ok": parse_ok, "latency_s": round(dt, 1),
            "structure_ok": parse_ok and not struct,
            "deep_ok": parse_ok and not struct and not deep,
            "violation_codes": [v.code for v in struct + deep],
            "stats": first_pass_stats(cfg) if parse_ok else None,
        }
        samples.append(rec)
        print(f"[{args.model} #{i+1}] parse={rec['parse_ok']} struct={rec['structure_ok']} "
              f"deep={rec['deep_ok']} {dt:.0f}s {rec['violation_codes']}", flush=True)

    n = len(samples) or 1
    summary = {
        "model": args.model, "n": args.n, "requirement": REQUIREMENT,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "parse_ok_rate": sum(s["parse_ok"] for s in samples) / n,
        "structure_ok_rate": sum(s["structure_ok"] for s in samples) / n,
        "deep_ok_rate": sum(s["deep_ok"] for s in samples) / n,
        "visible_bool_rate": (
            sum(s["stats"]["visible_bool"] for s in samples if s["stats"]) /
            max(1, sum(s["stats"]["components"] for s in samples if s["stats"]))
        ),
        "track_wellformed_rate": (
            sum(s["stats"]["track_keys_wellformed"] for s in samples if s["stats"]) /
            max(1, sum(s["stats"]["track_keys"] for s in samples if s["stats"]))
        ),
        "mean_latency_s": round(sum(s["latency_s"] for s in samples) / n, 1),
        "samples": samples,
    }
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "samples"},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
