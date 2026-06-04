#!/usr/bin/env python3
"""Print execution order derived from the workflow diagram graph."""
import argparse
import sys
from pathlib import Path

from workflow_graph_lib import DEFAULT_GRAPH, WorkflowGraphError, dry_run_plan, load_graph, print_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        plan = dry_run_plan(load_graph(args.graph))
    except WorkflowGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print_json(plan)
    else:
        for step in plan:
            command = f" :: {step['command']}" if step["command"] else ""
            print(f"wave {step['wave']:02d} | {step['id']} | {step['name']}{command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

