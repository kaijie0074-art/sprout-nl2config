"""patch 引擎回归：白名单 / manual_locked / 全量重写防护 / 原子性（docs/05 P1-P7）。"""
import unittest

from nl2config.api import apply_patch
from nl2config.mock_llm import BASE_VIDEO

LOCKED = "/pages/0/components/1/props"  # 人工调过的 ad_banner 属性


class TestPatchEngine(unittest.TestCase):
    def setUp(self):
        self.cfg = BASE_VIDEO

    def test_p1_allowed_replace_applies(self):
        patch = [{"op": "replace", "path": "/pages/0/components/1/props/src",
                  "value": "banner-new.png"}]
        r = apply_patch(self.cfg, patch)
        self.assertTrue(r.ok, r.rejections)
        self.assertEqual(r.config["pages"][0]["components"][1]["props"]["src"], "banner-new.png")

    def test_p2_locked_node_rejected(self):
        patch = [{"op": "replace", "path": "/pages/0/components/1/props/src",
                  "value": "evil.png"}]
        r = apply_patch(self.cfg, patch, manual_locked=[LOCKED])
        self.assertFalse(r.ok)
        self.assertEqual(r.rejections[0].code, "LOCKED_NODE_TOUCHED")
        self.assertEqual(r.config, self.cfg, "拒绝后配置必须原样")

    def test_p2b_locked_ancestor_rejected(self):
        # 锁更深的节点，patch 改其父级 → 祖先触碰同样拒绝
        patch = [{"op": "replace", "path": "/pages/0/components/1", "value": {}}]
        r = apply_patch(self.cfg, patch, manual_locked=[LOCKED + "/src"])
        self.assertFalse(r.ok)
        self.assertEqual(r.rejections[0].code, "LOCKED_NODE_TOUCHED")

    def test_p3_move_from_locked_rejected(self):
        patch = [{"op": "move", "from": "/pages/0/components/1/props/src",
                  "path": "/pages/0/components/0/props/legacySrc"}]
        r = apply_patch(self.cfg, patch, manual_locked=[LOCKED])
        self.assertFalse(r.ok)
        self.assertEqual(r.rejections[0].code, "LOCKED_NODE_TOUCHED")

    def test_p4_root_replace_forbidden(self):
        """F6 全量重写：对根的 replace 是架构性禁止，与锁无关。"""
        patch = [{"op": "replace", "path": "/", "value": {"siteName": "整树重写"}}]
        r = apply_patch(self.cfg, patch)
        self.assertFalse(r.ok)
        self.assertEqual(r.rejections[0].code, "ROOT_REPLACE_FORBIDDEN")

    def test_p5_path_whitelist(self):
        patch = [{"op": "replace", "path": "/package", "value": "flagship"}]
        r = apply_patch(self.cfg, patch)
        self.assertFalse(r.ok)
        self.assertEqual(r.rejections[0].code, "PATH_NOT_WHITELISTED")

    def test_p6_atomicity(self):
        patch = [
            {"op": "replace", "path": "/pages/0/components/0/props/autoplay", "value": False},
            {"op": "replace", "path": "/package", "value": "flagship"},  # 第二条违规
        ]
        r = apply_patch(self.cfg, patch)
        self.assertFalse(r.ok)
        self.assertTrue(r.config["pages"][0]["components"][0]["props"]["autoplay"],
                        "任一 op 被拒 → 整个 patch 不应用（原子性）")

    def test_p7_patch_must_not_break_structure(self):
        # BASE_VIDEO 有 2 页：删 1 页仍合法；删光则破坏结构必须回滚
        r1 = apply_patch(self.cfg, [{"op": "remove", "path": "/pages/0"}])
        self.assertTrue(r1.ok)
        patch2 = [{"op": "remove", "path": "/pages/0"}, {"op": "remove", "path": "/pages/0"}]
        r2 = apply_patch(self.cfg, patch2)
        self.assertFalse(r2.ok)
        self.assertEqual(r2.rejections[0].code, "PATCH_BREAKS_STRUCTURE")


if __name__ == "__main__":
    unittest.main()
