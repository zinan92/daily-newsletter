#!/usr/bin/env python3
"""List ready-to-claim task graph nodes."""
import argparse
import sys

from task_graph_lib import TaskGraphError, add_graph_arg, load_graph, print_json, ready_tasks


def main() -> int:
    parser = argparse.ArgumentParser()
    add_graph_arg(parser)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    try:
        tasks = ready_tasks(load_graph(args.graph))
    except TaskGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print_json(tasks)
    else:
        for task in tasks:
            print(f"{task['id']} | {task['type']} | {task['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

