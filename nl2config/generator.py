"""生成管线：Mock LLM → 结构校验 → 业务校验 → 结构化反馈重试 → 显式降级。

核心设计（源文档 1.5 第二层）：
  - 重试上限 3 次，超限返回 DegradeToHuman 语义的结果对象（status="degraded"），
    降级是**产品功能**而不是异常——调用方拿到完整失败原因清单去转人工。
  - 结构违规优先拦截（命名漂移时跳过深层校验，避免噪音反馈误导重试）。
"""
from dataclasses import dataclass, field

from .mock_llm import MockLLM
from .schema import validate_structure
from .validators import run_all


@dataclass
class GenerationResult:
    status: str                       # "ok" | "degraded"（不存在第三个状态）
    config: dict | None               # degraded 时为 None
    attempts: int                     # 实际尝试次数（1 + 重试）
    violation_history: list           # 每轮违规列表（结构化 dict）
    degraded_reasons: list = field(default_factory=list)  # 降级时的全部失败原因


def generate_config(requirement: str, scenario: str = "ok", max_retries: int = 3) -> GenerationResult:
    """需求 → 合法配置；有限重试内不收敛则显式降级转人工。"""
    llm = MockLLM(scenario)
    feedback = None
    history = []
    total = 1 + max_retries

    for attempt in range(1, total + 1):
        raw = llm.generate(requirement, feedback)
        violations = validate_structure(raw)
        if not violations:            # 结构合法才做深层校验
            violations = run_all(raw)
        history.append([x.to_dict() for x in violations])

        if not violations:            # 100% 合法才返回——不存在"大概是对的"
            return GenerationResult(status="ok", config=raw, attempts=attempt,
                                    violation_history=history)
        feedback = [x.to_feedback() for x in violations]  # 结构化回喂

    reasons = [d for round_vs in history for d in round_vs]
    return GenerationResult(status="degraded", config=None, attempts=total,
                            violation_history=history, degraded_reasons=reasons)
