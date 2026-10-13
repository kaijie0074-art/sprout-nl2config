"""生成管线回归：覆盖 7 类失败模式 + 降级路径（对应 docs/05 映射表 F1-F7/D1）。

两层：
1. 确定性层（离线）：以 tests.providers.ScriptedProvider 注入场景语料，回归
   校验-修复循环的收敛与降级——测试替身仅存在于 tests/，产品代码零脚本化模型；
2. live 层（env-gated）：真实 LLM（OpenAI 兼容协议）跑正常需求，无凭证自动跳过。
"""
import os
import unittest


from nl2config.api import generate_config
from nl2config.llm import LlmConfigError, OpenAICompatLLM
from nl2config.registry import COMPONENTS, PACKAGES
from nl2config.validators import run_all
from providers import ScriptedProvider
from scenarios import SCENARIOS


def _component_ids(cfg):
    return [c["componentId"] for p in cfg["pages"] for c in p["components"]]


class TestNormalGeneration(unittest.TestCase):
    def test_ok_first_pass(self):
        r = generate_config("做个视频资讯站", llm=ScriptedProvider("ok"))
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.attempts, 1)
        self.assertEqual(r.violation_history[0], [])


class TestFailureModeRepairs(unittest.TestCase):
    """F1 幻觉 ID / F2 类型漂移 / F3 命名漂移 / F4 必填省略 / F5 语义违规。"""

    def test_f1_hallucinated_id_repaired(self):
        r = generate_config("视频站", llm=ScriptedProvider("hallucinated_id"))
        self.assertEqual(r.status, "ok")
        ids = _component_ids(r.config)
        self.assertTrue(set(ids) <= set(COMPONENTS),
                        "最终配置不得包含幻觉 ID")

    def test_f2_type_drift_repaired(self):
        r = generate_config("视频站", llm=ScriptedProvider("type_drift"))
        self.assertEqual(r.status, "ok")
        vis = r.config["pages"][0]["components"][0]["visible"]
        self.assertIsInstance(vis, bool, "visible 必须是真布尔，不是字符串 'true'")

    def test_f3_naming_drift_repaired(self):
        r = generate_config("视频站", llm=ScriptedProvider("naming_drift"))
        self.assertEqual(r.status, "ok")
        self.assertIn("siteName", r.config)
        self.assertNotIn("site_name", r.config)

    def test_f4_missing_required_repaired(self):
        r = generate_config("视频站", llm=ScriptedProvider("missing_required"))
        self.assertEqual(r.status, "ok")
        self.assertIn("templateId", r.config)

    def test_f5_unsupported_platform_repaired(self):
        r = generate_config("双端直播站", llm=ScriptedProvider("unsupported_platform"))
        self.assertEqual(r.status, "ok")
        self.assertEqual(run_all(r.config), [], "修复后全量校验必须干净")

    def test_semantic_ad_limit_enforced(self):
        r = generate_config("广告位拉满的站", llm=ScriptedProvider("ad_limit_exceed"))
        self.assertEqual(r.status, "ok")
        limit = PACKAGES[r.config["package"]]["maxAdSlots"]
        ads = [c for p in r.config["pages"] for c in p["components"] if c["componentId"] == "ad_banner"]
        self.assertLessEqual(len(ads), limit)

    def test_business_package_whitelist_enforced(self):
        r = generate_config("带商城的站", llm=ScriptedProvider("package_violation"))
        self.assertEqual(r.status, "ok")
        whitelist = set(PACKAGES[r.config["package"]]["modules"])
        self.assertTrue(set(_component_ids(r.config)) <= whitelist)

    def test_business_track_param_format(self):
        r = generate_config("视频站", llm=ScriptedProvider("track_param_bad"))
        self.assertEqual(r.status, "ok")
        self.assertEqual(list(r.config["trackParams"]), ["ch_weixin_main"])


class TestDegradation(unittest.TestCase):
    """D1：不可纠正场景必须显式降级转人工，不存在"大概是对的"。"""

    def test_stubborn_degrades_after_retry_limit(self):
        r = generate_config("顽固幻觉场景", llm=ScriptedProvider("stubborn"), max_retries=3)
        self.assertEqual(r.status, "degraded")
        self.assertIsNone(r.config, "降级时不得返回半成品配置")
        self.assertEqual(r.attempts, 4, "1 次生成 + 3 次重试")
        self.assertIsNotNone(r.last_raw_config,
                             "降级时保留最后一轮非法输出供排障/转人工（不作为交付物）")
        self.assertIsNone(generate_config("ok 场景", llm=ScriptedProvider("ok")).last_raw_config)

    def test_no_intermediate_state(self):
        """任何场景的返回只有 ok（全绿）或 degraded（附原因），无第三态。"""
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                r = generate_config("回归扫描", llm=ScriptedProvider(scenario))
                self.assertIn(r.status, ("ok", "degraded"))
                if r.status == "ok":
                    self.assertEqual(run_all(r.config), [])


class TestRealLlmConfig(unittest.TestCase):
    def test_missing_credentials_explicit_error(self):
        key = os.environ.pop("NL2CONFIG_API_KEY", None)
        openai_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with self.assertRaises(LlmConfigError) as ctx:
                OpenAICompatLLM()
            self.assertIn("NL2CONFIG_API_KEY", str(ctx.exception))
        finally:
            for k, v in (("NL2CONFIG_API_KEY", key), ("OPENAI_API_KEY", openai_key)):
                if v is not None:
                    os.environ[k] = v


@unittest.skipIf(
    not (os.environ.get("NL2CONFIG_API_KEY") or os.environ.get("OPENAI_API_KEY")),
    "live 回归需要真实 LLM 凭证（NL2CONFIG_API_KEY 或 OPENAI_API_KEY）",
)
class TestRealLlmLive(unittest.TestCase):
    """真实 LLM：正常需求必须在有限重试内收敛到全绿配置。"""

    def test_normal_requirement_converges(self):
        r = generate_config("做一个视频资讯站，安卓端，专业版套餐，接微信渠道追踪")
        self.assertEqual(r.status, "ok", f"违规历史：{r.violation_history}")
        self.assertEqual(run_all(r.config), [])


if __name__ == "__main__":
    unittest.main()
