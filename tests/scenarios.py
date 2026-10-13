"""失败模式回归语料（测试夹具，仅 tests/ 内使用；产品代码不含任何脚本化模型）。

数据形态：scenario -> (首次/坏输出, 修正输出)。经 tests.providers.ScriptedProvider
驱动校验-修复循环，回归 7 类真实失败模式的拦截与收敛（docs/05 映射表 F1-F7/D1）。
合法基线配置 BASE_* 同时供 patch/校验器测试复用。
"""
from copy import deepcopy

# ---------- 合法基线配置（三个"正常"场景各自的正确输出） ----------

BASE_VIDEO = {
    "siteName": "客户视频站",
    "templateId": "template_video",
    "platforms": ["android"],
    "package": "pro",
    "trackParams": {"ch_weixin_main": "wx-1001"},
    "pages": [
        {
            "pageId": "home", "title": "首页",
            "components": [
                {"componentId": "video_player", "props": {"autoplay": True}, "visible": True},
                {"componentId": "ad_banner", "props": {"src": "banner-a.png"}, "visible": True},
            ],
        },
        {
            "pageId": "community", "title": "社区",
            "components": [{"componentId": "community_forum", "props": {}, "visible": True}],
        },
    ],
}

BASE_ECOMMERCE = {
    "siteName": "带货商城站",
    "templateId": "template_ecommerce",
    "platforms": ["android", "ios"],
    "package": "flagship",
    "trackParams": {"ch_douyin_shop": "dy-2001"},
    "pages": [
        {
            "pageId": "home", "title": "首页",
            "components": [
                {"componentId": "mall_shop", "props": {"cart": True}, "visible": True},
                {"componentId": "coupon_center", "props": {}, "visible": True},
                {"componentId": "short_video_feed", "props": {"swipe": "up"}, "visible": True},
                {"componentId": "ad_banner", "props": {"src": "banner-b.png"}, "visible": True},
                {"componentId": "ad_banner", "props": {"src": "banner-c.png"}, "visible": True},
            ],
        },
    ],
}

BASE_COMMUNITY = {
    "siteName": "本地社区站",
    "templateId": "template_community",
    "platforms": ["ios"],
    "package": "pro",
    "pages": [
        {
            "pageId": "home", "title": "首页",
            "components": [
                {"componentId": "community_forum", "props": {}, "visible": True},
                {"componentId": "search_bar", "props": {}, "visible": True},
                {"componentId": "nav_tab", "props": {"tabs": 4}, "visible": True},
            ],
        },
    ],
}


def _live_stream_added(base: dict) -> dict:
    cfg = deepcopy(base)
    cfg["pages"][0]["components"].append(
        {"componentId": "live_stream", "props": {}, "visible": True})
    return cfg


def _snake(base: dict) -> dict:
    """snake_case 命名漂移版本（失败模式 3）。"""
    bad = deepcopy(base)
    bad["site_name"] = bad.pop("siteName")
    bad["template_id"] = bad.pop("templateId")
    if "trackParams" in bad:
        bad["track_params"] = bad.pop("trackParams")
    for page in bad["pages"]:
        page["page_id"] = page.pop("pageId")
        for comp in page["components"]:
            comp["component_id"] = comp.pop("componentId")
    return bad


def _defect(base: dict, mutate) -> dict:
    bad = deepcopy(base)
    mutate(bad)
    return bad


# ---------- 场景语料：scenario -> (首次/坏输出, 修正输出) ----------

SCENARIOS = {
    # 正常场景：坏输出 == 正确输出
    "ok":           (deepcopy(BASE_VIDEO), deepcopy(BASE_VIDEO)),
    "ok_ecommerce": (deepcopy(BASE_ECOMMERCE), deepcopy(BASE_ECOMMERCE)),
    "ok_community": (deepcopy(BASE_COMMUNITY), deepcopy(BASE_COMMUNITY)),
    # 失败模式 1：幻觉 ID——库里只有 video_player，编造 v2
    "hallucinated_id": (
        _defect(BASE_VIDEO, lambda c: c["pages"][0]["components"][0].__setitem__("componentId", "video_player_v2")),
        deepcopy(BASE_VIDEO),
    ),
    # 失败模式 2：类型漂移——布尔/枚举给成字符串
    "type_drift": (
        _defect(BASE_VIDEO, lambda c: c["pages"][0]["components"][0].__setitem__("visible", "true")),
        deepcopy(BASE_VIDEO),
    ),
    # 失败模式 3：命名风格漂移
    "naming_drift":  (_snake(BASE_VIDEO), deepcopy(BASE_VIDEO)),
    # 失败模式 4：必填项省略
    "missing_required": (
        _defect(BASE_VIDEO, lambda c: c.pop("templateId")),
        deepcopy(BASE_VIDEO),
    ),
    # 失败模式 5：语义违规——iOS 配了不支持的直播组件
    "unsupported_platform": (
        _defect(_live_stream_added(BASE_VIDEO), lambda c: c.__setitem__("platforms", ["android", "ios"])),
        _defect(_live_stream_added(BASE_VIDEO), lambda c: c.__setitem__("package", "flagship")),
    ),
    # 语义违规：广告位超上限（basic 上限 2，配了 7 个）
    "ad_limit_exceed": (
        _defect(BASE_VIDEO, lambda c: (
            c.__setitem__("package", "basic"),
            c.__setitem__("pages", [{
                "pageId": "home", "title": "首页",
                "components": [
                    {"componentId": "ad_banner", "props": {"src": f"b{i}.png"}, "visible": True}
                    for i in range(7)
                ],
            }]),
        )),
        {
            "siteName": "客户视频站", "templateId": "template_video", "platforms": ["android"],
            "package": "basic",
            "pages": [{
                "pageId": "home", "title": "首页",
                "components": [
                    {"componentId": "video_player", "props": {}, "visible": True},
                    {"componentId": "ad_banner", "props": {"src": "b0.png"}, "visible": True},
                    {"componentId": "ad_banner", "props": {"src": "b1.png"}, "visible": True},
                ],
            }],
        },
    ),
    # 业务违规：basic 套餐配了旗舰模块
    "package_violation": (
        _defect(BASE_VIDEO, lambda c: (
            c.__setitem__("package", "basic"),
            c["pages"][0]["components"].append(
                {"componentId": "mall_shop", "props": {}, "visible": True}),
        )),
        _defect(BASE_VIDEO, lambda c: (
            c.__setitem__("package", "pro"),
            c["pages"][0]["components"].append(
                {"componentId": "mall_shop", "props": {}, "visible": True}),
        )),
    ),
    # 业务违规：渠道追踪参数格式错（归因事故源头）
    "track_param_bad": (
        _defect(BASE_VIDEO, lambda c: c.__setitem__("trackParams", {"utm_source": "wx-1001"})),
        deepcopy(BASE_VIDEO),
    ),
    # 永不修正：驱动降级路径
    "stubborn": (
        _defect(BASE_VIDEO, lambda c: c["pages"][0]["components"][0].__setitem__("componentId", "live_wall_v9")),
        None,  # 没有修正版
    ),
}

# 可纠正场景（stubborn 之外全部可被结构化反馈纠正）
CORRECTABLE = {s for s in SCENARIOS if s != "stubborn"}
