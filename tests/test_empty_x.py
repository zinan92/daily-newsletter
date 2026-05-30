"""Regression test for gotcha #24: empty/link-only X items stay out of the body."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import summarize


def test_link_only_x_has_no_content():
    assert not summarize.x_item_has_content({"content": "https://t.co/abc123"})
    assert not summarize.x_item_has_content({"content": ""})


def test_real_tweet_has_content():
    assert summarize.x_item_has_content({"content": "Claude Opus 4.8 发布了新功能"})


def test_empty_single_x_event_renders_nothing():
    primary = {"content": "https://t.co/x", "source": "op7418", "url": "u", "title": "Tweet"}
    event = {"items": [primary], "primary": primary, "event_key": "k"}
    assert summarize.render_summary_event(event) == [], "empty X item must not render"


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1; print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)
