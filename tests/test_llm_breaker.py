"""The primary provider must be skipped once it is clearly down.

2026-09-22: Codex hung for two hours and every call waited the full 240s
timeout before failing over — 30 times in a row.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lib


def _patch(monkeypatch, *, primary="codex", fallback="deepseek", failures=2, reprobe=15):
    monkeypatch.setattr(lib, "LLM_PROVIDER", primary)
    monkeypatch.setattr(lib, "LLM_FALLBACK_PROVIDER", fallback)
    monkeypatch.setattr(lib, "BREAKER_FAILURES", failures)
    monkeypatch.setattr(lib, "BREAKER_REPROBE_EVERY", reprobe)
    lib.reset_llm_breaker()
    calls = []

    def fake(provider, prompt, max_tokens, *, retries=3, timeout=120):
        calls.append(provider)
        if provider == primary and getattr(fake, "primary_down", True):
            raise lib.LLMUnavailable("codex CLI timed out after 240 seconds")
        return f"ok:{provider}"

    monkeypatch.setattr(lib, "_llm_call_provider", fake)
    return calls, fake


def test_breaker_stops_paying_the_timeout_after_two_failures(monkeypatch):
    calls, _ = _patch(monkeypatch)
    for _ in range(10):
        assert lib.llm_call("x") == "ok:deepseek"
    # the primary is tried for the first two calls only, then skipped
    assert calls.count("codex") == 2, calls
    assert calls.count("deepseek") == 10


def test_breaker_reprobes_and_returns_to_the_primary_when_it_recovers(monkeypatch):
    calls, fake = _patch(monkeypatch, reprobe=3)
    for _ in range(3):
        lib.llm_call("x")           # 2 failures trip the breaker, 3rd is skipped
    fake.primary_down = False       # Codex recovers, as it did at chunk 31
    outs = [lib.llm_call("x") for _ in range(6)]
    assert "ok:codex" in outs, calls
    # once healthy again every call goes back to the primary
    assert outs[-1] == "ok:codex"


def test_success_resets_the_counter(monkeypatch):
    calls, fake = _patch(monkeypatch)
    lib.llm_call("x")               # failure 1
    fake.primary_down = False
    assert lib.llm_call("x") == "ok:codex"   # success resets
    fake.primary_down = True
    lib.llm_call("x")               # failure 1 again, breaker must NOT be open
    assert calls.count("codex") == 3, calls


def test_config_errors_never_trip_the_breaker(monkeypatch):
    calls, _ = _patch(monkeypatch)

    def bad(provider, prompt, max_tokens, *, retries=3, timeout=120):
        calls.append(provider)
        raise lib.LLMNonRetryable("bad key")

    monkeypatch.setattr(lib, "_llm_call_provider", bad)
    for _ in range(3):
        try:
            lib.llm_call("x")
        except lib.LLMNonRetryable:
            pass
    # surfaced every time; never silently routed to the fallback
    assert calls == ["codex", "codex", "codex"]


def test_no_fallback_configured_keeps_using_the_primary(monkeypatch):
    calls, _ = _patch(monkeypatch, fallback="none")
    for _ in range(3):
        try:
            lib.llm_call("x")
        except lib.LLMUnavailable:
            pass
    assert calls == ["codex", "codex", "codex"]
