"""结构约束校验器（第一层）：字段名 / 类型 / 嵌套 / 必填 / 枚举。

不依赖第三方 jsonschema 库——内部 schema 尚无正式文档（源文档 1.6），
先以代码内建的校验器钉住结构契约；后续 schema 文档化后可替换为
jsonschema 库实现（见 docs/03 开源调研）。
"""
from .violations import Violation

PLATFORM_ENUM = ["android", "ios"]
PACKAGE_ENUM = ["basic", "pro", "flagship"]

# 命名风格漂移别名表（失败模式 3）
ALIASES = {
    "site_name": "siteName", "template_id": "templateId", "track_params": "trackParams",
    "page_id": "pageId", "component_id": "componentId",
}


def _wrong(path, expect, got):
    return Violation("WRONG_TYPE", path, f"类型错误：期望 {expect}，实际 {type(got).__name__}", layer="structure")


def validate_structure(config) -> list:
    """校验配置树结构，返回违规列表（空列表 = 结构合法）。"""
    v = []
    if not isinstance(config, dict):
        return [Violation("WRONG_TYPE", "/", "配置根必须是对象", layer="structure")]

    # —— 命名风格漂移检测（先于必填检测，修正命名后字段才可见）——
    for key in list(config.keys()):
        if key in ALIASES:
            v.append(Violation("NAMING_DRIFT", "/" + key,
                               f"命名风格错误：{key} 应为 {ALIASES[key]}", layer="structure"))
    if v:
        return v  # 命名漂移会让后续字段检测产生噪音，先只报这一层

    # —— 顶层必填与类型 ——
    for f in ("siteName", "templateId", "platforms", "package", "pages"):
        if f not in config:
            v.append(Violation("MISSING_REQUIRED", "/" + f, f"缺少必填字段 {f}", layer="structure"))
    if not isinstance(config.get("siteName", ""), str):
        v.append(_wrong("/siteName", "str", config.get("siteName")))
    if not isinstance(config.get("templateId", ""), str):
        v.append(_wrong("/templateId", "str", config.get("templateId")))
    if "trackParams" in config and not isinstance(config["trackParams"], dict):
        v.append(_wrong("/trackParams", "object", config["trackParams"]))

    # —— 枚举字段 ——
    platforms = config.get("platforms")
    if platforms is not None:
        if not isinstance(platforms, list) or not platforms:
            v.append(Violation("WRONG_TYPE", "/platforms", "platforms 必须是非空数组", layer="structure"))
        else:
            for i, p in enumerate(platforms):
                if p not in PLATFORM_ENUM:
                    v.append(Violation("ENUM_INVALID", f"/platforms/{i}",
                                       f"非法平台 {p}", options=PLATFORM_ENUM, layer="structure"))
    pkg = config.get("package")
    if pkg is not None and pkg not in PACKAGE_ENUM:
        v.append(Violation("ENUM_INVALID", "/package", f"非法套餐 {pkg}",
                           options=PACKAGE_ENUM, layer="structure"))

    # —— pages 嵌套 ——
    pages = config.get("pages")
    if pages is not None:
        if not isinstance(pages, list) or not pages:
            v.append(Violation("WRONG_TYPE", "/pages", "pages 必须是非空数组", layer="structure"))
        else:
            v.extend(_validate_pages(pages))
    return v


def _validate_pages(pages) -> list:
    v = []
    for i, page in enumerate(pages):
        base = f"/pages/{i}"
        if not isinstance(page, dict):
            v.append(_wrong(base, "object", page))
            continue
        for key in list(page.keys()):
            if key in ALIASES:
                v.append(Violation("NAMING_DRIFT", f"{base}/{key}",
                                   f"命名风格错误：{key} 应为 {ALIASES[key]}", layer="structure"))
        for f in ("pageId", "title", "components"):
            if f not in page:
                v.append(Violation("MISSING_REQUIRED", f"{base}/{f}", f"缺少必填字段 {f}", layer="structure"))
        comps = page.get("components")
        if comps is not None:
            if not isinstance(comps, list):
                v.append(_wrong(f"{base}/components", "array", comps))
            else:
                v.extend(_validate_components(comps, base))
    return v


def _validate_components(comps, page_base) -> list:
    v = []
    for j, comp in enumerate(comps):
        base = f"{page_base}/components/{j}"
        if not isinstance(comp, dict):
            v.append(_wrong(base, "object", comp))
            continue
        for key in list(comp.keys()):
            if key in ALIASES:
                v.append(Violation("NAMING_DRIFT", f"{base}/{key}",
                                   f"命名风格错误：{key} 应为 {ALIASES[key]}", layer="structure"))
        if "componentId" not in comp:
            v.append(Violation("MISSING_REQUIRED", f"{base}/componentId", "缺少必填字段 componentId", layer="structure"))
        elif not isinstance(comp["componentId"], str):
            v.append(_wrong(f"{base}/componentId", "str", comp["componentId"]))
        if "props" in comp and not isinstance(comp["props"], dict):
            v.append(_wrong(f"{base}/props", "object", comp["props"]))
        # 严格布尔：字符串 "true" 是失败模式 2 的典型样本
        if "visible" in comp and not isinstance(comp["visible"], bool):
            v.append(_wrong(f"{base}/visible", "bool", comp["visible"]))
    return v
