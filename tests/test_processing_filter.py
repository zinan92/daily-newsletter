"""Regression tests for the unprocessed -> processed low-value filter.

Run: python3 tests/test_processing_filter.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import processing_filter


def item(title: str, content: str, source: str = "普通 X") -> dict:
    return {
        "title": title,
        "content": content,
        "source": source,
        "url": f"https://x.com/example/status/{abs(hash(title))}",
        "meta": f"source: {source} · [link](https://x.com/example/status/{abs(hash(title))})",
    }


def test_low_value_consumer_chatter_is_rejected():
    keep, reason = processing_filter.should_keep_item(
        {"platform": "twitter", "category": "ai-personal"},
        item("上 iPhone 17 还是等 iPhone 18", "上 iPhone 17 还是等 iPhone 18，这个选择太纠结了。"),
    )
    assert not keep
    assert reason == "consumer_chatter"


def test_low_value_life_philosophy_is_rejected():
    keep, reason = processing_filter.should_keep_item(
        {"platform": "twitter", "category": "ai-personal"},
        item("主线任务", "你要找到自己的人生主线任务，否则痛苦会一直跟着你。"),
    )
    assert not keep
    assert reason == "life_philosophy"


def test_official_and_key_people_are_protected_before_scoring():
    for source in ["Claude X", "Dario Amodei", "Sam Altman"]:
        keep, reason = processing_filter.should_keep_item(
            {"platform": "twitter", "category": "ai-official", "source_name": source},
            item("短更新", "发布了。", source),
        )
        assert keep
        assert reason == "protected_source"


def test_domain_signal_is_kept_for_scoring():
    keep, reason = processing_filter.should_keep_item(
        {"platform": "twitter", "category": "ai-personal"},
        item("Fable 5 实战", "Fable 5 调试两轮做出 RSS 阅读器，适合评估 AI 编程模型和工作流集成。"),
    )
    assert keep
    assert reason == "kept"


def test_consumer_chatter_iphone_regex_path_is_rejected():
    # Regression: the `iPhone\\s*17` alternative was double-escaped (`\\\\s`),
    # so a space-separated "iPhone 17" only got caught by the literal `上/等`
    # alternatives. This case has no 上/等 prefix and >90 chars (so the length
    # gate cannot fire), proving the regex alternative itself now matches.
    keep, reason = processing_filter.should_keep_item(
        {"platform": "twitter", "category": "ai-personal"},
        item(
            "iPhone 17 拍照续航闲聊",
            "聊聊 iPhone 17 这次的拍照和续航，整体体验比上代提升了一些，但价格确实不便宜，"
            "纠结了好久到底要不要换，身边朋友有的说值有的说不值，真的拿不定主意啊到底买不买呢",
        ),
    )
    assert not keep
    assert reason == "consumer_chatter"


def test_bare_url_noise_is_dropped_after_url_strip():
    # Regression: compact_content_without_urls used `\\\\S`/`\\\\s` (double-escaped),
    # so URLs were never stripped and a bare-link post stayed long enough to slip
    # past the length gates. After the fix the URL is stripped and the post is
    # correctly rejected as too short / no domain signal.
    keep, reason = processing_filter.should_keep_item(
        {"platform": "twitter", "category": "ai-personal"},
        {
            "title": "看",
            "content": "看 https://example.com/some/very/long/path/that/used/to/inflate/length/aaaaaaaaaaaaaaaaaaaa",
            "source": "普通 X",
            "url": "https://x.com/a/1",
            "meta": "source: 普通 X · [link](https://x.com/a/1)",
        },
    )
    assert not keep
    assert reason in {"too_short_without_domain_signal", "no_domain_signal_short_social_post"}


def test_filter_markdown_items_rewrites_file_with_only_kept_items():
    body = """## 上 iPhone 17 还是等 iPhone 18
source: 普通 X · [link](https://x.com/a/status/1)

上 iPhone 17 还是等 iPhone 18，这个选择太纠结了。

## Fable 5 实战
source: 普通 X · [link](https://x.com/a/status/2)

Fable 5 调试两轮做出 RSS 阅读器，适合评估 AI 编程模型和工作流集成。
"""
    fm = {"platform": "twitter", "category": "ai-personal", "source_name": "普通 X"}
    replacement, rejected = processing_filter.filter_markdown_items(body, fm, Path("sample.md"))
    assert replacement is not None
    assert "Fable 5 实战" in replacement
    assert "上 iPhone 17" not in replacement
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "consumer_chatter"


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
