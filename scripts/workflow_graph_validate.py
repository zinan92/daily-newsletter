#!/usr/bin/env python3
"""Validate the executable workflow diagram graph."""
import argparse
import sys
from pathlib import Path

from workflow_graph_lib import DEFAULT_GRAPH, WorkflowGraphError, load_graph, validate_graph


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    args = parser.parse_args()
    try:
        nodes = validate_graph(load_graph(args.graph))
    except WorkflowGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print(f"PASS {args.graph}: {len(nodes)} node(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

