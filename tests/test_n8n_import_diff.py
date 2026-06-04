"""Tests for importing and diffing n8n workflow JSON.

Run: python3 tests/test_n8n_import_diff.py
"""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from n8n_export import to_n8n_workflow  # noqa: E402
from n8n_import_diff import diff_graphs, import_n8n_projection  # noqa: E402
from workflow_graph_lib import load_graph, validate_graph  # noqa: E402


def canonical_graph():
    return load_graph(ROOT / "workflow" / "diagram" / "daily-newsletter.graph.json")


def test_exported_workflow_round_trips_without_diff():
    graph = canonical_graph()
    workflow = to_n8n_workflow(graph)
    imported = import_n8n_projection(workflow)
    validate_graph(imported)
    assert diff_graphs(graph, imported) == []


def test_removed_connection_reports_missing_edge():
    graph = canonical_graph()
    workflow = to_n8n_workflow(graph)
    changed = copy.deepcopy(workflow)
    changed["connections"]["Open Batch"]["main"][0] = []
    differences = diff_graphs(graph, import_n8n_projection(changed))
    assert "missing edge in n8n: open_batch -> score (main)" in differences


def test_added_connection_reports_extra_edge():
    graph = canonical_graph()
    workflow = to_n8n_workflow(graph)
    changed = copy.deepcopy(workflow)
    changed["connections"].setdefault("Build Digest", {"main": [[]]})
    changed["connections"]["Build Digest"]["main"][0].append(
        {"node": "Finalize Local Artifacts", "type": "main", "index": 0}
    )
    differences = diff_graphs(graph, import_n8n_projection(changed))
    assert "extra edge in n8n: build_digest -> finalize_local (main)" in differences


def test_command_reports_no_diff_for_generated_file():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "workflow.json"
        export_result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "n8n_export.py"), "--output", str(out)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert export_result.returncode == 0, export_result.stderr or export_result.stdout
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "n8n_import_diff.py"), "--workflow", str(out)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert "PASS n8n workflow matches canonical graph projection" in result.stdout
        assert json.loads(out.read_text(encoding="utf-8"))["meta"]["graphEdges"]


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    raise SystemExit(1 if failed else 0)
