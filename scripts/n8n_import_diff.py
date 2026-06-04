#!/usr/bin/env python3
"""Diff n8n workflow JSON against the canonical executable workflow graph.

The n8n file is an adapter artifact. This command imports the n8n-visible
projection and reports drift without overwriting the canonical graph.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from workflow_graph_lib import DEFAULT_GRAPH, WorkflowGraphError, edges, load_graph, nodes_by_id, validate_graph

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOW = ROOT / "workflow" / "n8n" / "daily-newsletter.workflow.json"


class N8nImportError(ValueError):
    """Raised when n8n workflow JSON cannot be imported."""


def load_workflow(path: Path = DEFAULT_WORKFLOW) -> dict[str, Any]:
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise N8nImportError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(workflow, dict):
        raise N8nImportError("n8n workflow must be a JSON object")
    return workflow


def _node_metadata(node: dict[str, Any]) -> dict[str, Any]:
    raw = node.get("notes", "{}")
    if not isinstance(raw, str):
        raise N8nImportError(f"{node.get('name', '<unnamed>')}: notes must be a JSON string")
    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise N8nImportError(f"{node.get('name', '<unnamed>')}: notes are not valid graph metadata") from exc
    graph_id = metadata.get("graph_id")
    if not isinstance(graph_id, str) or not graph_id:
        raise N8nImportError(f"{node.get('name', '<unnamed>')}: missing graph_id metadata")
    return metadata


def _command_from_node(node: dict[str, Any]) -> str:
    parameters = node.get("parameters", {})
    if not isinstance(parameters, dict):
        return ""
    command = parameters.get("command", "")
    return command if isinstance(command, str) else ""


def _edge_type_lookup(workflow: dict[str, Any]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    meta = workflow.get("meta", {})
    graph_edges = meta.get("graphEdges", []) if isinstance(meta, dict) else []
    if not isinstance(graph_edges, list):
        return out
    for edge in graph_edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("from")
        target = edge.get("to")
        edge_type = edge.get("type")
        if isinstance(source, str) and isinstance(target, str) and isinstance(edge_type, str):
            out[(source, target)] = edge_type
    return out


def import_n8n_projection(workflow: dict[str, Any]) -> dict[str, Any]:
    nodes_value = workflow.get("nodes")
    if not isinstance(nodes_value, list) or not nodes_value:
        raise N8nImportError("n8n workflow.nodes must be a non-empty list")
    imported_nodes: list[dict[str, Any]] = []
    name_to_id: dict[str, str] = {}
    for node in nodes_value:
        if not isinstance(node, dict):
            raise N8nImportError("each n8n node must be an object")
        name = node.get("name")
        if not isinstance(name, str) or not name:
            raise N8nImportError("each n8n node needs a non-empty name")
        metadata = _node_metadata(node)
        graph_id = metadata["graph_id"]
        if name in name_to_id:
            raise N8nImportError(f"duplicate n8n node name: {name}")
        name_to_id[name] = graph_id
        imported_nodes.append(
            {
                "id": graph_id,
                "name": name,
                "type": metadata.get("graph_type", "command"),
                "command": _command_from_node(node),
                "inputs": metadata.get("inputs", []),
                "outputs": metadata.get("outputs", []),
            }
        )

    type_lookup = _edge_type_lookup(workflow)
    imported_edges: list[dict[str, str]] = []
    connections = workflow.get("connections", {})
    if not isinstance(connections, dict):
        raise N8nImportError("n8n workflow.connections must be an object")
    for source_name, value in connections.items():
        if source_name not in name_to_id:
            raise N8nImportError(f"connection references unknown source node: {source_name}")
        main_groups = value.get("main", []) if isinstance(value, dict) else []
        if not isinstance(main_groups, list):
            raise N8nImportError(f"{source_name}: main connections must be a list")
        for group in main_groups:
            if not isinstance(group, list):
                raise N8nImportError(f"{source_name}: each main connection group must be a list")
            for target in group:
                if not isinstance(target, dict):
                    raise N8nImportError(f"{source_name}: target connection must be an object")
                target_name = target.get("node")
                if target_name not in name_to_id:
                    raise N8nImportError(f"connection references unknown target node: {target_name}")
                source_id = name_to_id[source_name]
                target_id = name_to_id[target_name]
                imported_edges.append(
                    {
                        "from": source_id,
                        "to": target_id,
                        "type": type_lookup.get((source_id, target_id), "main"),
                    }
                )
    return {
        "version": 1,
        "name": workflow.get("name", "n8n-import"),
        "source_of_truth": "workflow/diagram",
        "nodes": imported_nodes,
        "edges": imported_edges,
    }


def _normal_edges(graph: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (edge["from"], edge["to"], edge["type"])
        for edge in edges(graph)
        if edge["type"] != "failure"
    }


def _node_projection(graph: dict[str, Any]) -> dict[str, tuple[Any, ...]]:
    return {
        node_id: (
            node.get("name"),
            node.get("type"),
            node.get("command", ""),
            tuple(node.get("inputs", [])),
            tuple(node.get("outputs", [])),
        )
        for node_id, node in nodes_by_id(graph).items()
    }


def diff_graphs(canonical: dict[str, Any], imported: dict[str, Any]) -> list[str]:
    validate_graph(canonical)
    validate_graph(imported)
    differences: list[str] = []

    canonical_nodes = _node_projection(canonical)
    imported_nodes = _node_projection(imported)
    for node_id in sorted(set(canonical_nodes) - set(imported_nodes)):
        differences.append(f"missing node in n8n: {node_id}")
    for node_id in sorted(set(imported_nodes) - set(canonical_nodes)):
        differences.append(f"extra node in n8n: {node_id}")
    for node_id in sorted(set(canonical_nodes) & set(imported_nodes)):
        if canonical_nodes[node_id] != imported_nodes[node_id]:
            differences.append(f"changed node in n8n: {node_id}")

    canonical_edges = _normal_edges(canonical)
    imported_edges = _normal_edges(imported)
    for edge in sorted(canonical_edges - imported_edges):
        differences.append(f"missing edge in n8n: {edge[0]} -> {edge[1]} ({edge[2]})")
    for edge in sorted(imported_edges - canonical_edges):
        differences.append(f"extra edge in n8n: {edge[0]} -> {edge[1]} ({edge[2]})")
    return differences


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        canonical = load_graph(args.graph)
        imported = import_n8n_projection(load_workflow(args.workflow))
        differences = diff_graphs(canonical, imported)
    except (WorkflowGraphError, N8nImportError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"differences": differences}, indent=2, ensure_ascii=False))
    elif differences:
        print(f"FAIL n8n workflow differs from canonical graph: {len(differences)} difference(s)")
        for item in differences:
            print(f"- {item}")
    else:
        print("PASS n8n workflow matches canonical graph projection")
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
