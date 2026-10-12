"""第二~四层校验器：引用完整性 / 语义约束 / 业务约束。

这些约束不在 JSON Schema 里（源文档 1.3），散落在平台代码与业务规则中，
必须自建。所有错误信息结构化并携带合法可选值——这是第三层
"合法枚举注入"的另一半：不仅把枚举喂给上游，也让错误信息教会模型下次怎么改。
"""
import re

from .registry import (AD_KINDS, COMPONENTS, MAX_AD_BANNER_PER_PAGE, PACKAGES,
                       TEMPLATES, TRACK_PARAM_PATTERN)
from .violations import Violation


def validate_references(config: dict) -> list:
    """引用完整性：componentId / templateId 必须真实存在（失败模式 1）。"""
    v = []
    if config.get("templateId") not in TEMPLATES:
        v.append(Violation("UNKNOWN_TEMPLATE", "/templateId",
                           f"模板 {config.get('templateId')!r} 不存在",
                           options=sorted(TEMPLATES), layer="reference"))
    for i, page in enumerate(config.get("pages", [])):
        for j, comp in enumerate(page.get("components", [])):
            cid = comp.get("componentId")
            if cid not in COMPONENTS:
                v.append(Violation(
                    "INVALID_COMPONENT_ID", f"/pages/{i}/components/{j}",
                    f"组件 {cid!r} 不存在（幻觉 ID）",
                    options=sorted(COMPONENTS), layer="reference"))
    return v


def validate_semantics(config: dict) -> list:
    """语义约束：双端兼容 / 广告位数量（schema 校验通过也会在这里炸的一类）。"""
    v = []
    platforms = set(config.get("platforms", []))
    # 双端兼容矩阵
    for i, page in enumerate(config.get("pages", [])):
        for j, comp in enumerate(page.get("components", [])):
            cid = comp.get("componentId")
            if cid in COMPONENTS:
                supported = set(COMPONENTS[cid]["platforms"])
                if not platforms <= supported:
                    v.append(Violation(
                        "UNSUPPORTED_PLATFORM", f"/pages/{i}/components/{j}",
                        f"组件 {cid} 不支持平台 {sorted(platforms - supported)}",
                        options=sorted(supported), layer="semantic"))
    # 广告位总量（套餐上限）与单页横幅上限
    ad_count = sum(
        1 for page in config.get("pages", [])
        for comp in page.get("components", [])
        if comp.get("componentId") in AD_KINDS)
    limit = PACKAGES.get(config.get("package"), {}).get("maxAdSlots", 0)
    if ad_count > limit:
        v.append(Violation("AD_SLOT_EXCEEDED", "/pages",
                           f"广告位 {ad_count} 个超过套餐上限 {limit}",
                           layer="semantic"))
    for i, page in enumerate(config.get("pages", [])):
        banners = sum(1 for c in page.get("components", []) if c.get("componentId") == "ad_banner")
        if banners > MAX_AD_BANNER_PER_PAGE:
            v.append(Violation("AD_PER_PAGE_EXCEEDED", f"/pages/{i}",
                               f"单页 ad_banner {banners} 个超过上限 {MAX_AD_BANNER_PER_PAGE}",
                               layer="semantic"))
    return v


def validate_business(config: dict) -> list:
    """业务约束：套餐模块白名单 / 渠道追踪参数格式（计费与归因事故防线）。"""
    v = []
    pkg = config.get("package")
    whitelist = PACKAGES.get(pkg, {}).get("modules", [])
    for i, page in enumerate(config.get("pages", [])):
        for j, comp in enumerate(page.get("components", [])):
            cid = comp.get("componentId")
            if cid in COMPONENTS and cid not in whitelist:
                v.append(Violation(
                    "MODULE_NOT_IN_PACKAGE", f"/pages/{i}/components/{j}",
                    f"组件 {cid} 不在 {pkg} 套餐白名单内",
                    options=sorted(whitelist), layer="business"))
    pattern = re.compile(TRACK_PARAM_PATTERN)
    for key in config.get("trackParams", {}):
        if not pattern.match(key):
            v.append(Violation(
                "TRACK_PARAM_FORMAT", f"/trackParams/{key}",
                f"追踪参数 {key!r} 不符合渠道格式 ch_<channel>_<id>",
                options=["ch_weixin_*", "ch_douyin_*", "ch_baidu_*"], layer="business"))
    return v


def run_all(config: dict) -> list:
    """结构合法前提下的全量校验（结构违规由 schema 层先行拦截）。"""
    return validate_references(config) + validate_semantics(config) + validate_business(config)
