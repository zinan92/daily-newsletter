"""Regression tests for the Chinese-only fallback (gotcha #5).

When the LLM rewrite is unavailable or returns non-Chinese, the consumer body
must NOT show raw English. The deterministic fallbacks suppress English source
text (the content-derived Chinese title + link carry the item) but keep
already-Chinese source text.

These tests hit only deterministic paths (no LLM).

Run: python3 tests/test_chinese_fallback.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import summarize


def test_english_source_item_suppressed():
    item = {"source": "Claude Devs X", "title": "x",
            "content": "To learn more, see our docs on automatic-caching and system prompts", "url": "u"}
    assert summarize.source_item_paragraph(item) == "", "raw English must be suppressed"


def test_chinese_source_item_kept():
    item = {"source": "op7418", "title": "x", "content": "这是一条中文内容，值得展示。", "url": "u"}
    out = summarize.source_item_paragraph(item)
    assert "中文内容" in out, f"Chinese content must survive: {out!r}"


def test_english_event_summary_suppressed():
    primary = {"source": "Claude Devs X", "title": "x", "content": "Only English here, no docs link", "url": "u"}
    event = {"primary": primary, "items": [primary]}
    assert summarize.source_event_summary(event) == "", "English event bodies must be suppressed"


def test_chinese_event_summary_kept():
    primary = {"source": "op7418", "title": "x", "content": "中文事件正文内容。", "url": "u"}
    event = {"primary": primary, "items": [primary]}
    out = summarize.source_event_summary(event)
    assert "中文事件" in out, f"Chinese event body must survive: {out!r}"


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
