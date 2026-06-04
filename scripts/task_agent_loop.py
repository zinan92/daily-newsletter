#!/usr/bin/env python3
"""Show or perform one bounded idle-agent claim loop."""
import argparse
import sys

from task_graph_lib import (
    TaskGraphError,
    add_graph_arg,
    claim_task,
    load_graph,
    next_ready_task,
    print_json,
    save_graph,
)


def plan_claims(graph: dict, agent: str, iterations: int) -> list[dict]:
    planned: list[dict] = []
    for _ in range(iterations):
        task = next_ready_task(graph)
        if task is None:
            break
        planned.append({"agent": agent, "task_id": task["id"], "title": task["title"], "type": task["type"]})
        # Simulate reservation so a multi-iteration dry run does not print the
        # same task repeatedly. This mutates only the in-memory graph.
        task["status"] = "claimed"
        task["claimed_by"] = agent
    return planned


def main() -> int:
    parser = argparse.ArgumentParser()
    add_graph_arg(parser)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--claim", action="store_true", help="Persist claims to the task graph")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    if args.iterations < 1:
        print("FAIL --iterations must be >= 1", file=sys.stderr)
        return 1
    try:
        graph = load_graph(args.graph)
        if args.claim:
            claimed = []
            for _ in range(args.iterations):
                task = next_ready_task(graph)
                if task is None:
                    break
                claimed_task = claim_task(graph, task["id"], args.agent)
                claimed.append(
                    {
                        "agent": args.agent,
                        "task_id": claimed_task["id"],
                        "title": claimed_task["title"],
                        "type": claimed_task["type"],
                    }
                )
            save_graph(graph, args.graph)
            planned = claimed
        else:
            planned = plan_claims(graph, args.agent, args.iterations)
    except TaskGraphError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print_json({"mode": "claim" if args.claim else "dry-run", "claims": planned})
    else:
        mode = "CLAIM" if args.claim else "DRY-RUN"
        if not planned:
            print(f"{mode} no ready task")
        for item in planned:
            print(f"{mode} {item['agent']} -> {item['task_id']} | {item['type']} | {item['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
