"""研究开关（反馈风格 A/B + few-shot）的离线单测。

- json 风格 = v2 基线，字段集与逐字段内容不变（可复现性前提）
- directive 风格附加 current_value / fix_hint
- few-shot 示例本身必须通过全部校验器（防示例自身腐化）
"""
import json
import os
import unittest
from unittest import mock

from nl2config.llm import SYSTEM_PROMPT, OpenAICompatLLM, build_system_prompt
from nl2config.schema import validate_structure
from nl2config.validators import run_all
from nl2config.violations import Violation, build_feedback

CFG = {"siteName": "x", "templateId": "template_video", "platforms": ["ios"],
       "package": "pro", "pages": [{"pageId": "home", "title": "h",
       "components": [{"componentId": "live_stream", "props": {}, "visible": "true"}]}]}


class TestFeedbackStyles(unittest.TestCase):
    def test_json_style_is_v2_baseline(self):
        vs = [Violation("WRONG_TYPE", "/pages/0/components/0/visible", "类型错误：期望 bool，实际 str")]
        fb = build_feedback(vs, CFG)
        self.assertEqual(fb, [{"code": "WRONG_TYPE", "path": "/pages/0/components/0/visible",
                               "message": "类型错误：期望 bool，实际 str"}])

    def test_directive_style_enriches(self):
        vs = [Violation("UNSUPPORTED_PLATFORM", "/pages/0/components/0",
                        "组件 live_stream 不支持平台 ['ios']", options=["android"])]
        fb = build_feedback(vs, CFG, style="directive")[0]
        self.assertEqual(fb["current_value"], CFG["pages"][0]["components"][0])
        self.assertIn("二选一", fb["fix_hint"])
        self.assertEqual(fb["options"], ["android"])

    def test_directive_with_no_config(self):
        vs = [Violation("INVALID_JSON", "", "输出不是合法 JSON")]
        fb = build_feedback(vs, None, style="directive")[0]
        self.assertNotIn("current_value", fb)
        self.assertIn("JSON", fb["fix_hint"])

    def test_pointer_resolution_miss_returns_none(self):
        vs = [Violation("MISSING_REQUIRED", "/templateId", "缺少必填字段 templateId")]
        fb = build_feedback(vs, {"siteName": "x"}, style="directive")[0]
        self.assertIsNone(fb["current_value"])


class TestRenderUser(unittest.TestCase):
    def _llm(self, style):
        with mock.patch.dict(os.environ, {"NL2CONFIG_API_KEY": "k"}):
            return OpenAICompatLLM(feedback_style=style)

    def test_json_render_identical_to_v2(self):
        fb = [{"code": "WRONG_TYPE", "path": "/a", "message": "m"}]
        got = self._llm("json")._render_user("r", fb)
        want = "需求：r\n\n上一轮输出存在以下违规，必须全部修正后重新输出完整 JSON：\n" + \
            json.dumps(fb, ensure_ascii=False, indent=1)
        self.assertEqual(got, want)

    def test_directive_render(self):
        fb = [{"code": "WRONG_TYPE", "path": "/a", "message": "m",
               "fix_hint": "改类型", "current_value": "true"}]
        got = self._llm("directive")._render_user("r", fb)
        self.assertIn("逐条修正", got)
        self.assertIn("当前值：\"true\"", got)
        self.assertIn("修正方法：改类型", got)

    def test_no_feedback_just_requirement(self):
        self.assertEqual(self._llm("directive")._render_user("r", None), "需求：r")


class TestFewShotPrompt(unittest.TestCase):
    def test_base_prompt_unchanged(self):
        self.assertEqual(build_system_prompt(False), SYSTEM_PROMPT)

    def test_few_shot_example_is_valid_config(self):
        example = json.loads(build_system_prompt(True).split("完整合法输出示例", 1)[1].split("：\n", 1)[1])
        self.assertEqual(validate_structure(example), [])
        self.assertEqual(run_all(example), [])

    def test_env_switch(self):
        with mock.patch.dict(os.environ, {"NL2CONFIG_API_KEY": "k", "NL2CONFIG_FEW_SHOT": "1",
                                          "NL2CONFIG_FEEDBACK_STYLE": "directive"}):
            llm = OpenAICompatLLM()
        self.assertTrue(llm._few_shot)
        self.assertEqual(llm.feedback_style, "directive")


if __name__ == "__main__":
    unittest.main()
