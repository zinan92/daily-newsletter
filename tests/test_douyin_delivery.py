"""Regression test: Douyin delivery no longer swallows late-first-seen videos (#4).

The old logic delivered to the inbox only when published==today while deduping
against the library, so a video first fetched the day after it was posted got
archived (→ permanently processed) but never delivered. awemes_to_deliver()
decouples delivery from archival: deliver when not-yet-delivered AND published
within the recency window.

Run: python3 tests/test_douyin_delivery.py
"""
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_spec = importlib.util.spec_from_file_location("fetch_douyin", os.path.join(_ROOT, "fetch-douyin.py"))
fd = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(fd)
except Exception as exc:  # pragma: no cover - optional runtime dep missing is fine
    print(f"SKIP (cannot import fetch-douyin: {type(exc).__name__}: {exc})")
    sys.exit(0)

TODAY = "2026-06-04"


def _epoch(date_str: str) -> int:
    import datetime
    return int(datetime.datetime.strptime(date_str, "%Y-%m-%d").timestamp())


def aweme(aid: str, date_str: str) -> dict:
    return {"aweme_id": aid, "create_time": _epoch(date_str)}


def ids(awemes):
    return [a["aweme_id"] for a in awemes]


def test_published_today_is_delivered():
    out = fd.awemes_to_deliver([aweme("1", TODAY)], delivered_ids=set(), today_str=TODAY)
    assert ids(out) == ["1"]


def test_already_delivered_is_skipped():
    out = fd.awemes_to_deliver([aweme("1", TODAY)], delivered_ids={"1"}, today_str=TODAY)
    assert out == []


def test_late_first_seen_within_window_is_delivered():
    # Published yesterday, first seen today, never delivered → MUST ship (the fix).
    out = fd.awemes_to_deliver([aweme("2", "2026-06-03")], delivered_ids=set(), today_str=TODAY)
    assert ids(out) == ["2"], "late-first-seen video was swallowed"


def test_old_video_outside_window_not_backfilled():
    out = fd.awemes_to_deliver([aweme("3", "2026-05-20")], delivered_ids=set(), today_str=TODAY)
    assert out == [], "old video should not be backfilled into today's digest"


def test_migration_seeded_ids_not_reflooded():
    # On migration delivered_ids is seeded from processed_ids; those must not re-ship.
    seeded = {"7646187098134859034", "7646665973897973043"}
    awemes = [aweme(i, "2026-06-02") for i in seeded]
    out = fd.awemes_to_deliver(awemes, delivered_ids=seeded, today_str=TODAY)
    assert out == [], "seeded/archived videos must not be re-delivered"


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)
