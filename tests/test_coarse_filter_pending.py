"""Regression: the morning batch drains every pending day dir, not just today's.

Run: python3 -m pytest tests/test_coarse_filter_pending.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stages.coarse_filter import run as coarse  # noqa: E402


def _item(path: Path, title: str, source: str = "vista8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "id: 1",
                f"source: {source}",
                f"source_name: {source}",
                f"profile_id: {source}",
                "platform: twitter",
                "category: ai",
                f"title: {title}",
                "url: https://x.com/vista8/status/1",
                "published_at: 2026-09-17",
                "---",
                "",
                f"# {title}",
                "",
                "TypeSafe 发布 Jev：一个只做类型化决策的 System One 模型，比 LLM 快 40 倍。官方 waitlist 已开放。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _setup(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    unprocessed = tmp_path / "unprocessed"
    processed = tmp_path / "processed" / "26-09-18"
    monkeypatch.setattr(coarse, "UNPROCESSED_DIR", unprocessed)
    monkeypatch.setattr(coarse, "processed_batch_dir", lambda bid=None: processed)
    monkeypatch.setattr(coarse, "batch_id", lambda: "20260918")
    monkeypatch.setattr(coarse, "today", lambda: "2026-09-18")
    monkeypatch.setattr(coarse, "log", lambda *_a, **_k: None)
    monkeypatch.delenv("PARKIO_PENDING_LOOKBACK_DAYS", raising=False)
    return unprocessed, processed


def test_yesterday_items_are_drained_into_today_batch(tmp_path, monkeypatch):
    unprocessed, processed = _setup(tmp_path, monkeypatch)
    _item(unprocessed / "2026-09-17" / "items" / "jev-1.md", "这两天最火的新构架大模型 Jev")
    _item(unprocessed / "2026-09-18" / "items" / "today-1.md", "Claude Code Projects 重做")

    assert coarse.main() == 0

    moved = sorted(p.name for p in processed.rglob("*.md"))
    assert moved == ["jev-1.md", "today-1.md"]
    assert not (unprocessed / "2026-09-17").exists()
    assert not (unprocessed / "2026-09-18").exists()


def test_dirs_older_than_lookback_are_left_alone(tmp_path, monkeypatch):
    unprocessed, processed = _setup(tmp_path, monkeypatch)
    _item(unprocessed / "2026-09-10" / "items" / "old-1.md", "太旧的条目")
    _item(unprocessed / "2026-09-16" / "items" / "recent-1.md", "两天前的条目")

    assert coarse.main() == 0

    assert sorted(p.name for p in processed.rglob("*.md")) == ["recent-1.md"]
    assert (unprocessed / "2026-09-10" / "items" / "old-1.md").exists()


def test_lookback_env_widens_the_window(tmp_path, monkeypatch):
    unprocessed, processed = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("PARKIO_PENDING_LOOKBACK_DAYS", "10")
    _item(unprocessed / "2026-09-10" / "items" / "old-1.md", "八天前的条目")

    assert coarse.main() == 0

    assert sorted(p.name for p in processed.rglob("*.md")) == ["old-1.md"]


def test_future_dated_dirs_are_ignored(tmp_path, monkeypatch):
    unprocessed, processed = _setup(tmp_path, monkeypatch)
    _item(unprocessed / "2026-09-19" / "items" / "future-1.md", "未来日期的条目")

    assert coarse.main() == 0

    assert not processed.exists() or not list(processed.rglob("*.md"))
    assert (unprocessed / "2026-09-19" / "items" / "future-1.md").exists()
