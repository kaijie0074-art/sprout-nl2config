"""Q5 锚定实验：对抗性括号提示是否是 repair 类不收敛的主因？

两组 arm（每组 n 次单发采样，不进修复循环）：
  trap  = 原始 golden 需求（含"（模型会先…）"元指令）
  clean = 剥离括号后的干净需求
量化第 1 轮裸输出的违规率——若 clean 显著更干净，则失败主因是
"对抗性指令锚定 + 每轮重注入"，而非模型不具备输出合法格式的能力。

用法：NL2CONFIG_API_KEY=... python3 evidence/anchor_probe.py out.json --pairs 05,08 --n 4
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nl2config.golden import load_pairs  # noqa: E402
from nl2config.llm import OpenAICompatLLM  # noqa: E402
from nl2config.schema import validate_structure  # noqa: E402
from nl2config.validators import run_all  # noqa: E402


def strip_trap(requirement: str) -> str:
    return re.sub(r"[（(][^）)]*[）)]", "", requirement).strip()


def sample(llm, requirement):
    t0 = time.time()
    try:
        cfg = llm.generate(requirement)
        sv = validate_structure(cfg)
        codes = [v.code for v in sv] or [v.code for v in run_all(cfg)]
        visible = [c.get("visible") for p in cfg.get("pages", [])
                   for c in p.get("components", [])]
        visible_types = [type(v).__name__ for v in visible]
        return {"ok": not codes, "codes": codes, "visible_types": visible_types,
                "latency_s": round(time.time() - t0, 1), "config": cfg}
    except ValueError as e:
        return {"ok": False, "codes": ["INVALID_JSON"], "visible_types": [],
                "latency_s": round(time.time() - t0, 1), "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--pairs", default="05,08")
    ap.add_argument("--n", type=int, default=4)
    args = ap.parse_args()

    llm = OpenAICompatLLM()
    report = {"model": os.environ.get("NL2CONFIG_MODEL", "glm-4-flash"),
              "n_per_arm": args.n, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "pairs": []}
    for pair in load_pairs():
        if not any(pair["name"].startswith(k) for k in args.pairs.split(",")):
            continue
        arms = {}
        for arm, req in (("trap", pair["requirement"]),
                         ("clean", strip_trap(pair["requirement"]))):
            samples = [sample(llm, req) for _ in range(args.n)]
            arms[arm] = {
                "requirement": req,
                "first_pass_ok_rate": sum(s["ok"] for s in samples) / args.n,
                "visible_bool_rate": (
                    sum(t == "bool" for s in samples for t in s["visible_types"]) /
                    max(1, sum(len(s["visible_types"]) for s in samples))
                ),
                "codes_flat": [c for s in samples for c in s["codes"]],
                "samples": [{k: v for k, v in s.items() if k != "config"} for s in samples],
            }
            print(f"[{pair['name']}/{arm}] ok_rate={arms[arm]['first_pass_ok_rate']} "
                  f"visible_bool={arms[arm]['visible_bool_rate']:.2f} {arms[arm]['codes_flat']}",
                  flush=True)
        report["pairs"].append({"name": pair["name"], **arms})

    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
