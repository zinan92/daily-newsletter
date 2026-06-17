"""Regression tests for X timeline fetch state handling.

Run: python3 tests/test_x_timeline_state.py
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ingestion.x import timeline


DAY = "2026-06-12"


def patch_timeline(**replacements):
    old = {name: getattr(timeline, name) for name in replacements}
    for name, value in replacements.items():
        setattr(timeline, name, value)
    return old


def restore_timeline(old):
    for name, value in old.items():
        setattr(timeline, name, value)


def test_x_fetch_saves_state_after_each_handle():
    state = {"twitter:first": {"last_id": "100", "last_fetch": "2026-06-11"}}
    snapshots = []

    def fake_fetch_tweets(handle):
        if handle == "second":
            raise RuntimeError("boom")
        return [
            {
                "id": "100",
                "createdAtLocal": DAY,
                "text": "already seen",
                "author": {"name": "First", "screenName": "first"},
                "metrics": {},
            }
        ]

    old = patch_timeline(
        load_state=lambda: state,
        save_state=lambda data: snapshots.append(copy.deepcopy(data)),
        load_sources=lambda: [
            {"platform": "twitter", "url": "https://x.com/first", "name": "first", "id": "first"},
            {"platform": "twitter", "url": "https://x.com/second", "name": "second", "id": "second"},
        ],
        fetch_tweets=fake_fetch_tweets,
        enrich_tweet=lambda tweet: tweet,
        today=lambda: DAY,
        log=lambda *args, **kwargs: None,
    )
    try:
        timeline.main()
    finally:
        restore_timeline(old)

    assert snapshots, "fetcher should save state before the whole run exits"
    first_saved = snapshots[0].get("twitter:first", {})
    assert first_saved.get("status") == "ok_no_new"
    assert first_saved.get("fetched_count") == 1
    assert first_saved.get("new_count") == 0
    assert snapshots[-1].get("twitter:second", {}).get("status") == "failed"


def test_x_fetch_filters_old_tweets_before_enrichment():
    state = {"twitter:first": {"last_id": "200", "last_fetch": "2026-06-11"}}
    snapshots = []
    enrich_calls = []

    def fake_enrich(tweet):
        enrich_calls.append(tweet["id"])
        return tweet

    old = patch_timeline(
        load_state=lambda: state,
        save_state=lambda data: snapshots.append(copy.deepcopy(data)),
        load_sources=lambda: [
            {"platform": "twitter", "url": "https://x.com/first", "name": "first", "id": "first"},
        ],
        fetch_tweets=lambda handle: [
            {
                "id": "100",
                "createdAtLocal": DAY,
                "text": "already seen today",
                "author": {"name": "First", "screenName": "first"},
                "metrics": {},
            },
            {
                "id": "300",
                "createdAtLocal": "2026-06-11",
                "text": "yesterday",
                "author": {"name": "First", "screenName": "first"},
                "metrics": {},
            },
        ],
        enrich_tweet=fake_enrich,
        today=lambda: DAY,
        log=lambda *args, **kwargs: None,
    )
    try:
        timeline.main()
    finally:
        restore_timeline(old)

    assert enrich_calls == [], "old or non-today tweets must be filtered before article enrichment"
    first_saved = snapshots[-1].get("twitter:first", {})
    assert first_saved.get("status") == "ok_no_new"
    assert first_saved.get("fetched_count") == 2
    assert first_saved.get("new_count") == 0


def test_x_fetch_enriches_only_new_today_tweets():
    state = {"twitter:first": {"last_id": "200", "last_fetch": "2026-06-11"}}
    snapshots = []
    written = []
    enrich_calls = []

    def fake_enrich(tweet):
        enrich_calls.append(tweet["id"])
        enriched = dict(tweet)
        enriched["text"] = "expanded article text"
        return enriched

    old = patch_timeline(
        load_state=lambda: state,
        save_state=lambda data: snapshots.append(copy.deepcopy(data)),
        load_sources=lambda: [
            {"platform": "twitter", "url": "https://x.com/first", "name": "first", "id": "first"},
        ],
        fetch_tweets=lambda handle: [
            {
                "id": "100",
                "createdAtLocal": DAY,
                "text": "already seen today",
                "author": {"name": "First", "screenName": "first"},
                "metrics": {},
            },
            {
                "id": "300",
                "createdAtLocal": DAY,
                "text": "",
                "author": {"name": "First", "screenName": "first"},
                "metrics": {},
            },
        ],
        enrich_tweet=fake_enrich,
        write_source_output=lambda src, items: written.extend(copy.deepcopy(items)),
        today=lambda: DAY,
        log=lambda *args, **kwargs: None,
    )
    try:
        timeline.main()
    finally:
        restore_timeline(old)

    assert enrich_calls == ["300"]
    assert len(written) == 1
    assert written[0]["id"] == "300"
    assert written[0]["text"] == "expanded article text"
    assert snapshots[-1]["twitter:first"]["status"] == "ok_new"


def test_x_fetch_rate_limit_preserves_same_day_success():
    state = {
        "twitter:first": {
            "last_id": "300",
            "last_fetch": DAY,
            "status": "ok_new",
            "fetched_count": 20,
            "new_count": 1,
            "detail": "timeline checked; 1 new item(s) from 20 fetched",
        }
    }
    snapshots = []

    def fake_fetch_tweets(handle):
        raise RuntimeError("twitter-cli exit=1: Rate limited (429), retrying")

    old = patch_timeline(
        load_state=lambda: state,
        save_state=lambda data: snapshots.append(copy.deepcopy(data)),
        load_sources=lambda: [
            {"platform": "twitter", "url": "https://x.com/first", "name": "first", "id": "first"},
        ],
        fetch_tweets=fake_fetch_tweets,
        today=lambda: DAY,
        log=lambda *args, **kwargs: None,
    )
    try:
        timeline.main()
    finally:
        restore_timeline(old)

    saved = snapshots[-1]["twitter:first"]
    assert saved["status"] == "ok_new"
    assert saved["new_count"] == 1
    assert "error" not in saved
    assert "Rate limited" in saved["last_warning"]


if __name__ == "__main__":
    tests = [
        test_x_fetch_saves_state_after_each_handle,
        test_x_fetch_filters_old_tweets_before_enrichment,
        test_x_fetch_enriches_only_new_today_tweets,
        test_x_fetch_rate_limit_preserves_same_day_success,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("\nALL PASS")
