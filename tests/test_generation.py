"""生成管线回归：覆盖 7 类失败模式 + 降级路径（对应 docs/05 映射表 F1-F7/D1）。

同一套测试在 baseline（naive 管线）上失败 = 复现材料（docs/02）。
"""
import unittest

from nl2config.api import generate_config
from nl2config.mock_llm import SCENARIOS
from nl2config.registry import COMPONENTS, PACKAGES
from nl2config.validators import run_all


def _component_ids(cfg):
    return [c["componentId"] for p in cfg["pages"] for c in p["components"]]


class TestNormalGeneration(unittest.TestCase):
    def test_ok_first_pass(self):
        r = generate_config("做个视频资讯站", scenario="ok")
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.attempts, 1)
        self.assertEqual(r.violation_history[0], [])


class TestFailureModeRepairs(unittest.TestCase):
    """F1 幻觉 ID / F2 类型漂移 / F3 命名漂移 / F4 必填省略 / F5 语义违规。"""

    def test_f1_hallucinated_id_repaired(self):
        r = generate_config("视频站", scenario="hallucinated_id")
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.attempts, 2, "结构化反馈后应第 2 轮收敛")
        self.assertEqual(r.violation_history[0][0]["code"], "INVALID_COMPONENT_ID")
        self.assertTrue(set(_component_ids(r.config)) <= set(COMPONENTS),
                        "最终配置不得包含幻觉 ID")

    def test_f2_type_drift_repaired(self):
        r = generate_config("视频站", scenario="type_drift")
        self.assertEqual(r.status, "ok")
        vis = r.config["pages"][0]["components"][0]["visible"]
        self.assertIsInstance(vis, bool, "visible 必须是真布尔，不是字符串 'true'")

    def test_f3_naming_drift_repaired(self):
        r = generate_config("视频站", scenario="naming_drift")
        self.assertEqual(r.status, "ok")
        for key in ("siteName", "templateId", "pages"):
            self.assertIn(key, r.config)
        self.assertNotIn("site_name", r.config)

    def test_f4_missing_required_repaired(self):
        r = generate_config("视频站", scenario="missing_required")
        self.assertEqual(r.status, "ok")
        self.assertIn("templateId", r.config)

    def test_f5_unsupported_platform_repaired(self):
        r = generate_config("双端直播站", scenario="unsupported_platform")
        self.assertEqual(r.status, "ok")
        self.assertEqual(run_all(r.config), [], "修复后全量校验必须干净")

    def test_semantic_ad_limit_enforced(self):
        r = generate_config("广告位拉满的站", scenario="ad_limit_exceed")
        self.assertEqual(r.status, "ok")
        ads = [c for p in r.config["pages"] for c in p["components"]
               if c["componentId"] in ("ad_banner", "ad_popup")]
        limit = PACKAGES[r.config["package"]]["maxAdSlots"]
        self.assertLessEqual(len(ads), limit)

    def test_business_package_whitelist_enforced(self):
        r = generate_config("带商城的站", scenario="package_violation")
        self.assertEqual(r.status, "ok")
        whitelist = set(PACKAGES[r.config["package"]]["modules"])
        self.assertTrue(set(_component_ids(r.config)) <= whitelist)

    def test_business_track_param_format(self):
        r = generate_config("视频站", scenario="track_param_bad")
        self.assertEqual(r.status, "ok")
        self.assertEqual(list(r.config["trackParams"]), ["ch_weixin_main"])


class TestDegradation(unittest.TestCase):
    """D1：不可纠正场景必须显式降级转人工，不存在"大概是对的"。"""

    def test_stubborn_degrades_after_retry_limit(self):
        r = generate_config("顽固幻觉场景", scenario="stubborn", max_retries=3)
        self.assertEqual(r.status, "degraded")
        self.assertIsNone(r.config, "降级时不得返回半成品配置")
        self.assertEqual(r.attempts, 4, "1 次生成 + 3 次重试")
        self.assertTrue(r.degraded_reasons, "降级必须携带失败原因清单供人工处置")

    def test_no_intermediate_state(self):
        """任何场景的返回只有 ok（全绿）或 degraded（附原因），无第三态。"""
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                r = generate_config("回归扫描", scenario=scenario)
                self.assertIn(r.status, ("ok", "degraded"))
                if r.status == "ok":
                    self.assertEqual(run_all(r.config), [])


if __name__ == "__main__":
    unittest.main()
