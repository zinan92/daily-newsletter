#!/usr/bin/env python3
"""Return the best ready task for an idle agent."""
import argparse
import sys

from task_graph_lib import TaskGraphError, add_graph_arg, load_graph, next_ready_task, print_json


def main() -> int:
    parser = argparse.ArgumentParser()
    add_graph_arg(parser)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    try:
        task = next_ready_task(load_graph(args.graph))
    except TaskGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if task is None:
        print("NO READY TASK")
        return 2
    if args.json:
        print_json(task)
    else:
        print(f"{task['id']} | {task['type']} | {task['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
