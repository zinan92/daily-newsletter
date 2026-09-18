"""Coverage ledger: fetched → batched → published on fixture dirs.

Run: python3 -m pytest tests/test_coverage_ledger.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import coverage_ledger as ledger  # noqa: E402

DATE = "2026-09-17"


def _raw(root: Path, profile: str, tid: str) -> str:
    url = f"https://x.com/{profile}/status/{tid}"
    path = root / DATE / profile / f"{tid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"id": tid, "url": url, "text": "hello"}), encoding="utf-8")
    (root / DATE / profile / f"{tid}.json.to-md.json").write_text("{}", encoding="utf-8")
    return url


def _fixture(tmp_path: Path) -> dict[str, Path]:
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    sent = tmp_path / "sent"
    unprocessed = tmp_path / "unprocessed"
    (raw / DATE).mkdir(parents=True)
    (raw / DATE / "product-radar.json").write_text('{"signals": []}', encoding="utf-8")

    u_jev = _raw(raw, "vista8", "1")          # fetched, never batched (the Jev case)
    u_pub = _raw(raw, "openai", "2")          # fetched → batched → published
    u_drop = _raw(raw, "wadezone", "3")       # fetched → batched → discarded
    _raw(raw, "wadezone", "4")                # fetched, never batched

    ai_dir = processed / "26-09-17" / "ai"
    ai_dir.mkdir(parents=True)
    (ai_dir / "00-input-items.json").write_text(
        json.dumps([{"url": u_pub}, {"url": u_drop + "?utm=x"}, {"url": "https://example.com/not-fetched-today"}]),
        encoding="utf-8",
    )
    sent.mkdir()
    (sent / "26-09-17.md").write_text(f"# AI Daily\n\n- [a]({u_pub})\n- [b](https://example.com/other)\n", encoding="utf-8")

    (unprocessed / DATE / "items").mkdir(parents=True)
    (unprocessed / DATE / "items" / "jev.md").write_text("---\nurl: x\n---\n", encoding="utf-8")
    (unprocessed / "2026-09-18" / "items").mkdir(parents=True)
    (unprocessed / "2026-09-18" / "items" / "today.md").write_text("---\nurl: y\n---\n", encoding="utf-8")
    return {"raw": raw, "processed": processed, "sent": sent, "unprocessed": unprocessed}


def _row(tmp_path: Path, as_of: str = "2026-09-18") -> dict:
    d = _fixture(tmp_path)
    return ledger.build_ledger_row(
        DATE,
        as_of=as_of,
        raw_dir=d["raw"],
        processed_dir=d["processed"],
        sent_dir=d["sent"],
        unprocessed_dir=d["unprocessed"],
    )


def test_three_layers_count_only_items_fetched_that_day(tmp_path):
    row = _row(tmp_path)
    assert row["fetched"] == 4
    assert row["fetched_by_profile"] == {"openai": 1, "vista8": 1, "wadezone": 2}
    assert row["batched"] == 2  # query string on the batched URL must not break the match
    assert row["published"] == 1
    assert row["published_total_urls"] == 2
    assert row["batch_rate"] == 0.5
    assert row["publish_rate"] == 0.5


def test_never_batched_is_listed_by_profile(tmp_path):
    row = _row(tmp_path)
    assert row["never_batched"] == 2
    assert row["never_batched_by_profile"] == {"vista8": 1, "wadezone": 1}
    assert any("vista8/status/1" in u for u in row["never_batched_examples"])


def test_backlog_older_than_as_of_is_stale(tmp_path):
    row = _row(tmp_path, as_of="2026-09-18")
    assert row["pending_backlog"] == {DATE: 1, "2026-09-18": 1}
    assert row["stale_backlog"] is True
    assert row["stale_days"] == [DATE]


def test_backlog_on_the_as_of_day_is_not_stale(tmp_path):
    d = _fixture(tmp_path)
    row = ledger.build_ledger_row(
        DATE,
        as_of=DATE,
        raw_dir=d["raw"],
        processed_dir=d["processed"],
        sent_dir=d["sent"],
        unprocessed_dir=d["unprocessed"],
    )
    assert row["pending_backlog"] == {DATE: 1}
    assert row["stale_backlog"] is False


def test_rerun_replaces_the_same_day_row(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.append_ledger({"date": DATE, "fetched": 1}, path)
    ledger.append_ledger({"date": "2026-09-16", "fetched": 9}, path)
    ledger.append_ledger({"date": DATE, "fetched": 2}, path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [r["date"] for r in rows] == ["2026-09-16", DATE]
    assert rows[1]["fetched"] == 2


def test_markdown_mentions_all_three_layers_and_backlog(tmp_path):
    text = ledger.render_markdown(_row(tmp_path))
    assert "抓到 4 → 进批 2（50%）→ 进日报 1（50%）" in text
    assert "从未进批 2 条" in text
    assert "超期积压" in text


def test_markdown_for_today_calls_the_gap_tomorrows_batch(tmp_path):
    text = ledger.render_markdown(_row(tmp_path, as_of=DATE))
    assert "明早进批" in text
    assert "超期" not in text
