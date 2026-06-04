"""Tests for executable workflow diagram graphs.

Run: python3 tests/test_workflow_graph.py
"""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from workflow_graph_lib import (  # noqa: E402
    WorkflowGraphError,
    dry_run_plan,
    execution_waves,
    load_graph,
    validate_graph,
)


def node(node_id, command="true"):
    return {
        "id": node_id,
        "name": node_id,
        "type": "command" if command else "trigger",
        "command": command,
        "inputs": [],
        "outputs": [node_id],
    }


def graph(nodes, edges):
    return {
        "version": 1,
        "name": "test",
        "source_of_truth": "workflow/diagram",
        "nodes": nodes,
        "edges": edges,
    }


def test_daily_newsletter_graph_validates():
    g = load_graph(ROOT / "workflow" / "diagram" / "daily-newsletter.graph.json")
    nodes = validate_graph(g)
    assert "rss" in nodes
    assert "build_digest" in nodes
    assert "finalize_local" in nodes


def test_unknown_edge_node_is_rejected():
    g = graph([node("start", command="")], [{"from": "start", "to": "missing", "type": "main"}])
    try:
        validate_graph(g)
    except WorkflowGraphError as exc:
        assert "unknown to node" in str(exc)
    else:
        raise AssertionError("unknown edge target accepted")


def test_command_node_requires_command():
    g = graph([{"id": "bad", "name": "bad", "type": "command", "command": "", "inputs": [], "outputs": []}], [])
    try:
        validate_graph(g)
    except WorkflowGraphError as exc:
        assert "requires command" in str(exc)
    else:
        raise AssertionError("empty command accepted")


def test_cycle_is_rejected():
    g = graph(
        [node("a"), node("b")],
        [{"from": "a", "to": "b", "type": "main"}, {"from": "b", "to": "a", "type": "main"}],
    )
    try:
        validate_graph(g)
    except WorkflowGraphError as exc:
        assert "workflow cycle" in str(exc)
    else:
        raise AssertionError("cycle accepted")


def test_dry_run_plan_uses_graph_edges():
    g = graph(
        [node("a"), node("b"), node("c")],
        [{"from": "a", "to": "c", "type": "main"}, {"from": "b", "to": "c", "type": "main"}],
    )
    plan = dry_run_plan(g)
    assert [step["id"] for step in plan] == ["a", "b", "c"]
    assert [step["wave"] for step in plan] == [1, 1, 2]


def test_dry_run_excludes_failure_only_nodes():
    g = graph(
        [node("start", command=""), node("ok"), node("alert")],
        [
            {"from": "start", "to": "ok", "type": "main"},
            {"from": "ok", "to": "alert", "type": "failure"},
        ],
    )
    assert [step["id"] for step in dry_run_plan(g)] == ["start", "ok"]


def test_changing_edge_changes_execution_order():
    base = graph(
        [node("a"), node("b"), node("c")],
        [{"from": "a", "to": "c", "type": "main"}],
    )
    changed = copy.deepcopy(base)
    changed["edges"].append({"from": "c", "to": "b", "type": "main"})
    assert execution_waves(base) == [["a", "b"], ["c"]]
    assert execution_waves(changed) == [["a"], ["c"], ["b"]]


def test_workflow_runner_dry_run_does_not_execute_commands():
    with tempfile.TemporaryDirectory() as tmp:
        marker = Path(tmp) / "marker.txt"
        graph_path = Path(tmp) / "graph.json"
        g = graph(
            [node("start", command=""), node("write", command=f"{sys.executable} -c \"open('{marker}', 'w').write('ran')\"")],
            [{"from": "start", "to": "write", "type": "main"}],
        )
        graph_path.write_text(json.dumps(g), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "workflow_graph_run.py"), "--graph", str(graph_path)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert "DRY-RUN wave" in result.stdout
        assert not marker.exists()


def test_workflow_runner_requires_confirmation_for_run_mode():
    with tempfile.TemporaryDirectory() as tmp:
        graph_path = Path(tmp) / "graph.json"
        graph_path.write_text(json.dumps(graph([node("write")], [])), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "workflow_graph_run.py"),
                "--graph",
                str(graph_path),
                "--node",
                "write",
                "--run",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 1
        assert "--confirm-production" in result.stderr


def test_workflow_runner_can_select_failure_only_node():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "workflow_graph_run.py"),
            "--node",
            "health_alert",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "health_alert" in result.stdout
    assert "check-pipeline-health.py" in result.stdout


def test_workflow_runner_executes_selected_node_with_confirmation():
    with tempfile.TemporaryDirectory() as tmp:
        marker = Path(tmp) / "marker.txt"
        graph_path = Path(tmp) / "graph.json"
        command = f"{sys.executable} -c \"open('{marker}', 'w').write('ran')\""
        g = graph([node("write", command=command)], [])
        graph_path.write_text(json.dumps(g), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "workflow_graph_run.py"),
                "--graph",
                str(graph_path),
                "--node",
                "write",
                "--run",
                "--confirm-production",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert marker.read_text() == "ran"


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
