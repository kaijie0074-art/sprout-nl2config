"""低代码平台资产注册表（模拟）：组件 / 模板 / 套餐 / 广告位限制。

真实场景里这张表散落在平台代码中，是逆向整理出来的 machine-readable
资产（源文档 1.6 第一条加重因素）。带版本号：模板库持续新增，约束层
必须版本化管理，否则每月一次静默腐化。
"""

SCHEMA_VERSION = "2026.10.0"

# 组件注册表：componentId → 双端支持矩阵 + 分类
COMPONENTS = {
    "video_player":    {"platforms": ["android", "ios"], "kind": "media"},
    "short_video_feed": {"platforms": ["android", "ios"], "kind": "media"},
    "live_stream":     {"platforms": ["android"],         "kind": "media"},  # iOS 不支持
    "community_forum": {"platforms": ["android", "ios"], "kind": "social"},
    "mall_shop":       {"platforms": ["android", "ios"], "kind": "commerce"},
    "coupon_center":   {"platforms": ["android", "ios"], "kind": "commerce"},
    "ad_banner":       {"platforms": ["android", "ios"], "kind": "ad"},
    "ad_popup":        {"platforms": ["android"],         "kind": "ad"},     # iOS 不支持弹窗广告
    "search_bar":      {"platforms": ["android", "ios"], "kind": "basic"},
    "nav_tab":         {"platforms": ["android", "ios"], "kind": "basic"},
}

# 模板注册表
TEMPLATES = {
    "template_video":      {"name": "视频资讯站", "tags": ["video", "feed"]},
    "template_ecommerce":  {"name": "电商带货站", "tags": ["mall", "coupon"]},
    "template_community":  {"name": "社区论坛站", "tags": ["forum", "ugc"]},
    "template_corporate":  {"name": "企业官网",   "tags": ["corp"]},
    "template_hybrid":     {"name": "混合站",     "tags": ["video", "mall"]},
}

# 套餐：模块白名单 + 广告位数量上限（业务约束：超出售卖范围 = 计费事故）
# R1-2（评审修复）：白名单 sorted 固化——set 推导顺序不定会导致错误信息
# options 与 golden 对照跨运行漂移，不可复现。
PACKAGES = {
    "basic":    {"modules": ["video_player", "search_bar", "nav_tab", "ad_banner"], "maxAdSlots": 2},
    "pro":      {"modules": sorted(COMPONENTS.keys() - {"live_stream"}),            "maxAdSlots": 4},
    "flagship": {"modules": sorted(COMPONENTS.keys()),                              "maxAdSlots": 6},
}

# 渠道追踪参数格式（业务约束：归因出错 = 收入层面事故）
TRACK_PARAM_PATTERN = "ch_(weixin|douyin|baidu)_[a-z0-9_]+"

AD_KINDS = {"ad_banner", "ad_popup"}
MAX_AD_BANNER_PER_PAGE = 2


def ad_component_ids() -> list:
    return sorted(cid for cid, meta in COMPONENTS.items() if meta["kind"] == "ad")
