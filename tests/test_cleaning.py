"""Regression tests for reader-facing text cleaning.

These lock gotcha #4: raw source/ingestion metadata (公众号/作者/WeChat ID/
Source/channel/...) must NEVER appear in consumer-facing output. They belong
in the status dashboard only.

Run: python3 -m pytest tests/ -q   (or)   python3 tests/test_cleaning.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from digest_text import consumer_text, sanitize_product_text, strip_source_meta

# Strings that must never survive into reader-facing output.
FORBIDDEN = ("公众号：", "作者：", "WeChat ID", "简介：", "Source:", "channel:", "platform:", "category:", "t.co")

# Real leaked strings observed in processed batches (26-05-27..29).
LEAK_CASES = [
    "Claude 推出 17 个新功能。公众号：深思SenseAI 作者：深思圈 WeChat ID：gh_a54fc6d3826c",
    "作者：dontbesilent聊赚钱。今天讲的是用 AI 赚钱的方法",
    "公众号：新智元 作者：ASI启示录 简介：最新 AI 进展",
    "Source: twitter channel: x platform: web 这是正文内容",
    "引用内容：https://t.co/abc123 转发者补充：值得一看",
]

# Legitimate content that must survive cleaning largely intact.
LEGIT_CASES = [
    "Anthropic 发布 Claude Opus 4.5，编程能力大幅提升。",
    "OpenAI 推出新的 Codex CLI，支持本地沙箱执行。",
    "这次更新让开发者能更快定位问题，减少重复调试。",
]


def test_meta_never_leaks_through_consumer_text():
    for raw in LEAK_CASES:
        out = consumer_text(raw)
        leaked = [m for m in FORBIDDEN if m in out]
        assert not leaked, f"meta leaked {leaked} in: {out!r}"


def test_meta_never_leaks_through_sanitize():
    for raw in LEAK_CASES:
        out = sanitize_product_text(raw)
        leaked = [m for m in FORBIDDEN if m in out]
        assert not leaked, f"meta leaked {leaked} in: {out!r}"


def test_legit_content_survives():
    for raw in LEGIT_CASES:
        out = consumer_text(raw)
        # core content must remain (allow trailing punctuation normalization)
        assert len(out) >= len(raw) * 0.7, f"over-deleted: {raw!r} -> {out!r}"


def test_internal_line_and_handle_names_are_cleaned():
    out = consumer_text("尤其适合面向内容创作的 Line3 类公众号直接推送，作者ai_xiaomu持续输出。")
    assert "Line3" not in out
    assert "Line 3" not in out
    assert "ai_xiaomu" not in out
    assert "黄小木" in out


def test_wechat_reader_chrome_is_cleaned():
    raw = "今年高考，我让12个顶级AI一起考了语文和数学。 Original 数字生命卡兹克 数字生命卡兹克 在小说阅读器读本章 去阅读 在小说阅读器中沉浸阅读 一年一度的高考季又到了。"
    out = consumer_text(raw)
    assert "Original" not in out
    assert "小说阅读器" not in out
    assert "去阅读" not in out
    assert "一年一度的高考季" in out


def test_strip_source_meta_idempotent():
    for raw in LEAK_CASES + LEGIT_CASES:
        once = strip_source_meta(raw)
        twice = strip_source_meta(once)
        assert once == twice, f"not idempotent: {once!r} != {twice!r}"


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
