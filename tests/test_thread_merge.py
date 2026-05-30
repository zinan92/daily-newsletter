"""Regression tests for X thread merging (gotcha #9 / #10).

Tweets sharing a conversation_id (a thread: parent + replies) merge into one
event. Standalone tweets keep their own event_key, so cross-source keyword
merges are not affected. conversation_id survives the markdown write->parse
round-trip.

Run: python3 tests/test_thread_merge.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lib
import digest_events as de


def test_same_thread_merges():
    items = [
        {"url": "x/100", "conversation_id": "100", "title": "root", "score": 5, "source": "Claude Devs X"},
        {"url": "x/101", "conversation_id": "100", "title": "reply1", "score": 3, "source": "Claude Devs X"},
        {"url": "x/102", "conversation_id": "100", "title": "reply2", "score": 3, "source": "Claude Devs X"},
    ]
    events = de.build_events(items, limit=None)
    assert len(events) == 1, f"thread should be one event, got {len(events)}"
    assert events[0]["event_key"] == "thread:100"
    assert len(events[0]["items"]) == 3


def test_standalone_tweets_stay_separate():
    items = [
        {"url": "x/200", "conversation_id": "200", "title": "A", "score": 4, "source": "op7418"},
        {"url": "x/300", "conversation_id": "300", "title": "B", "score": 4, "source": "vista8"},
    ]
    events = de.build_events(items, limit=None)
    assert len(events) == 2, "distinct standalone tweets must not merge"


def test_single_thread_member_not_thread_keyed():
    # Only one tweet of a conversation present → not forced into a thread bucket;
    # it follows the normal event_key path (so cross-source merge still possible).
    items = [{"url": "x/100", "conversation_id": "100", "title": "solo", "score": 4, "source": "op7418"}]
    events = de.build_events(items, limit=None)
    assert events[0]["event_key"] != "thread:100"


def test_conversation_id_round_trip():
    item = {
        "title": "Test", "text": "hello", "url": "https://x.com/a/status/101",
        "source": "Claude Devs X", "author": "Claude Devs", "handle": "ClaudeDevs",
        "likes": 5, "rts": 2, "conversation_id": "100",
    }
    parsed = lib.parse_md_items(lib._twitter_item_md(item))
    assert parsed[0].get("conversation_id") == "100", "conversation_id lost in round-trip"


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
