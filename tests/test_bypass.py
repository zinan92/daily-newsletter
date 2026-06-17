"""Regression tests for unified score gating.

Every source type must be scored before entering the reader product. Source
identity can inform the score reason, but it must not bypass scoring.

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
    assert not summarize.bypasses_score(item), "official must be score-gated"


def test_code_release_survives_outage():
    item = {"source": _one("code"), "score": OUTAGE}
    assert not summarize.bypasses_score(item)


def test_key_people_survive_outage():
    item = {"source": _one("people"), "score": OUTAGE}
    assert not summarize.bypasses_score(item)


def test_saved_survives_outage():
    item = {"source": _one("saved"), "score": OUTAGE}
    assert not summarize.bypasses_score(item)


def test_media_platform_survives_outage():
    assert not summarize.bypasses_score({"source": "x", "score": OUTAGE}, platform="douyin")


def test_auto_wechat_rss_is_score_gated():
    assert not summarize.bypasses_score(
        {"source": "数字生命卡兹克", "score": OUTAGE, "category": "wechat-ai"},
        platform="wechat",
    )


def test_manual_wechat_link_survives_outage():
    assert not summarize.bypasses_score(
        {"source": "手动公众号文章", "score": OUTAGE, "category": "wechat-manual"},
        platform="wechat",
    )


def test_video_category_survives_outage():
    assert not summarize.bypasses_score({"source": "x", "score": OUTAGE, "category": "video-podcast"})


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
