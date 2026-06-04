"""Regression tests for proactive failure alerting + transcription retry.

The owner must be told about ANY failure (no silent degradation):
  - a curated video that failed to transcribe today,
  - an LLM scoring outage,
  - a transient transcription failure must be retried (not stick forever).

Run: python3 tests/test_alerts.py
"""
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_ROOT, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ph = _load("ph_alerts", "check-pipeline-health.py")
fmt = _load("fmt_alerts", "fetch-media-transcripts.py")
TODAY = datetime.now().date().isoformat()


def _write_json(obj):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return path


def test_failed_transcription_today_alerts():
    ph.MEDIA_SUMMARIES = __import__("pathlib").Path(_write_json({
        "u1": {"status": "failed", "title": "柱子哥视频", "source": "柱子哥TzFilm",
               "error": "ReadTimeout: ", "updated_at": f"{TODAY}T10:00:00"},
        "u2": {"status": "summarized", "title": "ok", "source": "x", "updated_at": f"{TODAY}T10:00:00"},
        "u3": {"status": "no_transcript", "title": "short", "source": "y", "updated_at": f"{TODAY}T10:00:00"},
    }))
    out = ph.failed_transcriptions()
    assert len(out) == 1 and "柱子哥" in out[0], out


def test_old_failure_not_realerted():
    old = (datetime.now() - timedelta(days=2)).isoformat()
    ph.MEDIA_SUMMARIES = __import__("pathlib").Path(_write_json({
        "u1": {"status": "failed", "title": "old", "source": "z", "updated_at": old},
    }))
    assert ph.failed_transcriptions() == []


def test_scoring_outage_flagged():
    ph.SCORING_HEALTH = __import__("pathlib").Path(_write_json(
        {"date": TODAY, "status": "degraded", "failed_batches": 3}))
    assert ph.scoring_outage() is not None
    ph.SCORING_HEALTH = __import__("pathlib").Path(_write_json(
        {"date": TODAY, "status": "ok", "failed_batches": 0}))
    assert ph.scoring_outage() is None


def test_transient_failure_is_retryable():
    # A status=='failed' record within the window is re-surfaced for retry.
    cache = {"https://www.douyin.com/video/123": {
        "status": "failed", "title": "t", "source": "柱子哥TzFilm",
        "updated_at": f"{TODAY}T10:00:00"}}
    items = fmt.retryable_failed_items(cache)
    assert [i["url"] for i in items] == ["https://www.douyin.com/video/123"]
    # A settled 'no_transcript' is NOT retried.
    cache2 = {"u": {"status": "no_transcript", "updated_at": f"{TODAY}T10:00:00"}}
    assert fmt.retryable_failed_items(cache2) == []


def test_write_health_alert_local_file():
    import lib
    import pathlib
    fd, path = tempfile.mkstemp(suffix=".md")
    os.close(fd)
    orig = lib.HEALTH_ALERTS_PATH
    try:
        lib.HEALTH_ALERTS_PATH = pathlib.Path(path)
        assert lib.write_health_alert("⚠️ 1 个问题", ["Ray在思考（feed 冻结）"]) is True
        assert lib.write_health_alert("✅ 一切正常") is True
        text = pathlib.Path(path).read_text(encoding="utf-8")
        # newest entry is on top
        assert text.index("✅ 一切正常") < text.index("Ray在思考"), text
        assert "# Park-IO 健康告警" in text
    finally:
        lib.HEALTH_ALERTS_PATH = orig
        os.unlink(path)


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
