"""Q5/Q6：同题重复采样稳定性实验（输出非确定性量化）。

- mode=repeat：同一 repair 类 pair，max_attempts=1 裸采样 N 次，
  统计第 1 轮违规码的分布（同一 prompt 同一模型，不同采样）
- mode=temp0：temperature=0 直连采样 N 次，输出全文 hash 对比是否逐字节稳定

用法：NL2CONFIG_API_KEY=... python3 evidence/stability_probe.py out.json --mode repeat --pair 05 --n 6
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nl2config.golden import load_pairs  # noqa: E402
from nl2config.llm import SYSTEM_PROMPT, OpenAICompatLLM  # noqa: E402
from nl2config.schema import validate_structure  # noqa: E402
from nl2config.validators import run_all  # noqa: E402


def run_repeat(pair, n):
    llm = OpenAICompatLLM()
    runs = []
    for i in range(n):
        t0 = time.time()
        try:
            cfg = llm.generate(pair["requirement"])
            sv = validate_structure(cfg)
            codes = [v.code for v in sv] or [v.code for v in run_all(cfg)]
            ok = not codes
        except ValueError:
            cfg, codes, ok = None, ["INVALID_JSON"], False
        runs.append({"i": i + 1, "first_pass_ok": ok, "violation_codes": codes,
                     "latency_s": round(time.time() - t0, 1),
                     "config": cfg})
        print(f"[repeat #{i+1}] ok={ok} {runs[-1]['violation_codes']}", flush=True)
    return runs


def run_temp0(pair, n):
    """直连 temperature=0，比对最终 content 的 SHA256 是否稳定。"""
    llm = OpenAICompatLLM()
    base = llm._base_url.rstrip("/")
    hashes, contents = [], []
    for i in range(n):
        body = json.dumps({
            "model": llm._model, "temperature": 0.01,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"需求：{pair['requirement']}"},
            ],
        }, ensure_ascii=False).encode()
        req = urllib.request.Request(
            f"{base}/chat/completions", data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {llm._api_key}"})
        with urllib.request.urlopen(req, timeout=int(os.environ.get("NL2CONFIG_TIMEOUT", "300"))) as r:
            payload = json.loads(r.read().decode())
        text = payload["choices"][0]["message"]["content"].strip()
        h = hashlib.sha256(text.encode()).hexdigest()[:16]
        hashes.append(h)
        contents.append(text)
        print(f"[temp0 #{i+1}] sha={h} len={len(text)}", flush=True)
        time.sleep(2)
    return {"hashes": hashes, "unique_hashes": len(set(hashes)), "contents": contents}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--mode", choices=["repeat", "temp0"], required=True)
    ap.add_argument("--pair", default="05")
    ap.add_argument("--n", type=int, default=6)
    args = ap.parse_args()

    pair = next(p for p in load_pairs() if p["name"].startswith(args.pair))
    if args.mode == "repeat":
        runs = run_repeat(pair, args.n)
        ok_rate = sum(r["first_pass_ok"] for r in runs) / (len(runs) or 1)
        out = {"mode": "repeat", "pair": pair["name"], "n": args.n,
               "model": os.environ.get("NL2CONFIG_MODEL", "glm-4-flash"),
               "first_pass_ok_rate": ok_rate, "runs": runs}
    else:
        res = run_temp0(pair, args.n)
        out = {"mode": "temp0", "pair": pair["name"], "n": args.n,
               "model": os.environ.get("NL2CONFIG_MODEL", "glm-4-flash"), **res}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("runs", "contents")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
