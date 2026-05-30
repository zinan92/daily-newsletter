"""Regression tests for title generation.

Locks gotcha #5/#6: titles must be content-derived, never reused from stale
cross-event templates, and never raw English prose. Structured release/blog
identifiers are left untouched.

These tests avoid the LLM path (item_headline) by using inputs that resolve
deterministically — Chinese titles and structured sources do not call the LLM.

Run: python3 tests/test_titles.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import summarize


def test_has_chinese():
    assert summarize.has_chinese("Opus 4.8 支持对话")
    assert not summarize.has_chinese("With Opus 4.8 you can add system instructions")
    assert not summarize.has_chinese("Claude Code Release v2.1.156")


def test_structured_titles_untouched():
    # Release tags and blog headlines must NOT be regenerated (no LLM call).
    rel = {"source": "claude-code-releases", "title": "Claude Code Release：v2.1.156", "content": "x", "url": "u"}
    blog = {"source": "OpenAI Blog", "title": "Strengthening societal resilience", "content": "x", "url": "u"}
    assert summarize.display_title(rel) == "Claude Code Release：v2.1.156"
    assert "Strengthening societal resilience" in summarize.display_title(blog)


def test_chinese_tweet_title_kept_verbatim():
    # Already-Chinese prose titles are returned as-is (no needless regeneration).
    zh = {"source": "op7418", "title": "我做了一个 AI 工具测评", "content": "x", "url": "u"}
    assert summarize.display_title(zh) == "我做了一个 AI 工具测评"


def test_no_stale_template_map():
    # event_title must NOT intercept event_keys with hardcoded titles. With a
    # Chinese-titled primary (no LLM call), event_title must equal display_title
    # of the primary — proving no template map shadows real content.
    primary = {"source": "Claude Devs X", "title": "Opus 4.8 新增对话中系统指令", "content": "x", "url": "u"}
    event = {"event_key": "anthropic-claude-code-toolchain-update", "primary": primary, "items": [primary, primary]}
    title = summarize.event_title(event)
    assert "Fast Mode" not in title, f"stale template leaked: {title!r}"
    assert title == summarize.display_title(primary), f"unexpected: {title!r}"


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
