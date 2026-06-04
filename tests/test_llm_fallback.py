"""Regression tests for service-level LLM provider failover."""
import json
import os
import sys
import urllib.error
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lib


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_transient_primary_failure_falls_back_to_anthropic():
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) <= 3:
            raise urllib.error.URLError("ssl eof")
        return FakeResponse({"content": [{"type": "text", "text": "备用模型输出"}]})

    with patch.object(lib, "LLM_PROVIDER", "deepseek"), \
            patch.object(lib, "LLM_FALLBACK_PROVIDER", "anthropic"), \
            patch("urllib.request.urlopen", fake_urlopen), \
            patch("time.sleep", lambda *_args: None):
        out = lib.llm_call("hello", max_tokens=20, retries=3, timeout=1)

    assert out == "备用模型输出"
    assert len(calls) == 4
    assert calls[:3] == [lib.DEEPSEEK_ENDPOINT] * 3
    assert calls[3] == lib.CLIPROXY_ENDPOINT


def test_non_retryable_primary_error_does_not_fallback():
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", hdrs=None, fp=None)

    with patch.object(lib, "LLM_PROVIDER", "deepseek"), \
            patch.object(lib, "LLM_FALLBACK_PROVIDER", "anthropic"), \
            patch("urllib.request.urlopen", fake_urlopen):
        try:
            lib.llm_call("hello", max_tokens=20, retries=3, timeout=1)
        except lib.LLMNonRetryable:
            pass
        else:
            raise AssertionError("401 must fail fast instead of falling back")

    assert calls == [lib.DEEPSEEK_ENDPOINT]


def test_deepseek_thinking_flag_logic():
    # Fast non-thinking by default; reasoner is fixed-thinking; chat is fixed-fast.
    with patch.object(lib, "DEEPSEEK_THINKING", "disabled"):
        assert lib._deepseek_thinking_on("deepseek-v4-flash") is False
        assert lib._deepseek_thinking_on("deepseek-v4-pro") is False
    with patch.object(lib, "DEEPSEEK_THINKING", "enabled"):
        assert lib._deepseek_thinking_on("deepseek-v4-flash") is True
    assert lib._deepseek_thinking_on("deepseek-reasoner") is True
    assert lib._deepseek_thinking_on("deepseek-chat") is False


def test_v4_request_sends_thinking_disabled():
    captured = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse({"choices": [{"message": {"content": "ok"}}]})

    with patch.object(lib, "LLM_PROVIDER", "deepseek"), \
            patch.object(lib, "DEEPSEEK_MODEL", "deepseek-v4-flash"), \
            patch.object(lib, "DEEPSEEK_THINKING", "disabled"), \
            patch("urllib.request.urlopen", fake_urlopen):
        lib.llm_call("hi", max_tokens=100, retries=1, timeout=60)

    assert captured["body"].get("thinking") == {"type": "disabled"}, captured["body"]
    # Non-thinking must NOT get the 300s reasoning timeout bump.
    assert captured["timeout"] == 60, captured["timeout"]


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)
