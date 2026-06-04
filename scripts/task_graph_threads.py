#!/usr/bin/env python3
"""Show execution waves and serial task lanes."""
import argparse
import sys

from task_graph_lib import TaskGraphError, add_graph_arg, execution_threads, execution_waves, load_graph, print_json


def main() -> int:
    parser = argparse.ArgumentParser()
    add_graph_arg(parser)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    try:
        graph = load_graph(args.graph)
        waves = execution_waves(graph)
        threads = execution_threads(graph)
    except TaskGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print_json({"waves": waves, "threads": threads})
    else:
        print("Execution waves:")
        for idx, wave in enumerate(waves, 1):
            print(f"  wave {idx}: {', '.join(wave)}")
        print("\nExecution threads:")
        for idx, thread in enumerate(threads, 1):
            print(f"  thread {idx}: {' -> '.join(thread)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

