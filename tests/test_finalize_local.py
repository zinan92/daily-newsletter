"""Regression tests for local finalization artifact parity.

Run: python3 tests/test_finalize_local.py
"""
import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("finalize_local", ROOT / "finalize-local.py")
finalize_local = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finalize_local)


def test_finalize_copies_markdown_html_and_png():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        processed = base / "processed"
        sent = base / "sent"
        processed.mkdir()

        md = processed / "000-26-06-04.md"
        html = processed / "000-26-06-04.html"
        png = processed / "000-26-06-04.png"
        md.write_text("# Digest\n", encoding="utf-8")
        html.write_text("<h1>Digest</h1>\n", encoding="utf-8")
        png.write_bytes(b"fake-png-bytes")

        original_sent = finalize_local.SENT_DIR
        original_label = finalize_local.batch_label
        original_paths = finalize_local.batch_artifact_paths
        try:
            finalize_local.SENT_DIR = sent
            finalize_local.batch_label = lambda: "26-06-04"
            finalize_local.batch_artifact_paths = lambda: (md, html, png)

            assert finalize_local.main() == 0
        finally:
            finalize_local.SENT_DIR = original_sent
            finalize_local.batch_label = original_label
            finalize_local.batch_artifact_paths = original_paths

        assert (sent / "26-06-04.md").read_text(encoding="utf-8") == "# Digest\n"
        assert (sent / "26-06-04.html").read_text(encoding="utf-8") == "<h1>Digest</h1>\n"
        assert (sent / "26-06-04.png").read_bytes() == b"fake-png-bytes"


def test_missing_processed_markdown_fails():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        processed = base / "processed"
        sent = base / "sent"
        processed.mkdir()

        md = processed / "000-26-06-04.md"
        html = processed / "000-26-06-04.html"
        png = processed / "000-26-06-04.png"
        html.write_text("<h1>Digest</h1>\n", encoding="utf-8")
        png.write_bytes(b"fake-png-bytes")

        original_sent = finalize_local.SENT_DIR
        original_label = finalize_local.batch_label
        original_paths = finalize_local.batch_artifact_paths
        try:
            finalize_local.SENT_DIR = sent
            finalize_local.batch_label = lambda: "26-06-04"
            finalize_local.batch_artifact_paths = lambda: (md, html, png)

            assert finalize_local.main() == 1
        finally:
            finalize_local.SENT_DIR = original_sent
            finalize_local.batch_label = original_label
            finalize_local.batch_artifact_paths = original_paths

        assert not sent.exists()


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
    raise SystemExit(1 if failed else 0)
