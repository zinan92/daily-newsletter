"""Tests for executable task graph planning and claim semantics.

Run: python3 tests/test_task_graph.py
"""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from task_graph_lib import (  # noqa: E402
    TaskGraphError,
    claim_task,
    complete_task,
    downstream_counts,
    execution_threads,
    execution_waves,
    load_graph,
    next_ready_task,
    ready_tasks,
    validate_graph,
)


def minimal_task(task_id, deps=None, status="todo"):
    return {
        "id": task_id,
        "title": task_id,
        "type": "implementation",
        "status": status,
        "dependencies": deps or [],
        "success_criteria": ["done"],
        "test_commands": ["true"],
        "review_requirements": ["review"],
        "linter_commands": ["true"],
    }


def graph(tasks):
    return {"version": 1, "project": "test", "tasks": tasks}


def test_daily_inbox_task_graph_validates():
    tasks = validate_graph(load_graph(ROOT / "tasks" / "daily-inbox-task-graph.json"))
    assert len(tasks) >= 20
    assert "TG-001" in tasks
    assert "VERIFY-001" in tasks


def test_missing_dependency_is_rejected():
    g = graph([minimal_task("TG-001", deps=["NOPE-001"])])
    try:
        validate_graph(g)
    except TaskGraphError as exc:
        assert "unknown dependency" in str(exc)
    else:
        raise AssertionError("missing dependency accepted")


def test_dependency_cycle_is_rejected():
    g = graph([
        minimal_task("TG-001", deps=["TG-002"]),
        minimal_task("TG-002", deps=["TG-001"]),
    ])
    try:
        validate_graph(g)
    except TaskGraphError as exc:
        assert "dependency cycle" in str(exc)
    else:
        raise AssertionError("cycle accepted")


def test_ready_tasks_require_done_dependencies():
    g = graph([
        minimal_task("TG-001", status="done"),
        minimal_task("TG-002", deps=["TG-001"]),
        minimal_task("TG-003", deps=["TG-002"]),
    ])
    ready = [task["id"] for task in ready_tasks(g)]
    assert ready == ["TG-002"]


def test_claim_and_complete_task():
    g = graph([minimal_task("TG-001")])
    claimed = claim_task(g, "TG-001", "codex")
    assert claimed["status"] == "claimed"
    assert claimed["claimed_by"] == "codex"
    completed = complete_task(g, "TG-001", "codex", commit="abc123")
    assert completed["status"] == "done"
    assert completed["commit"] == "abc123"


def test_execution_waves_change_when_edge_changes():
    base = graph([
        minimal_task("TG-001"),
        minimal_task("TG-002"),
        minimal_task("TG-003", deps=["TG-001", "TG-002"]),
    ])
    changed = copy.deepcopy(base)
    changed["tasks"][1]["dependencies"] = ["TG-001"]
    assert execution_waves(base) == [["TG-001", "TG-002"], ["TG-003"]]
    assert execution_waves(changed) == [["TG-001"], ["TG-002"], ["TG-003"]]


def test_execution_threads_are_serial_lanes():
    g = graph([
        minimal_task("TG-001"),
        minimal_task("TG-002"),
        minimal_task("TG-003", deps=["TG-001"]),
        minimal_task("TG-004", deps=["TG-002"]),
    ])
    threads = execution_threads(g)
    assert ["TG-001", "TG-003"] in threads
    assert ["TG-002", "TG-004"] in threads


def test_next_ready_task_prefers_largest_downstream_unlock():
    g = graph([
        minimal_task("A-001"),
        minimal_task("B-001"),
        minimal_task("A-002", deps=["A-001"]),
        minimal_task("A-003", deps=["A-002"]),
    ])
    assert downstream_counts(validate_graph(g))["A-001"] == 2
    assert next_ready_task(g)["id"] == "A-001"


def test_next_ready_task_uses_type_then_id_tiebreak():
    g = graph([
        {**minimal_task("B-001"), "type": "implementation"},
        {**minimal_task("A-001"), "type": "contract"},
    ])
    assert next_ready_task(g)["id"] == "A-001"


def test_agent_loop_dry_run_does_not_mutate_graph_file():
    with tempfile.TemporaryDirectory() as tmp:
        graph_path = Path(tmp) / "graph.json"
        original = graph([minimal_task("A-001"), minimal_task("B-001")])
        graph_path.write_text(json.dumps(original, indent=2), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "task_agent_loop.py"),
                "--graph",
                str(graph_path),
                "--agent",
                "codex",
                "--iterations",
                "2",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert "DRY-RUN codex -> A-001" in result.stdout
        assert json.loads(graph_path.read_text(encoding="utf-8")) == original


def test_agent_loop_claim_mode_mutates_graph_file():
    with tempfile.TemporaryDirectory() as tmp:
        graph_path = Path(tmp) / "graph.json"
        graph_path.write_text(json.dumps(graph([minimal_task("A-001")]), indent=2), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "task_agent_loop.py"),
                "--graph",
                str(graph_path),
                "--agent",
                "codex",
                "--claim",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        updated = json.loads(graph_path.read_text(encoding="utf-8"))
        assert updated["tasks"][0]["status"] == "claimed"
        assert updated["tasks"][0]["claimed_by"] == "codex"


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
