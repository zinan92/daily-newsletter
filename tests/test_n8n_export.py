"""Tests for exporting executable workflow graph to n8n JSON.

Run: python3 tests/test_n8n_export.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from n8n_export import to_n8n_workflow  # noqa: E402
from workflow_graph_lib import edges, load_graph, nodes_by_id  # noqa: E402


def test_export_preserves_node_count_and_names():
    graph = load_graph(ROOT / "workflow" / "diagram" / "daily-newsletter.graph.json")
    workflow = to_n8n_workflow(graph)
    graph_nodes = nodes_by_id(graph)
    assert len(workflow["nodes"]) == len(graph_nodes)
    exported_names = {node["name"] for node in workflow["nodes"]}
    assert {node["name"] for node in graph_nodes.values()} == exported_names


def test_export_maps_non_failure_edges_to_connections():
    graph = load_graph(ROOT / "workflow" / "diagram" / "daily-newsletter.graph.json")
    workflow = to_n8n_workflow(graph)
    graph_nodes = nodes_by_id(graph)
    expected = {
        (graph_nodes[e["from"]]["name"], graph_nodes[e["to"]]["name"])
        for e in edges(graph)
        if e["type"] != "failure"
    }
    actual = set()
    for source, value in workflow["connections"].items():
        for target in value["main"][0]:
            actual.add((source, target["node"]))
    assert expected == actual


def test_failure_edges_are_not_normal_connections():
    graph = load_graph(ROOT / "workflow" / "diagram" / "daily-newsletter.graph.json")
    workflow = to_n8n_workflow(graph)
    targets = {
        target["node"]
        for value in workflow["connections"].values()
        for target in value["main"][0]
    }
    assert "Write Health Alert On Failure" not in targets


def test_export_command_writes_parseable_json():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "workflow.json"
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "n8n_export.py"), "--output", str(out)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["name"] == "daily-newsletter-executable-diagram"
        assert data["active"] is False


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

