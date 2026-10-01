"""A run that dies late must not pay for the earlier stages again."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stages.ai_process import run as ai


def _cards(ids):
    return [{"id": i, "title": i} for i in ids]


def _events(pairs):
    return [{"event_id": eid, "sources": [{"id": s} for s in srcs]} for eid, srcs in pairs]


def test_events_checkpoint_requires_every_current_card(tmp_path):
    ai.write_json(tmp_path / "02-events.json", _events([("e1", ["a", "b"]), ("e2", ["c"])]))
    assert ai.cached_events(tmp_path, _cards(["a", "b", "c"])) is not None
    # a new card that the stored merge never saw -> recompute
    assert ai.cached_events(tmp_path, _cards(["a", "b", "c", "d"])) is None
    # no checkpoint at all
    assert ai.cached_events(tmp_path / "empty", _cards(["a"])) is None


def test_events_checkpoint_rejects_corrupt_or_empty_files(tmp_path):
    (tmp_path / "02-events.json").write_text("{not json", encoding="utf-8")
    assert ai.cached_events(tmp_path, _cards(["a"])) is None
    ai.write_json(tmp_path / "02-events.json", [])
    assert ai.cached_events(tmp_path, _cards(["a"])) is None


def test_selection_checkpoint_requires_every_referenced_event(tmp_path):
    events = _events([("e1", ["a"]), ("e2", ["b"])])
    ai.write_json(tmp_path / "03-selection.json", {
        "brief_universe": [{"event_id": "e1", "subsection": "底层工具"}],
        "deep_candidates": [], "discard": [{"event_id": "e2"}],
    })
    assert ai.cached_selection(tmp_path, events) is not None
    # selection points at an event id that no longer exists -> recompute
    assert ai.cached_selection(tmp_path, _events([("e9", ["a"])])) is None


def test_selection_checkpoint_rejects_empty_selection(tmp_path):
    ai.write_json(tmp_path / "03-selection.json", {"brief_universe": []})
    assert ai.cached_selection(tmp_path, _events([("e1", ["a"])])) is None


def test_item_understanding_resumes_from_finished_chunks(tmp_path, monkeypatch):
    items = [{"id": f"i{n}", "title": "t", "content": "c"} for n in range(6)]
    monkeypatch.setattr(ai, "chunk_items_for_understanding", lambda xs: [xs[0:2], xs[2:4], xs[4:6]])
    calls = []

    def fake_stage(ai_dir, stage, prompt, chunk, max_tokens=0, extra_instruction=""):
        calls.append([c["id"] for c in chunk])
        if len(calls) == 2 and not getattr(fake_stage, "ok", False):
            raise RuntimeError("network blip")
        return [{"id": c["id"], "main_claim": "x"} for c in chunk]

    monkeypatch.setattr(ai, "call_json_stage", fake_stage)
    try:
        ai.item_understanding(tmp_path, items)
    except RuntimeError:
        pass
    assert calls == [["i0", "i1"], ["i2", "i3"]]
    fake_stage.ok = True
    calls.clear()
    cards = ai.item_understanding(tmp_path, items)
    assert calls == [["i2", "i3"], ["i4", "i5"]]          # chunk 1 not redone
    assert [c["id"] for c in cards] == [f"i{n}" for n in range(6)]
