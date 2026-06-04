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
