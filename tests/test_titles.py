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
from digest_text import one_line


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


def test_x_truncated_titles_detected():
    # Real chopped X titles observed in the 26-06-04 batch (gotcha #2). Each is
    # the body's opening cut mid-thought; the guard must flag all three.
    cases = [
        ("果然做过的人的分享就是不一样，Late",
         "果然做过的人的分享就是不一样，Laten Space 访谈了 Ethan He，罗列一些观点"),
        ("长文《想做高级咨询风视觉",
         "长文《想做高级咨询风视觉？这套麦肯锡风格提示词可以直接复制》最近"),
        ("Codex 昨晚上线的这个 Site 插件非",
         "Codex 昨晚上线的这个 Site 插件非常厉害。它本质上感觉类似于 Claude Design"),
    ]
    for title, body in cases:
        assert summarize.x_title_looks_truncated(title, body), f"missed truncation: {title!r}"


def test_x_legit_titles_kept():
    # A complete author-led heading (terminal punctuation, balanced brackets)
    # must NOT be flagged, even when the body opens with it (龙德宸-style).
    assert not summarize.x_title_looks_truncated(
        "我做了一个 AI 工具测评", "x"
    )  # body does not repeat the title
    assert not summarize.x_title_looks_truncated(
        "今天发布了新版本。", "今天发布了新版本。详情如下：支持多模态"
    )  # complete sentence title-led post
    assert not summarize.x_title_looks_truncated(
        "《麦肯锡风格提示词》上线", "《麦肯锡风格提示词》上线，欢迎体验"
    )  # balanced brackets, title is its own complete clause
    # A stray bracket in a title the body does NOT begin with is the author's own
    # heading — must not be flagged just for the bracket (codex review fix).
    assert not summarize.x_title_looks_truncated(
        "我用 Cursor (实验) 做了个工具", "完全不同的正文开头，讲别的事情"
    )


def test_no_stale_template_map():
    # event_title must NOT intercept event_keys with hardcoded titles. With a
    # Chinese-titled primary (no LLM call), event_title must equal display_title
    # of the primary — proving no template map shadows real content.
    primary = {"source": "Claude Devs X", "title": "Opus 4.8 新增对话中系统指令", "content": "x", "url": "u"}
    event = {"event_key": "anthropic-claude-code-toolchain-update", "primary": primary, "items": [primary, primary]}
    title = summarize.event_title(event)
    assert "Fast Mode" not in title, f"stale template leaked: {title!r}"
    assert title == summarize.display_title(primary), f"unexpected: {title!r}"


def test_one_line_does_not_fabricate_single_letter_sentence_endings():
    text = "一人公司创始人开发了一款多 AI 语音 Agent 系统，系统基于本地部署的 ASR 和 Codex SDK 构建，支持任务调度和进度查看。"
    out = one_line(text, limit=46)
    assert "的A。" not in out
    assert not out.endswith("A。")


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
