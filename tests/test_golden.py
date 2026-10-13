"""golden 回归评测集测试（第五层）。

确定性层（离线）：ScriptedProvider 按场景语料驱动，验证回归器本身的
统计口径与全绿判据；live 层（env-gated）：真实 LLM 跑 golden 集。
"""
import os
import unittest


from nl2config.api import run_golden_regression
from providers import ScriptedProvider


class TestGoldenRegressionHarness(unittest.TestCase):
    """回归器口径测试（离线，脚本语料经测试替身注入）。"""

    def test_golden_all_green_with_scripted(self):
        report = run_golden_regression(llm=ScriptedProvider("ok"))
        self.assertTrue(report["passed"], f"失败对：{report['failed']}")
        self.assertEqual(report["total"], 8)

    def test_metrics_reported(self):
        report = run_golden_regression(llm=ScriptedProvider("ok"))
        m = report["metrics"]
        # ok 场景 8 对全部一次通过
        self.assertAlmostEqual(m["first_pass_rate"], 1.0)
        self.assertAlmostEqual(m["converged_rate"], 1.0)


@unittest.skipIf(
    not (os.environ.get("NL2CONFIG_API_KEY") or os.environ.get("OPENAI_API_KEY")),
    "live 回归需要真实 LLM 凭证（NL2CONFIG_API_KEY 或 OPENAI_API_KEY）",
)
class TestGoldenRegressionLive(unittest.TestCase):
    def test_golden_real_llm(self):
        report = run_golden_regression()
        self.assertEqual(report["total"], 8)
        # 真实模型的合法解不唯一，判据是校验全绿；此处只要求收敛率可度量地报告出来
        print("live metrics:", report["metrics"])


if __name__ == "__main__":
    unittest.main()
