"""Regression test: the digest top carries a compact channel-health banner (#1).

It is derived from source_health() rows, stays a few lines, and names the
sources that need attention (failed / stale). Pure render — no LLM, no network.

Run: python3 tests/test_health_dashboard.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import summarize


ROWS = [
    {"name": "Anthropic News", "status": "ok_new"},
    {"name": "OpenAI Blog", "status": "ok_no_new"},
    {"name": "vista8", "status": "filtered_out"},
    {"name": "数字生命卡兹克", "status": "failed"},
    {"name": "Dwarkesh Podcast", "status": "stale"},
    {"name": "ChatGPT X", "status": "not_configured"},  # excluded from counts
]


def test_dashboard_is_compact():
    lines = summarize.render_health_dashboard_md(ROWS)
    nonblank = [ln for ln in lines if ln.strip()]
    assert "## 渠道概览" in lines
    assert len(nonblank) <= 5, f"dashboard too long: {nonblank}"


def test_dashboard_counts_and_failures():
    lines = summarize.render_health_dashboard_md(ROWS)
    text = "\n".join(lines)
    assert "健康渠道 **3**" in text, text       # ok_new + ok_no_new + filtered_out
    assert "今日有新增 **1**" in text, text       # only ok_new
    assert "需关注 **2**" in text, text           # failed + stale
    assert "数字生命卡兹克" in text and "Dwarkesh Podcast" in text
    assert "ChatGPT X" not in text                # not_configured is not a failure


def test_dashboard_all_green():
    lines = summarize.render_health_dashboard_md([{"name": "x", "status": "ok_new"}])
    assert any("所有自动渠道今日抓取正常" in ln for ln in lines)


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
