#!/usr/bin/env python3
"""Mark a claimed task graph node complete."""
import argparse
import sys

from task_graph_lib import TaskGraphError, add_graph_arg, complete_task, load_graph, print_json, save_graph


def main() -> int:
    parser = argparse.ArgumentParser()
    add_graph_arg(parser)
    parser.add_argument("task_id")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--commit", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        graph = load_graph(args.graph)
        task = complete_task(graph, args.task_id, args.agent, commit=args.commit)
        save_graph(graph, args.graph)
    except TaskGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print_json(task)
    else:
        print(f"COMPLETED {task['id']} by {args.agent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

