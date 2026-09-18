"""Archive cleanup never deletes the batch being archived.

Run: python3 -m pytest tests/test_archive_cleanup.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stages.archive import run as archive  # noqa: E402


def _batch(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "000-x.md").write_text("x", encoding="utf-8")
    return d


def test_current_backfill_batch_survives_retention(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "PROCESSED_DIR", tmp_path)
    old = _batch(tmp_path, "26-09-01")
    current = _batch(tmp_path, "26-09-02-晚")  # labelled for an old day, archived today
    fresh = _batch(tmp_path, "26-12-31")
    monkeypatch.setattr(archive, "processed_batch_dir", lambda *_a, **_k: current)
    removed = archive.cleanup_old_processed(retention_hours=72)
    assert removed == 1
    assert not old.exists()
    assert current.exists()
    assert fresh.exists()


def test_retention_env_widens_the_window(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "PROCESSED_DIR", tmp_path)
    old = _batch(tmp_path, "26-09-01")
    current = _batch(tmp_path, "26-12-31")
    monkeypatch.setattr(archive, "processed_batch_dir", lambda *_a, **_k: current)
    monkeypatch.setenv("PARKIO_PROCESSED_RETENTION_HOURS", "100000")
    assert archive.cleanup_old_processed() == 0
    assert old.exists()
