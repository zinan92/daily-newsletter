#!/usr/bin/env python3
"""Render task graph nodes as GitHub Issue dry-run payloads."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from task_graph_lib import DONE, TaskGraphError, add_graph_arg, is_ready, load_graph, tasks_by_id, validate_graph


def labels_for_task(task: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> list[str]:
    labels = [
        "daily-inbox",
        "task-graph",
        f"task:{task['type']}",
        f"status:{task['status']}",
    ]
    if is_ready(task, tasks):
        labels.append("ready")
    if task["status"] == "blocked":
        labels.append("blocked")
    if task["status"] in {"claimed", "in_progress"}:
        labels.append("claimed")
    return labels


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- None"


def issue_body(task: dict[str, Any]) -> str:
    dependencies = task.get("dependencies", [])
    files = task.get("files", [])
    return "\n".join(
        [
            "## Task",
            "",
            f"- ID: {task['id']}",
            f"- Type: {task['type']}",
            f"- Status: {task['status']}",
            f"- Dependencies: {', '.join(dependencies) if dependencies else 'None'}",
            f"- Files: {', '.join(files) if files else 'None'}",
            "",
            "## Success Criteria",
            "",
            _bullets(task.get("success_criteria", [])),
            "",
            "## Test Commands",
            "",
            _bullets(task.get("test_commands", [])),
            "",
            "## Linter Commands",
            "",
            _bullets(task.get("linter_commands", [])),
            "",
            "## Review Requirements",
            "",
            _bullets(task.get("review_requirements", [])),
            "",
            "## Claim Protocol",
            "",
            f"Claim locally: `python3 scripts/task_claim.py {task['id']} --agent <agent-id>`",
            f"Complete locally: `python3 scripts/task_complete.py {task['id']} --agent <agent-id> --commit <sha>`",
            "",
            "## Source Of Truth",
            "",
            "`tasks/daily-inbox-task-graph.json` is canonical. GitHub Issues mirror this task but do not replace the local graph.",
        ]
    )


def issue_payload(task: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "task_id": task["id"],
        "title": f"[{task['id']}] {task['title']}",
        "labels": labels_for_task(task, tasks),
        "state": "closed" if task["status"] == DONE else "open",
        "body": issue_body(task),
    }


def export_payloads(graph: dict[str, Any], only_task: str = "") -> list[dict[str, Any]]:
    validate_graph(graph)
    tasks = tasks_by_id(graph)
    if only_task and only_task not in tasks:
        raise TaskGraphError(f"unknown task id: {only_task}")
    selected = [tasks[only_task]] if only_task else list(tasks.values())
    return [issue_payload(task, tasks) for task in sorted(selected, key=lambda item: item["id"])]


def main() -> int:
    parser = argparse.ArgumentParser()
    add_graph_arg(parser)
    parser.add_argument("--task", default="", help="Render one task id")
    parser.add_argument("--json", action="store_true", help="Print full issue payload JSON")
    args = parser.parse_args()
    try:
        payloads = export_payloads(load_graph(args.graph), only_task=args.task)
    except TaskGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payloads, indent=2, ensure_ascii=False))
    else:
        for payload in payloads:
            print(f"{payload['state'].upper()} {payload['title']} labels={','.join(payload['labels'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
