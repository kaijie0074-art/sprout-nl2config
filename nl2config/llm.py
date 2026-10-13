"""真实 LLM 客户端（OpenAI 兼容协议）。

接口约定与校验-修复循环（generator.py）耦合：
  generate(requirement, feedback) -> dict
  - 输出必须是 JSON 对象（低代码配置 dict）；解析失败由 generator
    以结构违规回喂重试
  - feedback 是上一轮的结构化违规清单（错误码/路径/可选值），
    重试时注入 prompt

环境变量：
  NL2CONFIG_API_KEY    必填（API 凭证）
  NL2CONFIG_BASE_URL   可选（默认智谱开放平台；可指向 DeepSeek 等兼容服务）
  NL2CONFIG_MODEL      可选（默认 glm-4-flash）
"""
from __future__ import annotations

import json
import os
import urllib.request

from .registry import COMPONENTS, PACKAGES, SCHEMA_VERSION, TEMPLATES


class LlmConfigError(RuntimeError):
    """缺少真实 LLM 凭证。"""


def _asset_sheet() -> str:
    comps = "\n".join(f"  {cid}: 支持平台 {info['platforms']}" for cid, info in COMPONENTS.items())
    templates = ", ".join(TEMPLATES)
    packages = ", ".join(PACKAGES)
    return (
        f"组件注册表（SCHEMA_VERSION {SCHEMA_VERSION}）：\n{comps}\n"
        f"可用模板：{templates}\n可用套餐：{packages}"
    )


SYSTEM_PROMPT = (
    "你是低代码平台的配置生成器。根据用户需求输出一个 JSON 对象（低代码站点配置），"
    "只输出 JSON，不要输出任何解释文字。可用资产如下：\n" + _asset_sheet() + "\n"
    "配置结构：siteName(string), templateId(string), platforms(list, 值∈android/ios), "
    "package(string), trackParams(object, 渠道参数), pages(list of {pageId, title, "
    "components: list of {componentId, props: object}}), 以及可选 adSlots(list)。"
    "只能使用注册表中存在的 componentId/templateId/package；组件平台支持矩阵必须遵守。"
)


class OpenAICompatLLM:
    """真实 API 客户端。generate 返回 JSON dict；文本不可解析时抛 ValueError。"""

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self._api_key = api_key or os.environ.get("NL2CONFIG_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self._base_url = (
            base_url
            or os.environ.get("NL2CONFIG_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
        )
        self._model = model or os.environ.get("NL2CONFIG_MODEL", "glm-4-flash")
        if not self._api_key:
            raise LlmConfigError(
                "需要真实 LLM API 凭证：请设置 NL2CONFIG_API_KEY（或 OPENAI_API_KEY），"
                "可选 NL2CONFIG_BASE_URL / NL2CONFIG_MODEL 指向任意 OpenAI 兼容服务。"
            )

    def generate(self, requirement: str, feedback: list | None = None) -> dict:
        user = f"需求：{requirement}"
        if feedback:
            user += (
                "\n\n上一轮输出存在以下违规，必须全部修正后重新输出完整 JSON：\n"
                + json.dumps(feedback, ensure_ascii=False, indent=1)
            )
        body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url.rstrip('/')}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = payload["choices"][0]["message"]["content"].strip()
        # 容错剥 ```json 围栏
        if text.startswith("```"):
            text = text.split("```", 2)[1].removeprefix("json").strip()
        return json.loads(text)
