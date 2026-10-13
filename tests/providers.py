"""测试替身 provider（仅 tests/ 内使用；产品代码零脚本化模型）。

ScriptedProvider：按场景语料首轮回放坏输出、收到结构化反馈后回放修正输出，
驱动校验-修复循环的确定性回归（收敛与降级路径）。
"""
from copy import deepcopy

from scenarios import CORRECTABLE, SCENARIOS


class ScriptedProvider:
    """接口与 nl2config.llm.OpenAICompatLLM 相同：generate(requirement, feedback) -> dict。"""

    def __init__(self, scenario: str = "ok"):
        if scenario not in SCENARIOS:
            raise ValueError(f"未知场景 {scenario}，可选：{sorted(SCENARIOS)}")
        self.scenario = scenario
        self.attempts = 0

    def generate(self, requirement: str, feedback: list | None = None) -> dict:
        self.attempts += 1
        bad, fixed = SCENARIOS[self.scenario]
        if feedback and self.scenario in CORRECTABLE:
            return deepcopy(fixed)
        return deepcopy(bad)
