"""golden 回归评测集（第五层）：需求 → 真实 LLM 生成 → 校验判据回归。

任何 prompt / schema / 校验器 / 资产注册表改动，跑一次回归即可量化影响：
  - 一次通过率（first_pass_rate）：第 1 轮就全绿的比例
  - 收敛率（converged_rate）：重试循环内最终合法的比例
  - 幻觉 ID 率（hallucination_rate）：历史中出现 INVALID_COMPONENT_ID 的占比

判据：结构 + 业务校验全绿（status == "ok"）。真实模型的合法解不唯一，
不做逐字段相等比对；pair 的 expected 字段保留为人工参考基线。
需要真实 LLM 凭证（NL2CONFIG_API_KEY / OPENAI_API_KEY）。
"""
import json
from pathlib import Path

from .generator import generate_config

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "data" / "golden"


def load_pairs() -> list:
    pairs = []
    for f in sorted(GOLDEN_DIR.glob("*.json")):
        pairs.append(json.loads(f.read_text(encoding="utf-8")))
    return pairs


def run_golden_regression(llm=None) -> dict:
    """跑全部 golden pairs（真实 LLM），返回逐对结果 + 汇总指标。"""
    pairs = load_pairs()
    per_pair = []
    for pair in pairs:
        result = generate_config(pair["requirement"], llm=llm)
        codes_flat = [d["code"] for round_vs in result.violation_history for d in round_vs]
        per_pair.append({
            "name": pair["name"],
            "passed": result.status == "ok",
            "attempts": result.attempts,
            "first_pass": result.attempts == 1,
            "had_hallucination": "INVALID_COMPONENT_ID" in codes_flat,
        })
    n = len(per_pair) or 1
    return {
        "schema_version_note": "golden 与 registry.SCHEMA_VERSION 绑定",
        "passed": all(p["passed"] for p in per_pair),
        "total": len(per_pair),
        "failed": [p["name"] for p in per_pair if not p["passed"]],
        "metrics": {
            "first_pass_rate": sum(p["first_pass"] for p in per_pair) / n,
            "converged_rate": sum(p["passed"] for p in per_pair) / n,
            "hallucination_rate": sum(p["had_hallucination"] for p in per_pair) / n,
        },
        "per_pair": per_pair,
    }
