#!/usr/bin/env python3
"""Export executable workflow graph to n8n workflow JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from workflow_graph_lib import DEFAULT_GRAPH, WorkflowGraphError, edges, load_graph, nodes_by_id, validate_graph

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "workflow" / "n8n" / "daily-newsletter.workflow.json"


def stable_uuid(name: str) -> str:
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def node_position(index: int, wave: int = 0) -> list[int]:
    column = wave or index // 5
    row = index % 5
    return [260 + column * 280, 180 + row * 180]


def incoming_counts(graph: dict[str, Any]) -> dict[str, int]:
    nodes = nodes_by_id(graph)
    counts = {node_id: 0 for node_id in nodes}
    for edge in edges(graph):
        if edge["type"] == "failure":
            continue
        counts[edge["to"]] += 1
    return counts


def n8n_node_type(graph_type: str, command: str) -> tuple[str, float, dict[str, Any]]:
    if graph_type == "trigger":
        return "n8n-nodes-base.manualTrigger", 1, {}
    if command:
        return "n8n-nodes-base.executeCommand", 1, {"command": command}
    return "n8n-nodes-base.noOp", 1, {}


def to_n8n_workflow(graph: dict[str, Any]) -> dict[str, Any]:
    validate_graph(graph)
    nodes = nodes_by_id(graph)
    counts = incoming_counts(graph)
    ordered_ids = list(nodes.keys())
    name_by_id = {node_id: nodes[node_id]["name"] for node_id in ordered_ids}
    n8n_nodes = []
    for index, node_id in enumerate(ordered_ids):
        graph_node = nodes[node_id]
        node_type, type_version, parameters = n8n_node_type(graph_node["type"], graph_node.get("command", ""))
        if counts[node_id] > 1 and node_type == "n8n-nodes-base.executeCommand":
            # n8n receives only one input by default. Keep merge semantics explicit
            # in metadata until a future adapter introduces real Merge nodes.
            parameters = {
                **parameters,
                "notes": f"Graph node has {counts[node_id]} incoming edges; upstream merge is represented by graph metadata.",
            }
        n8n_nodes.append(
            {
                "parameters": parameters,
                "id": stable_uuid(node_id),
                "name": graph_node["name"],
                "type": node_type,
                "typeVersion": type_version,
                "position": node_position(index),
                "notes": json.dumps(
                    {
                        "graph_id": node_id,
                        "graph_type": graph_node["type"],
                        "inputs": graph_node.get("inputs", []),
                        "outputs": graph_node.get("outputs", []),
                    },
                    ensure_ascii=False,
                ),
            }
        )
    connections: dict[str, dict[str, list[list[dict[str, Any]]]]] = {}
    for edge in edges(graph):
        if edge["type"] == "failure":
            continue
        source = name_by_id[edge["from"]]
        target = name_by_id[edge["to"]]
        connections.setdefault(source, {"main": [[]]})
        connections[source]["main"][0].append({"node": target, "type": "main", "index": 0})
    return {
        "name": graph.get("name", "daily-newsletter"),
        "active": False,
        "nodes": n8n_nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {
            "source": "workflow/diagram/daily-newsletter.graph.json",
            "generatedBy": "scripts/n8n_export.py",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing output")
    parser.add_argument("--json", action="store_true", help="Print generated workflow JSON")
    args = parser.parse_args()
    try:
        workflow = to_n8n_workflow(load_graph(args.graph))
    except WorkflowGraphError as exc:
        print(f"FAIL {exc}")
        return 1
    if args.json:
        print(json.dumps(workflow, indent=2, ensure_ascii=False))
    elif args.dry_run:
        print(f"n8n workflow: {workflow['name']}")
        print(f"nodes: {len(workflow['nodes'])}")
        print(f"connections: {sum(len(v['main'][0]) for v in workflow['connections'].values())}")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

