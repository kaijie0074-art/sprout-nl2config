"""OpenAICompatLLM 传输层韧性测试（不触网）：

- 429/503 指数配额退避后成功（共享订阅下的必要韧性）
- 非可重试 HTTP 错误立即抛出
- 调用间隔（NL2CONFIG_CALL_INTERVAL）生效
"""
import io
import json
import os
import unittest
import urllib.error
from unittest import mock

from nl2config.llm import OpenAICompatLLM


def _ok_response(payload: dict):
    raw = json.dumps(payload).encode("utf-8")
    resp = mock.MagicMock()
    resp.read.return_value = raw
    resp.__enter__.return_value = resp
    return resp


class _Env:
    """测试期内覆盖退避相关环境变量（不拖慢测试）。"""

    def __init__(self, **overrides):
        self.overrides = overrides
        self.saved = {}

    def __enter__(self):
        for k, v in self.overrides.items():
            self.saved[k] = os.environ.get(k)
            os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


class TestTransportBackoff(unittest.TestCase):
    def _llm(self):
        with mock.patch.dict(os.environ, {"NL2CONFIG_API_KEY": "test-key"}):
            return OpenAICompatLLM()

    def test_429_backoff_then_success(self):
        llm = self._llm()
        err = urllib.error.HTTPError("url", 429, "Too Many Requests", hdrs=None, fp=io.BytesIO(b"{}"))
        ok = _ok_response({"choices": [{"message": {"content": "{\"a\": 1}"}}]})
        sleeps = []
        with _Env(NL2CONFIG_BACKOFF_SECONDS="0", NL2CONFIG_CALL_INTERVAL="0"), \
                mock.patch("urllib.request.urlopen", side_effect=[err, err, ok]), \
                mock.patch("time.sleep", side_effect=sleeps.append):
            out = llm.generate("需求：测试")
        self.assertEqual(out, {"a": 1})
        self.assertEqual(len(sleeps), 2)  # 两次退避

    def test_503_backoff_then_success(self):
        llm = self._llm()
        err = urllib.error.HTTPError("url", 503, "Unavailable", hdrs=None, fp=io.BytesIO(b"{}"))
        ok = _ok_response({"choices": [{"message": {"content": "{}"}}]})
        with _Env(NL2CONFIG_BACKOFF_SECONDS="0", NL2CONFIG_CALL_INTERVAL="0"), \
                mock.patch("urllib.request.urlopen", side_effect=[err, ok]), \
                mock.patch("time.sleep"):
            out = llm.generate("需求：测试")
        self.assertEqual(out, {})

    def test_non_retryable_error_raises(self):
        llm = self._llm()
        err = urllib.error.HTTPError("url", 401, "Unauthorized", hdrs=None, fp=io.BytesIO(b"{}"))
        with _Env(NL2CONFIG_CALL_INTERVAL="0"), \
                mock.patch("urllib.request.urlopen", side_effect=err), \
                mock.patch("time.sleep") as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                llm.generate("需求：测试")
        sleep.assert_not_called()

    def test_retry_exhaustion_raises(self):
        llm = self._llm()
        err = urllib.error.HTTPError("url", 429, "Too Many Requests", hdrs=None, fp=io.BytesIO(b"{}"))
        with _Env(NL2CONFIG_BACKOFF_SECONDS="0", NL2CONFIG_MAX_RETRIES="1",
                  NL2CONFIG_CALL_INTERVAL="0"), \
                mock.patch("urllib.request.urlopen", side_effect=err), \
                mock.patch("time.sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                llm.generate("需求：测试")

    def test_call_interval_applied(self):
        llm = self._llm()
        ok = _ok_response({"choices": [{"message": {"content": "{}"}}]})
        sleeps = []
        with _Env(NL2CONFIG_CALL_INTERVAL="2"), \
                mock.patch("urllib.request.urlopen", return_value=ok), \
                mock.patch("time.sleep", side_effect=sleeps.append):
            llm.generate("需求：测试")
        self.assertIn(2.0, sleeps)


if __name__ == "__main__":
    unittest.main()
