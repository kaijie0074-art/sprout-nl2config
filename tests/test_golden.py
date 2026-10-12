"""golden 回归评测集测试（第五层验收：回归全绿 + 指标产出）。"""
import unittest

from nl2config.api import run_golden_regression


class TestGoldenRegression(unittest.TestCase):
    def test_golden_all_green(self):
        report = run_golden_regression()
        self.assertTrue(report["passed"], f"失败对：{report['failed']}")
        self.assertEqual(report["total"], 8)

    def test_metrics_reported(self):
        report = run_golden_regression()
        m = report["metrics"]
        # 8 对中 3 对 ok 场景一次通过、1 对触发幻觉后收敛
        self.assertAlmostEqual(m["first_pass_rate"], 3 / 8)
        self.assertAlmostEqual(m["converged_rate"], 1.0)
        self.assertAlmostEqual(m["hallucination_rate"], 1 / 8)


if __name__ == "__main__":
    unittest.main()
