#!/usr/bin/env python3
"""Validate a repo-local executable task graph."""
import argparse
import sys

from task_graph_lib import TaskGraphError, add_graph_arg, load_graph, validate_graph


def main() -> int:
    parser = argparse.ArgumentParser()
    add_graph_arg(parser)
    args = parser.parse_args()
    try:
        graph = load_graph(args.graph)
        tasks = validate_graph(graph)
    except TaskGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print(f"PASS {args.graph}: {len(tasks)} task(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

