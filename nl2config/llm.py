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
  NL2CONFIG_TIMEOUT    可选（单请求超时秒数，默认 120；reasoning 模型建议 300）
  NL2CONFIG_CALL_INTERVAL 可选（相邻两次调用的间隔秒数，默认 0；共享配额下建议 ≥2）
  NL2CONFIG_BACKOFF_SECONDS / NL2CONFIG_MAX_RETRIES 可选（429/5xx 退避秒数与重试次数，
  默认 60s / 3 次）
"""
import json
import os
from pathlib import Path
import time
import urllib.error
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
    "package(string), trackParams(object), pages(list of {pageId, title, "
    "components: list of {componentId, props: object, visible: bool}}), 以及可选 adSlots(list)。\n"
    "trackParams 格式（严格）：键必须匹配 ch_<channel>_<id>（channel∈weixin/douyin/baidu，"
    "id 为小写字母数字下划线，如 ch_weixin_main），值为该渠道投放 ID 字符串（如 wx-1001）；"
    "需求提到\"微信/抖音/百度渠道追踪\"时必须按此格式给出对应键值。\n"
    "套餐白名单（package 决定可用组件，越界=计费事故）：\n"
    + "\n".join(
        f"  {pkg}: {info['modules']}（广告位上限 {info['maxAdSlots']}）"
        for pkg, info in PACKAGES.items()
    )
    + "\n只能使用注册表中存在的 componentId/templateId/package；组件平台支持矩阵必须遵守。"
)

def build_system_prompt(few_shot: bool = False) -> str:
    """v2 基线 SYSTEM_PROMPT + 可选 few-shot 完整示例（研究开关，默认关）。"""
    if not few_shot:
        return SYSTEM_PROMPT
    example = (Path(__file__).resolve().parent.parent / "examples" / "site.json").read_text(encoding="utf-8")
    return SYSTEM_PROMPT + "\n\n完整合法输出示例（仅结构/格式示范，组件按需求选配）：\n" + example


class OpenAICompatLLM:
    """真实 API 客户端。generate 返回 JSON dict；文本不可解析时抛 ValueError。"""

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, feedback_style: str | None = None,
                 few_shot: bool | None = None):
        self._api_key = api_key or os.environ.get("NL2CONFIG_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self._base_url = (
            base_url
            or os.environ.get("NL2CONFIG_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
        )
        self._model = model or os.environ.get("NL2CONFIG_MODEL", "glm-4-flash")
        # 研究开关（默认与 v2 基线完全一致）：
        #   feedback_style: "json"（v2 结构化 JSON）| "directive"（带当前值+修正指令）
        #   few_shot:       是否在 system prompt 注入完整合法示例
        self.feedback_style = feedback_style or os.environ.get("NL2CONFIG_FEEDBACK_STYLE", "json")
        self._few_shot = (
            few_shot if few_shot is not None
            else os.environ.get("NL2CONFIG_FEW_SHOT", "0").lower() in ("1", "true", "yes")
        )
        if not self._api_key:
            raise LlmConfigError(
                "需要真实 LLM API 凭证：请设置 NL2CONFIG_API_KEY（或 OPENAI_API_KEY），"
                "可选 NL2CONFIG_BASE_URL / NL2CONFIG_MODEL 指向任意 OpenAI 兼容服务。"
            )

    def _render_user(self, requirement: str, feedback: list | None) -> str:
        user = f"需求：{requirement}"
        if not feedback:
            return user
        if self.feedback_style == "directive":
            lines = []
            for i, fb in enumerate(feedback, 1):
                line = f"{i}. [{fb['code']}] 路径 {fb['path']}：{fb['message']}"
                if "current_value" in fb:
                    line += f"\n   当前值：{json.dumps(fb['current_value'], ensure_ascii=False)[:200]}"
                if fb.get("fix_hint"):
                    line += f"\n   修正方法：{fb['fix_hint']}"
                if fb.get("options"):
                    line += f"\n   可选值：{fb['options']}"
                lines.append(line)
            return user + (
                "\n\n上一轮输出存在以下违规，逐条修正后重新输出完整 JSON"
                "（未涉及字段保持原值不变）：\n" + "\n".join(lines)
            )
        return user + (
            "\n\n上一轮输出存在以下违规，必须全部修正后重新输出完整 JSON：\n"
            + json.dumps(feedback, ensure_ascii=False, indent=1)
        )

    def generate(self, requirement: str, feedback: list | None = None) -> dict:
        user = self._render_user(requirement, feedback)
        body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": build_system_prompt(self._few_shot)},
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
        payload = self._post(req)
        text = payload["choices"][0]["message"]["content"].strip()
        # 容错剥 ```json 围栏
        if text.startswith("```"):
            text = text.split("```", 2)[1].removeprefix("json").strip()
        return json.loads(text)

    def _post(self, req: urllib.request.Request, timeout_s: int | None = None) -> dict:
        """发请求；429/瞬时 5xx 限速退避重试（共享配额下的必要韧性）。"""
        timeout_s = timeout_s or int(os.environ.get("NL2CONFIG_TIMEOUT", "120"))
        interval = float(os.environ.get("NL2CONFIG_CALL_INTERVAL", "0"))
        backoff_s = float(os.environ.get("NL2CONFIG_BACKOFF_SECONDS", "60"))
        max_retries = int(os.environ.get("NL2CONFIG_MAX_RETRIES", "3"))
        for attempt in range(max_retries + 1):
            if interval > 0:
                time.sleep(interval)
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < max_retries:
                    time.sleep(backoff_s)
                    continue
                raise
