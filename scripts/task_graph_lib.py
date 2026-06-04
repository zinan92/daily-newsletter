#!/usr/bin/env python3
"""Utilities for repo-local executable task graphs."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "tasks" / "daily-inbox-task-graph.json"

STATUSES = {"todo", "claimed", "in_progress", "blocked", "done"}
DONE = "done"
ACTIVE = {"claimed", "in_progress"}
REQUIRED_TASK_FIELDS = {
    "id",
    "title",
    "type",
    "status",
    "dependencies",
    "success_criteria",
    "test_commands",
    "review_requirements",
    "linter_commands",
}


class TaskGraphError(ValueError):
    """Raised when a task graph is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_graph(path: Path = DEFAULT_GRAPH) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TaskGraphError(f"{path}: invalid JSON: {exc}") from exc


def save_graph(graph: dict[str, Any], path: Path = DEFAULT_GRAPH) -> None:
    path.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tasks_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = graph.get("tasks")
    if not isinstance(tasks, list):
        raise TaskGraphError("graph.tasks must be a list")
    out: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            raise TaskGraphError("each task must be an object")
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise TaskGraphError("each task needs a non-empty string id")
        if task_id in out:
            raise TaskGraphError(f"duplicate task id: {task_id}")
        out[task_id] = task
    return out


def _require_string_list(task: dict[str, Any], field: str) -> None:
    value = task.get(field)
    if not isinstance(value, list) or not value:
        raise TaskGraphError(f"{task['id']}: {field} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise TaskGraphError(f"{task['id']}: {field} must contain non-empty strings")


def validate_graph(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if graph.get("version") != 1:
        raise TaskGraphError("graph.version must be 1")
    if not isinstance(graph.get("project"), str) or not graph["project"]:
        raise TaskGraphError("graph.project must be a non-empty string")
    tasks = tasks_by_id(graph)
    for task in tasks.values():
        missing = sorted(REQUIRED_TASK_FIELDS - set(task))
        if missing:
            raise TaskGraphError(f"{task['id']}: missing fields: {', '.join(missing)}")
        if task["status"] not in STATUSES:
            raise TaskGraphError(f"{task['id']}: invalid status {task['status']!r}")
        dependencies = task["dependencies"]
        if not isinstance(dependencies, list):
            raise TaskGraphError(f"{task['id']}: dependencies must be a list")
        for dep in dependencies:
            if dep not in tasks:
                raise TaskGraphError(f"{task['id']}: unknown dependency {dep}")
        for field in ("success_criteria", "test_commands", "review_requirements", "linter_commands"):
            _require_string_list(task, field)
    _assert_acyclic(tasks)
    return tasks


def _assert_acyclic(tasks: dict[str, dict[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str, path: list[str]) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            cycle = " -> ".join(path + [task_id])
            raise TaskGraphError(f"dependency cycle: {cycle}")
        visiting.add(task_id)
        for dep in tasks[task_id].get("dependencies", []):
            visit(dep, path + [task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id, [])


def is_ready(task: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> bool:
    if task["status"] != "todo":
        return False
    return all(tasks[dep]["status"] == DONE for dep in task.get("dependencies", []))


def ready_tasks(graph: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = validate_graph(graph)
    return sorted((task for task in tasks.values() if is_ready(task, tasks)), key=lambda t: t["id"])


def blocked_by(task: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> list[str]:
    return [dep for dep in task.get("dependencies", []) if tasks[dep]["status"] != DONE]


def execution_waves(graph: dict[str, Any]) -> list[list[str]]:
    tasks = validate_graph(graph)
    remaining = set(tasks)
    completed: set[str] = set()
    waves: list[list[str]] = []
    while remaining:
        wave = sorted(
            task_id
            for task_id in remaining
            if all(dep in completed for dep in tasks[task_id].get("dependencies", []))
        )
        if not wave:
            raise TaskGraphError("cannot compute waves; graph may contain an unresolved cycle")
        waves.append(wave)
        completed.update(wave)
        remaining.difference_update(wave)
    return waves


def execution_threads(graph: dict[str, Any]) -> list[list[str]]:
    """Greedy dependency lanes for operator-readable execution threads.

    Waves show true parallel levels. Threads are stable serial lanes useful for
    assigning agents to chains of related work.
    """
    tasks = validate_graph(graph)
    waves = execution_waves(graph)
    lanes: list[list[str]] = []
    lane_tail: list[str] = []
    for wave in waves:
        for task_id in wave:
            deps = set(tasks[task_id].get("dependencies", []))
            assigned = False
            for idx, tail in enumerate(lane_tail):
                if tail in deps:
                    lanes[idx].append(task_id)
                    lane_tail[idx] = task_id
                    assigned = True
                    break
            if not assigned:
                lanes.append([task_id])
                lane_tail.append(task_id)
    return lanes


def claim_task(graph: dict[str, Any], task_id: str, agent: str) -> dict[str, Any]:
    tasks = validate_graph(graph)
    if task_id not in tasks:
        raise TaskGraphError(f"unknown task id: {task_id}")
    task = tasks[task_id]
    if not is_ready(task, tasks):
        blockers = blocked_by(task, tasks)
        detail = f"; blocked by {', '.join(blockers)}" if blockers else f"; status is {task['status']}"
        raise TaskGraphError(f"{task_id} is not ready{detail}")
    task["status"] = "claimed"
    task["claimed_by"] = agent
    task["claimed_at"] = utc_now()
    task.setdefault("history", []).append({"event": "claimed", "agent": agent, "at": task["claimed_at"]})
    return task


def complete_task(graph: dict[str, Any], task_id: str, agent: str, commit: str = "") -> dict[str, Any]:
    tasks = validate_graph(graph)
    if task_id not in tasks:
        raise TaskGraphError(f"unknown task id: {task_id}")
    task = tasks[task_id]
    if task["status"] not in ACTIVE:
        raise TaskGraphError(f"{task_id} must be claimed or in_progress before completion")
    if task.get("claimed_by") and task.get("claimed_by") != agent:
        raise TaskGraphError(f"{task_id} is claimed by {task.get('claimed_by')}, not {agent}")
    task["status"] = "done"
    task["completed_by"] = agent
    task["completed_at"] = utc_now()
    if commit:
        task["commit"] = commit
    task.setdefault("history", []).append({"event": "completed", "agent": agent, "at": task["completed_at"], "commit": commit})
    return task


def add_graph_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH, help=f"Task graph JSON path (default: {DEFAULT_GRAPH})")


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))

