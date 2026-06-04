#!/usr/bin/env python3
"""Dry-run or explicitly run commands from the executable workflow graph."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from workflow_graph_lib import DEFAULT_GRAPH, WorkflowGraphError, dry_run_plan, load_graph, nodes_by_id

ROOT = Path(__file__).resolve().parents[1]


def selected_steps(graph: dict[str, Any], selected_ids: list[str]) -> list[dict[str, Any]]:
    all_steps = dry_run_plan(graph)
    if not selected_ids:
        return all_steps
    nodes = nodes_by_id(graph)
    missing = [node_id for node_id in selected_ids if node_id not in nodes]
    if missing:
        raise WorkflowGraphError(f"unknown node id(s): {', '.join(missing)}")
    selected = set(selected_ids)
    return [step for step in all_steps if step["id"] in selected]


def run_steps(steps: list[dict[str, Any]]) -> int:
    for step in steps:
        command = step.get("command", "")
        if not command:
            print(f"SKIP {step['id']} has no command")
            continue
        print(f"RUN {step['id']} :: {command}")
        result = subprocess.run(command, shell=True, cwd=ROOT)
        if result.returncode != 0:
            print(f"FAIL {step['id']} exited {result.returncode}", file=sys.stderr)
            return result.returncode
    return 0


def print_steps(steps: list[dict[str, Any]], mode: str) -> None:
    for step in steps:
        command = f" :: {step['command']}" if step["command"] else ""
        print(f"{mode} wave {step['wave']:02d} | {step['id']} | {step['name']}{command}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--node", action="append", default=[], help="Run or preview one node id; repeatable")
    parser.add_argument("--run", action="store_true", help="Execute selected command nodes")
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="Required with --run so production command execution cannot happen accidentally",
    )
    args = parser.parse_args()
    try:
        steps = selected_steps(load_graph(args.graph), args.node)
    except WorkflowGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if args.run:
        if not args.confirm_production:
            print("FAIL --run requires --confirm-production", file=sys.stderr)
            return 1
        if not args.node:
            print("FAIL --run requires at least one --node", file=sys.stderr)
            return 1
        return run_steps(steps)
    print_steps(steps, "DRY-RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
