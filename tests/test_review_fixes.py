"""评审轮修复验证（PR #2 评审意见 R1-1/R1-2 的回归测试）。"""
import unittest

from nl2config.api import apply_patch
from nl2config.mock_llm import BASE_VIDEO
from nl2config.registry import PACKAGES


class TestReviewFixes(unittest.TestCase):
    def test_r1_1a_malformed_index_rejected_not_crash(self):
        """R1-1：非数字数组下标必须结构化拒绝，不得抛未捕获异常。"""
        patch = [{"op": "replace", "path": "/pages/abc/components/0/props/src",
                  "value": "x.png"}]
        r = apply_patch(BASE_VIDEO, patch)   # 不得 raise
        self.assertFalse(r.ok)
        self.assertEqual(r.rejections[0].code, "PATH_UNRESOLVABLE")
        self.assertEqual(r.config, BASE_VIDEO, "拒绝后配置原样")

    def test_r1_1b_out_of_bound_rejected(self):
        """R1-1：越界下标同样结构化拒绝。"""
        patch = [{"op": "remove", "path": "/pages/99"}]
        r = apply_patch(BASE_VIDEO, patch)
        self.assertFalse(r.ok)
        self.assertEqual(r.rejections[0].code, "PATH_UNRESOLVABLE")

    def test_r1_2_package_whitelist_sorted(self):
        """R1-2：套餐白名单顺序跨运行稳定（sorted 固化）。"""
        for pkg in PACKAGES.values():
            self.assertEqual(pkg["modules"], sorted(pkg["modules"]))


if __name__ == "__main__":
    unittest.main()
