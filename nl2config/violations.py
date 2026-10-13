"""违规项统一表示：结构化错误信息是校验-修复循环的燃料。

设计要点（借 Guardrails AI 的思路）：错误不是抛异常，而是携带
机器可读字段（错误码 / 路径 / 可选值）的结构化对象，可直接回喂模型。
"""
from dataclasses import dataclass, field


@dataclass
class Violation:
    code: str                 # 错误码，如 INVALID_COMPONENT_ID
    path: str                 # JSON Pointer 路径，如 /pages/0/components/2
    message: str              # 人读信息（中文）
    options: list = None       # 合法可选值（供回喂修正）
    layer: str = "structure"  # structure / reference / semantic / business

    def to_dict(self) -> dict:
        d = {"code": self.code, "path": self.path, "message": self.message, "layer": self.layer}
        if self.options is not None:
            d["options"] = self.options
        return d

    def to_feedback(self) -> dict:
        """回喂给 LLM 的结构化反馈（模型据此修正后重试）。"""
        fb = {"code": self.code, "path": self.path, "message": self.message}
        if self.options is not None:
            fb["options"] = self.options
        return fb


@dataclass
class PatchRejection:
    op_index: int
    code: str
    path: str
    message: str
