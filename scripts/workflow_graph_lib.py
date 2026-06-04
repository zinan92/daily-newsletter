#!/usr/bin/env python3
"""Executable workflow graph utilities.

The graph is the source of truth for runtime order. Commands are payloads on
nodes; edges decide sequencing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "workflow" / "diagram" / "daily-newsletter.graph.json"

NODE_TYPES = {"trigger", "command", "gate", "artifact", "status", "notification"}
EDGE_TYPES = {"main", "success", "failure", "optional"}
REQUIRED_NODE_FIELDS = {"id", "name", "type", "command", "inputs", "outputs"}
REQUIRED_EDGE_FIELDS = {"from", "to", "type"}


class WorkflowGraphError(ValueError):
    """Raised when a workflow graph is invalid."""


def load_graph(path: Path = DEFAULT_GRAPH) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowGraphError(f"{path}: invalid JSON: {exc}") from exc


def nodes_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise WorkflowGraphError("graph.nodes must be a non-empty list")
    out: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise WorkflowGraphError("each node must be an object")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise WorkflowGraphError("each node needs a non-empty string id")
        if node_id in out:
            raise WorkflowGraphError(f"duplicate node id: {node_id}")
        out[node_id] = node
    return out


def edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    value = graph.get("edges")
    if not isinstance(value, list):
        raise WorkflowGraphError("graph.edges must be a list")
    return value


def _require_string_list(node: dict[str, Any], field: str) -> None:
    value = node.get(field)
    if not isinstance(value, list):
        raise WorkflowGraphError(f"{node['id']}: {field} must be a list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise WorkflowGraphError(f"{node['id']}: {field} must contain strings")


def validate_graph(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if graph.get("version") != 1:
        raise WorkflowGraphError("graph.version must be 1")
    if graph.get("source_of_truth") != "workflow/diagram":
        raise WorkflowGraphError("graph.source_of_truth must be workflow/diagram")
    nodes = nodes_by_id(graph)
    for node in nodes.values():
        missing = sorted(REQUIRED_NODE_FIELDS - set(node))
        if missing:
            raise WorkflowGraphError(f"{node['id']}: missing fields: {', '.join(missing)}")
        if node["type"] not in NODE_TYPES:
            raise WorkflowGraphError(f"{node['id']}: invalid type {node['type']!r}")
        if node["type"] == "command" and not str(node.get("command", "")).strip():
            raise WorkflowGraphError(f"{node['id']}: command node requires command")
        _require_string_list(node, "inputs")
        _require_string_list(node, "outputs")
    for edge in edges(graph):
        missing = sorted(REQUIRED_EDGE_FIELDS - set(edge))
        if missing:
            raise WorkflowGraphError(f"edge missing fields: {', '.join(missing)}")
        if edge["from"] not in nodes:
            raise WorkflowGraphError(f"edge references unknown from node: {edge['from']}")
        if edge["to"] not in nodes:
            raise WorkflowGraphError(f"edge references unknown to node: {edge['to']}")
        if edge["type"] not in EDGE_TYPES:
            raise WorkflowGraphError(f"edge {edge['from']}->{edge['to']}: invalid type {edge['type']!r}")
    _assert_acyclic(nodes, edges(graph))
    return nodes


def _assert_acyclic(nodes: dict[str, dict[str, Any]], edge_list: list[dict[str, Any]]) -> None:
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for edge in edge_list:
        adjacency[edge["from"]].append(edge["to"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str, path: list[str]) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise WorkflowGraphError(f"workflow cycle: {' -> '.join(path + [node_id])}")
        visiting.add(node_id)
        for nxt in adjacency[node_id]:
            visit(nxt, path + [node_id])
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in nodes:
        visit(node_id, [])


def execution_waves(graph: dict[str, Any], include_failure: bool = False) -> list[list[str]]:
    nodes = validate_graph(graph)
    active_nodes = set(nodes) if include_failure else _normal_path_nodes(nodes, edges(graph))
    incoming: dict[str, set[str]] = {node_id: set() for node_id in active_nodes}
    for edge in edges(graph):
        if edge["type"] == "failure" and not include_failure:
            continue
        if edge["from"] in active_nodes and edge["to"] in active_nodes:
            incoming[edge["to"]].add(edge["from"])
    remaining = set(active_nodes)
    completed: set[str] = set()
    waves: list[list[str]] = []
    while remaining:
        wave = sorted(node_id for node_id in remaining if incoming[node_id].issubset(completed))
        if not wave:
            raise WorkflowGraphError("cannot compute execution order")
        waves.append(wave)
        completed.update(wave)
        remaining.difference_update(wave)
    return waves


def _normal_path_nodes(nodes: dict[str, dict[str, Any]], edge_list: list[dict[str, Any]]) -> set[str]:
    normal_edges = [edge for edge in edge_list if edge["type"] != "failure"]
    incoming_normal: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    incoming_failure: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for edge in edge_list:
        if edge["type"] == "failure":
            incoming_failure[edge["to"]].add(edge["from"])
            continue
        incoming_normal[edge["to"]].add(edge["from"])
        adjacency[edge["from"]].append(edge["to"])
    roots = sorted(
        node_id
        for node_id in nodes
        if not incoming_normal[node_id] and not incoming_failure[node_id]
    )
    if not normal_edges:
        return set(roots)
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        stack.extend(adjacency[node_id])
    return seen


def dry_run_plan(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = validate_graph(graph)
    out: list[dict[str, Any]] = []
    for wave_index, wave in enumerate(execution_waves(graph), 1):
        for node_id in wave:
            node = nodes[node_id]
            out.append(
                {
                    "wave": wave_index,
                    "id": node_id,
                    "name": node["name"],
                    "type": node["type"],
                    "command": node.get("command", ""),
                    "inputs": node.get("inputs", []),
                    "outputs": node.get("outputs", []),
                }
            )
    return out


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))
