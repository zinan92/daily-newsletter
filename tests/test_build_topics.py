"""Regression tests for the read-only hourly topic workbench.

Run: python3 tests/test_build_topics.py
"""
import importlib.util
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_build_topics():
    spec = importlib.util.spec_from_file_location("build_topics", ROOT / "build-topics.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_collect_topics_reads_unprocessed_without_consuming_files():
    build_topics = load_build_topics()
    with tempfile.TemporaryDirectory() as tmp:
        inbox = Path(tmp)
        raw = inbox / "26-06-05-openai.md"
        raw.write_text(
            "\n".join(
                [
                    "---",
                    "profile_id: openai",
                    "profile_name: OpenAI",
                    "category: ai-official",
                    "published_at: 2026-06-05",
                    "---",
                    "",
                    "# openai · 2026-06-05",
                    "",
                    "## Codex update",
                    "source: OpenAI Blog · *2026-06-05* · [link](https://openai.com/news/example)",
                    "",
                    "Codex shipped a workflow update.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        rows = build_topics.collect_topics(inbox)
        assert raw.exists(), "topic workbench must not consume unprocessed raw files"
        assert len(rows) == 1
        assert rows[0]["channel"] == "official"
        assert rows[0]["title"] == "Codex update"


def test_render_outputs_are_nonempty_and_owner_readable():
    build_topics = load_build_topics()
    rows = [
        {
            "title": "Codex update",
            "url": "https://openai.com/news/example",
            "source": "OpenAI Blog",
            "profile": "openai",
            "channel": "official",
            "channel_label": "官方动态",
            "published": "2026-06-05",
            "excerpt": "Codex shipped a workflow update.",
            "file": "26-06-05-openai.md",
            "mtime": 1,
        }
    ]
    md = build_topics.render_md(rows)
    html = build_topics.render_html(rows)
    assert "Park-IO Topic Workbench" in md
    assert "只读" in html
    assert "Codex update" in html


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
