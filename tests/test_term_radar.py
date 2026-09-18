"""Term radar: ≥3 independent sources + still-new → candidate; known/stop words never.

Run: python3 -m pytest tests/test_term_radar.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import term_radar as radar  # noqa: E402

DATE = "2026-09-17"


def _raw(root: Path, profile: str, name: str, **fields) -> None:
    path = root / DATE / profile / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")


def _fixture(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    # Jev: three independent x handles + one radar post → candidate.
    _raw(raw, "vista8", "a", url="https://x.com/vista8/status/1", text="这两天最火的新构架大模型 Jev，官方 Waitlist 填写地址", handle="vista8")
    _raw(raw, "x-home", "b", url="https://x.com/dev1/status/2", text="Tried Jev from TypeSafe for routing. Wild speed.", handle="dev1")
    _raw(raw, "x-home", "c", url="https://x.com/dev2/status/3", text="Jev means structured output is interesting again. The OpenAI alumni did it.", handle="dev2")
    _raw(raw, "x-home", "c2", url="https://x.com/dev2/status/4", text="More on Jev: it never hallucinates a type.", handle="dev2")  # same handle → same source
    # Hypit: only two sources → not a candidate.
    _raw(raw, "x-home", "d", url="https://x.com/maker/status/5", text="Hypit clones viral videos with agents", handle="maker")
    _raw(raw, "github-trending", "e", url="https://github.com/hypit-ai/hypit", title="hypit-ai/hypit — Clone any viral video", text="Hypit is open source")
    # Radar: TrustMRR template words across many cards must count as ONE source.
    (raw / DATE).mkdir(parents=True, exist_ok=True)
    (raw / DATE / "product-radar.json").write_text(json.dumps({"signals": [
        {"source": "TrustMRR", "url": f"https://trustmrr.com/startup/{i}", "title": "Stealth Company", "summary": "Revenue Tool; Revenue/MRR $4k"} for i in range(6)
    ] + [
        {"source": "Hacker News", "url": "https://news.ycombinator.com/item?id=9", "title": "Show HN: Jev playground", "summary": "typed decisions"},
    ]}), encoding="utf-8")
    return raw


def test_extract_terms_finds_names_not_common_words():
    terms = radar.extract_terms("After Jev launched, OpenRouter shipped Union Alpha. Check hypit.ai and 「Astra for Law」 https://x.com/a @bob #ai")
    assert {"Jev", "OpenRouter", "Union Alpha", "hypit.ai", "Astra for Law"} <= terms
    assert "https" not in " ".join(terms).lower()
    assert "bob" not in {t.lower() for t in terms}


def test_three_sources_flag_jev_but_two_do_not_flag_hypit(tmp_path):
    raw = _fixture(tmp_path)
    mentions = radar.count_mentions(radar.iter_documents(DATE, raw, tmp_path / "no-saved.json"), radar.known_terms())
    assert len(mentions["jev"]["sources"]) == 4  # vista8, dev1, dev2 (two posts), HN post
    assert len(mentions["hypit"]["sources"]) == 2
    assert "stealth company" not in mentions  # known template phrase
    assert "revenue" not in mentions
    candidates, memory = radar.build_candidates(DATE, mentions, {})
    names = [c["term"] for c in candidates]
    assert names == ["Jev"]
    assert candidates[0]["sources"] == 4
    assert candidates[0]["first_seen"] == DATE
    assert memory["jev"]["candidate_dates"] == [DATE]
    assert memory["hypit"]["days"] == {DATE: 2}
    assert "candidate_dates" not in memory["hypit"]


def test_template_radar_source_counts_once(tmp_path):
    raw = _fixture(tmp_path)
    docs = list(radar.iter_documents(DATE, raw, tmp_path / "no-saved.json"))
    trust = {src for src, _, _ in docs if src.startswith("radar:TrustMRR")}
    assert trust == {"radar:TrustMRR"}
    hn = {src for src, _, _ in docs if src.startswith("radar:Hacker News")}
    assert len(hn) == 1 and next(iter(hn)).endswith("item?id=9")


def test_old_terms_are_not_new_even_with_many_sources(tmp_path):
    raw = _fixture(tmp_path)
    mentions = radar.count_mentions(radar.iter_documents(DATE, raw, tmp_path / "no-saved.json"), radar.known_terms())
    old_memory = {"jev": {"first_seen": "2026-08-01", "days": {"2026-08-01": 3}}}
    candidates, memory = radar.build_candidates(DATE, mentions, old_memory)
    assert candidates == []
    assert memory["jev"]["first_seen"] == "2026-08-01"
    assert memory["jev"]["days"][DATE] == 4


def test_lowercase_usage_in_corpus_demotes_capitalized_common_words(tmp_path):
    raw = tmp_path / "raw"
    for i, handle in enumerate(("a", "b", "c")):
        _raw(raw, "x-home", handle, url=f"https://x.com/{handle}/status/{i}", handle=handle,
             text="Building is fun. I love building things. Zorblax is the new tool.")
    mentions = radar.count_mentions(radar.iter_documents(DATE, raw, tmp_path / "no-saved.json"), radar.known_terms())
    assert "building" not in mentions
    assert len(mentions["zorblax"]["sources"]) == 3


def test_run_writes_candidates_and_memory(tmp_path):
    raw = _fixture(tmp_path)
    mem = tmp_path / "term-memory.json"
    out = tmp_path / "term-candidates"
    candidates, markdown = radar.run(DATE, write=True, raw_dir=raw, memory_path=mem, candidates_dir=out, x_saved_path=tmp_path / "none.json")
    assert [c["term"] for c in candidates] == ["Jev"]
    assert "**Jev** · 4 个来源 · 今天首见" in markdown
    assert (out / f"{DATE}.md").read_text(encoding="utf-8") == markdown
    assert json.loads(mem.read_text(encoding="utf-8"))["jev"]["surface"] == "Jev"


def test_render_without_candidates_says_so():
    assert "没有跨 3 个来源" in radar.render_markdown(DATE, [])
