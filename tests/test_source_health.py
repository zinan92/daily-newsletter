"""Regression test for the WeChat RSS bridge false-green (gotcha #23).

When fetch-wechat-rss errors (bridge down → [Errno 61] Connection refused), it
records status='failed' + error in state but STILL stamps last_fetch=today.
source-health must therefore report 'failed' — not 'ok' — or the bridge-down
alert never fires and 公众号 silently stops updating while the dashboard is green.

This is the exact failure observed 2026-06-02 (bridge container down overnight,
3/4 runs Connection refused, yet health showed wechat 8/8 ok).

Run: python3 tests/test_source_health.py
"""
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)  # so source-health.py's `from lib import ...` resolves
_SH_PATH = os.path.join(_ROOT, "source-health.py")
_spec = importlib.util.spec_from_file_location("source_health", _SH_PATH)
sh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sh)

DAY = "2026-06-02"
WECHAT = {
    "name": "数字生命卡兹克",
    "platform": "wechat",
    "notes": "rss_url http://localhost:4000/feeds/MP_WXS_3223096120.json",
    "url": "https://mp.weixin.qq.com/s/vTv0Vu4RgrMkmLbXGvnSug",
}

TWITTER = {
    "name": "dontbesilent",
    "platform": "twitter",
    "notes": "",
    "url": "https://x.com/dontbesilent",
}


def test_bridge_connection_refused_is_failed():
    """Ran today but the fetcher recorded a connection error → must be 'failed'."""
    st = {
        "last_fetch": DAY,
        "status": "failed",
        "error": "URLError: <urlopen error [Errno 61] Connection refused>",
    }
    status, detail = sh.classify_source(WECHAT, st, DAY)
    assert status == "failed", f"bridge-down must be 'failed', got '{status}'"
    assert "Connection refused" in detail, f"detail should surface the error, got: {detail}"


def test_bridge_ok_when_imported_cleanly():
    """Ran today, no error recorded → 'ok'."""
    st = {"last_fetch": DAY, "status": "ok", "entries": 11, "imported": 2}
    status, _ = sh.classify_source(WECHAT, st, DAY)
    assert status == "ok", f"clean fetch must be 'ok', got '{status}'"


def test_no_fetch_today_is_failed():
    """Stale last_fetch → 'failed'."""
    st = {"last_fetch": "2026-05-01", "status": "ok"}
    status, _ = sh.classify_source(WECHAT, st, DAY)
    assert status == "failed", f"no fetch today must be 'failed', got '{status}'"


def test_twitter_checked_no_new_is_ok_no_new():
    st = {
        "last_fetch": DAY,
        "status": "ok_no_new",
        "fetched_count": 20,
        "new_count": 0,
        "detail": "timeline checked; 0 new item(s) from 20 fetched",
    }
    status, detail = sh.classify_source(TWITTER, st, DAY)
    assert status == "ok_no_new", f"checked empty X timeline must be ok_no_new, got '{status}'"
    assert "0 new" in detail


def test_twitter_timeout_not_checked_is_distinct_from_failed():
    old_latest_timeout = sh.latest_timeout
    try:
        sh.latest_timeout = lambda component, day: f"[{day}T00:00:00] !!! fetch-twitter.py timeout after 180s"
        status, detail = sh.classify_source(TWITTER, {"last_fetch": "2026-05-01"}, DAY)
    finally:
        sh.latest_timeout = old_latest_timeout
    assert status == "not_checked_due_timeout", f"timeout-skipped X source must be distinct, got '{status}'"
    assert "timed out" in detail


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
            n += 1
    print(f"OK — {n} tests passed")
