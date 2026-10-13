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

# 每类违规的"怎么改"指令（directive 反馈风格用；json 风格=v2 基线不含）
FIX_HINTS = {
    "INVALID_JSON": "只输出一个合法 JSON 对象，不要任何解释文字或代码围栏",
    "WRONG_TYPE": "按 message 中的期望类型重写该字段的值（布尔是 true/false，不带引号）",
    "MISSING_REQUIRED": "在该位置补上缺失字段，值需满足结构定义",
    "NAMING_DRIFT": "把该键名改为 message 中给出的 camelCase 键名",
    "ENUM_INVALID": "把值改为「可选值」中列出的合法枚举之一",
    "UNKNOWN_TEMPLATE": "把 templateId 改为「可选值」中的合法模板 ID",
    "INVALID_COMPONENT_ID": "把 componentId 改为「可选值」中真实存在的组件 ID",
    "UNSUPPORTED_PLATFORM": "二选一：从 /platforms 删除该组件不支持的平台，或删除该组件",
    "AD_SLOT_EXCEEDED": "删除广告组件，使总数不超过套餐上限",
    "AD_PER_PAGE_EXCEEDED": "删除该页超限的 ad_banner 组件",
    "MODULE_NOT_IN_PACKAGE": "删除该组件，或把 package 改为「可选值」中包含它的套餐",
    "TRACK_PARAM_FORMAT": "把键名改为 ch_<channel>_<id> 格式（channel∈weixin/douyin/baidu）",
}


def _resolve_pointer(config, path: str):
    """按 JSON Pointer 取当前值（解析失败返回 None，不抛异常）。"""
    if not isinstance(config, dict) or not path:
        return None
    node = config
    for token in path.strip("/").split("/"):
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        else:
            return None
    return node


def build_feedback(violations: list, config=None, style: str = "json") -> list:
    """违规 → 回喂反馈。

    style="json"：v2 基线（结构化 dict 列表，行为与历史版本一致）。
    style="directive"：附加 current_value（当前值）与 fix_hint（修正指令）。
    """
    if style != "directive":
        return [x.to_feedback() for x in violations]
    out = []
    for x in violations:
        fb = x.to_feedback()
        fb["fix_hint"] = FIX_HINTS.get(x.code, "按 message 与可选值修正")
        if config is not None:
            fb["current_value"] = _resolve_pointer(config, x.path)
        out.append(fb)
    return out
