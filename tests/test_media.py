"""Regression tests: only deep media reaches the consumer body (gotcha #3).

A video enters the media section ONLY with a publishable deep summary. Two real
records observed 2026-06-04 must be excluded:
  - "Team thinking, visualized by Claude" — status=no_transcript, no summary.
  - "It's time to fly | Codex" — has a summary, but it is a 宣传片 (brand promo).
A genuine deep-interview summary must still pass.

Run: python3 tests/test_media.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import summarize


def test_no_transcript_record_excluded():
    rec = {"title": "Team thinking, visualized by Claude", "status": "no_transcript",
           "error": "audio transcript too short: 149 chars", "summary": None, "bullets": None}
    assert not summarize.media_record_is_publishable(rec)


def test_promo_summary_excluded():
    rec = {
        "title": "It's time to fly | Codex",
        "status": "summarized",
        "summary": "OpenAI Codex 宣传片以火箭发射倒计时为隐喻，展现用自然语言命令即可让 AI 实时编写代码。",
        "bullets": ["视频通过类比传递体验。"],
    }
    assert not summarize.media_record_is_publishable(rec)


def test_deep_summary_published():
    rec = {
        "title": "Dwarkesh × Researcher: scaling laws",
        "status": "summarized",
        "summary": "访谈深入讨论了模型迭代速度如何决定能力提升，并解释了数据修复比新算法更关键的原因。",
        "bullets": ["团队迭代速度是模型进步的核心驱动。", "训练流程中的 BUG 修复带来质量提升。"],
    }
    assert summarize.media_record_is_publishable(rec)


def test_media_panel_drops_unsummarized(monkeypatch=None):
    # An item whose record has no publishable summary must not appear (no bare link).
    summaries = {
        "https://www.youtube.com/watch?v=8N1-XHNupfg": {
            "title": "Team thinking, visualized by Claude", "status": "no_transcript",
            "summary": None, "bullets": None,
        },
    }
    src = {
        "file": type("P", (), {"name": "x.md", "stem": "x"})(),
        "fm": {"source_name": "Claude YouTube"},
        "items": [{"source": "Claude YouTube", "url": "https://www.youtube.com/watch?v=8N1-XHNupfg",
                   "title": "Team thinking, visualized by Claude", "content": "x"}],
        "kept": [{"source": "Claude YouTube", "url": "https://www.youtube.com/watch?v=8N1-XHNupfg",
                  "title": "Team thinking, visualized by Claude", "content": "x"}],
        "filtered": [],
    }
    items, _total, _filtered = summarize.media_panel_items([src], summaries)
    assert items == [], f"unsummarized media leaked into body: {items}"


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
