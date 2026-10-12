"""【缺陷基线·现状】naive 管线：LLM 裸输出 JSON 文本直接当配置结果。

现状问题（docs/01 问题报告）：
  - 不做任何校验——幻觉 ID / 类型漂移 / 命名漂移 / 必填省略全部直通下游；
  - 没有重试与降级——"输出大概是对的"就是唯一状态；
  - 编辑让模型重出整棵树——人工修改被无声覆盖；patch 拿到就应用，无白名单无锁。
校验器代码其实在平台里已存在（validators.py），但管线根本没接——这正是问题报告的第一条发现。
"""
import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from .mock_llm import MockLLM

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "data" / "golden"


@dataclass
class GenerationResult:
    status: str
    config: dict | None
    attempts: int
    violation_history: list
    degraded_reasons: list = field(default_factory=list)


class PatchResult:
    def __init__(self, ok, config, applied, rejections):
        self.ok = ok
        self.config = config
        self.applied = applied
        self.rejections = rejections


def generate_config(requirement: str, scenario: str = "ok", max_retries: int = 3) -> GenerationResult:
    """现状：一次生成，裸输出直接返回。"""
    raw = MockLLM(scenario).generate(requirement)
    return GenerationResult(status="ok", config=raw, attempts=1,
                            violation_history=[[]], degraded_reasons=[])


def apply_patch(config: dict, patch: list, manual_locked=(), allowed_prefixes=None) -> PatchResult:
    """现状：拿到 patch 直接应用。忽略锁与白名单参数（假装它们不存在）。"""
    work = deepcopy(config)
    for op in patch:
        name, path = op.get("op"), op.get("path", "")
        if name == "replace" and path == "/":
            work = deepcopy(op["value"])           # 整棵树重写——事故源头
            continue
        segs = [s for s in path.split("/") if s]
        try:
            parent = work
            for s in segs[:-1]:
                parent = parent[int(s)] if isinstance(parent, list) else parent[s]
            last = segs[-1]
            if name == "remove":
                (parent.pop(int(last)) if isinstance(parent, list) else parent.pop(last))
            elif name in ("replace", "add"):
                if isinstance(parent, list):
                    parent[int(last)] = op["value"]
                else:
                    parent[last] = op["value"]
            elif name == "move":
                value = work
                for s in [x for x in op["from"].split("/") if x][:-1]:
                    value = value[int(s)] if isinstance(value, list) else value[s]
                src = op["from"].rstrip("/").split("/")[-1]
                parent[last] = value.pop(int(src) if isinstance(value, list) else src)
        except (KeyError, IndexError, ValueError, TypeError):
            pass  # 现状：路径解不开就跳过，静默吞掉
    return PatchResult(True, work, [op.get("path") for op in patch], [])


def run_golden_regression() -> dict:
    """现状：拿裸输出和期望硬比，不做指标分解。"""
    per = []
    for f in sorted(GOLDEN_DIR.glob("*.json")):
        pair = json.loads(f.read_text(encoding="utf-8"))
        raw = MockLLM(pair["scenario"]).generate(pair["requirement"])
        per.append({"name": pair["name"], "passed": raw == pair["expected"]})
    n = len(per) or 1
    return {
        "passed": all(p["passed"] for p in per),
        "total": len(per),
        "failed": [p["name"] for p in per if not p["passed"]],
        "metrics": {"first_pass_rate": 1.0,  # 现状根本没有重试概念
                    "converged_rate": sum(p["passed"] for p in per) / n,
                    "hallucination_rate": 0.0},  # 现状没有幻觉检测
        "per_pair": per,
    }
