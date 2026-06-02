"""Tests for truthful per-channel health classification.

Encodes the distinction the old status page collapsed:
  - an errored fetch is DOWN, never "成功无新增"
  - a fetch that succeeds against a FROZEN feed is STALE, not QUIET
  - 0-new against a fresh feed is QUIET; n-new is NEW
These are the exact confusions that hid the WeChat bridge outage and the
douyin TimeoutError behind a green dashboard.

Run: python3 tests/test_channel_health.py
"""
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_spec = importlib.util.spec_from_file_location("channel_health", os.path.join(_ROOT, "channel-health.py"))
ch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ch)


def test_parse_error_line():
    p = ch.parse_line("[ts]   柱子哥TzFilm: ERROR TimeoutError: ")
    assert p["error"], "must capture the error"
    assert p["new"] is None


def test_parse_new_counts():
    assert ch.parse_line("[ts]   柱子哥TzFilm: 1 NEW / 51 total") == {"error": None, "new": 1, "seen": 51}
    assert ch.parse_line("[ts]   数字生命卡兹克: 0 NEW / 11 entries") == {"error": None, "new": 0, "seen": 11}
    assert ch.parse_line("[ts]   Claude Blog: 0 NEW articles")["new"] == 0


def test_error_is_down_not_quiet():
    assert ch.classify({"error": "TimeoutError", "new": None, "seen": None}, None) == "DOWN"


def test_frozen_feed_is_stale_not_quiet():
    # 0 new BUT newest feed item is 30 days old → frozen bridge, must NOT read as QUIET
    assert ch.classify({"error": None, "new": 0, "seen": 11}, 30) == "STALE"


def test_zero_new_fresh_is_quiet():
    assert ch.classify({"error": None, "new": 0, "seen": 11}, 1) == "QUIET"
    assert ch.classify({"error": None, "new": 0, "seen": 50}, None) == "QUIET"


def test_new_items_is_new():
    assert ch.classify({"error": None, "new": 2, "seen": 52}, 0) == "NEW"


def test_absent_is_unknown():
    assert ch.classify(None, None) == "UNKNOWN"


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
            n += 1
    print(f"OK — {n} tests passed")
