"""Regression tests for unified Daily Inbox run report.

Run: python3 tests/test_run_report.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_report


TODAY = "2026-06-06"


def _temp_json(obj):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return Path(path)


def test_report_surfaces_media_failure_without_raw_traceback():
    original_media = run_report.MEDIA_SUMMARIES_PATH
    try:
        run_report.MEDIA_SUMMARIES_PATH = _temp_json(
            {
                "u1": {
                    "status": "failed",
                    "source": "OpenAI YouTube",
                    "title": "What Codex Unlocks for Zapier",
                    "url": "https://youtube.com/watch?v=demo",
                    "updated_at": f"{TODAY}T09:00:00",
                    "error": "RuntimeError: [cookies-file:youtube-cookies.txt]\nERROR: [youtube] Sign in to confirm",
                }
            }
        )
        sources = [{"items": [{"url": "u"}], "kept": [{"url": "u"}], "filtered": []}]
        health = [{"name": "OpenAI YouTube", "status": "ok_new", "platform": "rss"}]
        report = run_report.build_run_report(sources, health, TODAY, "20260606")
        lines = "\n".join(run_report.compact_digest_health_lines(report))
        assert "音视频转录异常 **1** 条" in lines
        assert "OpenAI YouTube" in lines
        assert "RuntimeError" not in lines
        assert "cookies-file" not in lines
        problems = "\n".join(run_report.problem_lines(report))
        assert "What Codex Unlocks for Zapier" in problems
        assert "YouTube cookie/登录态可能失效" in problems
    finally:
        try:
            run_report.MEDIA_SUMMARIES_PATH.unlink()
        except OSError:
            pass
        run_report.MEDIA_SUMMARIES_PATH = original_media


def test_report_counts_source_and_batch_totals():
    original_media = run_report.MEDIA_SUMMARIES_PATH
    try:
        run_report.MEDIA_SUMMARIES_PATH = _temp_json({})
        sources = [
            {"items": [{"url": "1"}, {"url": "2"}], "kept": [{"url": "1"}], "filtered": [{"url": "2"}]},
        ]
        health = [
            {"name": "Anthropic News", "status": "ok_new", "platform": "rss"},
            {"name": "海外独角兽", "status": "stale", "platform": "wechat", "detail": "上游 feed 冻结"},
        ]
        report = run_report.build_run_report(sources, health, TODAY, "20260606")
        assert report["totals"]["items"] == 2
        assert report["totals"]["kept"] == 1
        assert report["totals"]["filtered"] == 1
        assert report["health"]["needs_attention"] == 1
        text = "\n".join(run_report.compact_digest_health_lines(report))
        assert "健康渠道 **1**" in text
        assert "海外独角兽" in text
    finally:
        try:
            run_report.MEDIA_SUMMARIES_PATH.unlink()
        except OSError:
            pass
        run_report.MEDIA_SUMMARIES_PATH = original_media


def test_report_backfills_five_stage_artifact_funnel(tmp_path):
    original_processed = run_report.processed_batch_dir
    original_sent = run_report.SENT_DIR
    original_media = run_report.MEDIA_SUMMARIES_PATH
    try:
        batch_dir = tmp_path / "processed" / "26-06-06"
        ai = batch_dir / "ai"
        ai.mkdir(parents=True)
        (ai / "00-input-items.json").write_text(json.dumps([{"id": "1"}, {"id": "2"}]), encoding="utf-8")
        (ai / "01-item-cards.json").write_text(json.dumps([{"id": "1"}, {"id": "2"}]), encoding="utf-8")
        (ai / "02-events.json").write_text(json.dumps([{"event_id": "e1"}]), encoding="utf-8")
        (ai / "03-selection.json").write_text(
            json.dumps({"brief_universe": [{"event_id": "e1"}], "deep_candidates": [], "discard": [{"event_id": "e2"}]}),
            encoding="utf-8",
        )
        (batch_dir / "coarse-rejects.jsonl").write_text("{}\n{}\n", encoding="utf-8")
        (batch_dir / "source").mkdir()
        (batch_dir / "source" / "item.md").write_text("# Item\n", encoding="utf-8")
        sent = tmp_path / "sent"
        sent.mkdir()
        (sent / "26-06-06.md").write_text("- **A**\n", encoding="utf-8")
        (sent / "product-radar-26-06-06.md").write_text("### 1. A\n", encoding="utf-8")
        run_report.SENT_DIR = sent
        run_report.processed_batch_dir = lambda batch=None: batch_dir
        run_report.MEDIA_SUMMARIES_PATH = _temp_json({})

        report = run_report.build_run_report([], [], TODAY, "20260606")

        assert report["totals"]["items"] == 4
        assert report["totals"]["kept"] == 1
        assert report["totals"]["filtered"] == 3
        assert report["totals"]["coarse_rejects"] == 2
        assert report["totals"]["events"] == 1
        assert report["funnel"]["reader_products"]["product_radar"]["items"] == 1
    finally:
        try:
            run_report.MEDIA_SUMMARIES_PATH.unlink()
        except OSError:
            pass
        run_report.processed_batch_dir = original_processed
        run_report.SENT_DIR = original_sent
        run_report.MEDIA_SUMMARIES_PATH = original_media


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
