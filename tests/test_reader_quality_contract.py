"""Phase 4 reader-quality contract tests.

This file is the consolidated regression lock for the GSD Phase 4 success
criteria. Focused tests still cover the details; these assertions keep the
product-level contract visible in one place.

Run: python3 tests/test_reader_quality_contract.py
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import digest_config
import lib
import summarize


def load_quality_check():
    spec = importlib.util.spec_from_file_location("quality_check", ROOT / "quality-check.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


quality_check = load_quality_check()


def test_x_titles_reject_truncated_first_sentence_prefixes():
    cases = [
        (
            "Codex 昨晚上线的这个 Site 插件非",
            "Codex 昨晚上线的这个 Site 插件非常厉害。它本质上感觉类似于 Claude Design。",
        ),
        (
            "长文《想做高级咨询风视觉",
            "长文《想做高级咨询风视觉？这套麦肯锡风格提示词可以直接复制》最近很火。",
        ),
    ]
    for title, body in cases:
        assert summarize.x_title_looks_truncated(title, body), title


def test_media_requires_transcript_backed_non_promo_summary():
    no_transcript = {
        "title": "Team thinking, visualized by Claude",
        "status": "no_transcript",
        "error": "audio transcript too short: 149 chars",
        "summary": None,
        "bullets": None,
    }
    promo = {
        "title": "It's time to fly | Codex",
        "status": "summarized",
        "summary": "OpenAI Codex 宣传片以火箭发射倒计时为隐喻，展现用自然语言命令即可让 AI 实时编写代码。",
        "bullets": ["视频通过类比传递体验。"],
    }
    deep = {
        "title": "Dwarkesh × Researcher: scaling laws",
        "status": "summarized",
        "summary": "访谈深入讨论了模型迭代速度如何决定能力提升，并解释了数据修复比新算法更关键的原因。",
        "bullets": ["团队迭代速度是模型进步的核心驱动。", "训练流程中的 BUG 修复带来质量提升。"],
    }

    assert not summarize.media_record_is_publishable(no_transcript)
    assert not summarize.media_record_is_publishable(promo)
    assert summarize.media_record_is_publishable(deep)


def test_active_douyin_sources_are_loaded_from_source_config():
    original_loader = lib.load_sources
    original_cache = digest_config._ACTIVE_DOUYIN_CACHE

    def fake_load_sources():
        return [
            {"platform": "douyin", "active": "true", "name": "柱子哥TzFilm"},
            {"platform": "douyin", "active": "false", "name": "已停用抖音源"},
            {"platform": "wechat", "active": "true", "name": "不是抖音源"},
        ]

    try:
        lib.load_sources = fake_load_sources
        digest_config._ACTIVE_DOUYIN_CACHE = None
        active = digest_config.active_douyin_source_names()
        douyin_group = digest_config.source_names_for_group("douyin")
    finally:
        lib.load_sources = original_loader
        digest_config._ACTIVE_DOUYIN_CACHE = original_cache

    assert "柱子哥TzFilm" in active
    assert "柱子哥TzFilm" in douyin_group
    assert "已停用抖音源" not in active
    assert "不是抖音源" not in active


def test_visible_product_gate_covers_reader_quality_leaks():
    assert "no_transcript" in quality_check.BAD_PATTERNS
    assert "转录失败" in quality_check.BAD_PATTERNS
    assert "一位博主" in quality_check.BAD_PATTERNS
    assert "公众号：" in quality_check.BAD_PATTERNS
    assert "source_name" in quality_check.METADATA_PATTERNS
    assert quality_check.raw_english_body_lines(
        "This line is raw English prose from an unrevised source.\n"
        "这行中文读者正文是可以的。"
    )


def test_markdown_html_heading_divergence_is_detected():
    visible_md = "## 今日精选\n\n### 厂商动态\n\n##### 新模型上线\n"
    visible_html = "<h2>今日精选</h2><h3>厂商动态</h3>"
    assert quality_check.heading_divergence(visible_md, visible_html) == ["新模型上线"]


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
