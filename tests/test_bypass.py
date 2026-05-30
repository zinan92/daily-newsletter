"""Regression tests for score-bypass (gotcha #1/#2/#3/#21).

When the scoring service is down (502), curated inputs get score=0. They must
still appear: official channels, code releases, key people, media, user-saved,
and WeChat bypass the score threshold. Only ordinary feed items are gated.

This is the exact failure that suppressed official content during an outage.

Run: python3 tests/test_bypass.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import summarize
from digest_config import source_names_for_group

OUTAGE = 0  # score assigned to unscored items during a 502


def _one(group):
    return sorted(source_names_for_group(group))[0]


def test_official_survives_outage():
    item = {"source": _one("official"), "score": OUTAGE}
    assert summarize.bypasses_score(item), "official must bypass score on outage"


def test_code_release_survives_outage():
    item = {"source": _one("code"), "score": OUTAGE}
    assert summarize.bypasses_score(item)


def test_key_people_survive_outage():
    item = {"source": _one("people"), "score": OUTAGE}
    assert summarize.bypasses_score(item)


def test_saved_survives_outage():
    item = {"source": _one("saved"), "score": OUTAGE}
    assert summarize.bypasses_score(item)


def test_media_platform_survives_outage():
    # douyin/wechat platform items bypass regardless of source name
    assert summarize.bypasses_score({"source": "x", "score": OUTAGE}, platform="douyin")
    assert summarize.bypasses_score({"source": "x", "score": OUTAGE}, platform="wechat")


def test_video_category_survives_outage():
    assert summarize.bypasses_score({"source": "x", "score": OUTAGE, "category": "video-podcast"})


def test_ordinary_feed_is_gated():
    # An ordinary X account not in any curated group must NOT bypass — it is
    # correctly score-gated (and would be dropped on a 502, by design).
    item = {"source": "some-random-x-account", "score": OUTAGE}
    assert not summarize.bypasses_score(item), "ordinary feed must remain score-gated"


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
