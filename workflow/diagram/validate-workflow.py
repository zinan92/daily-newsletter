#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import defaultdict, deque
from pathlib import Path

import yaml


VALID_ROLES = {"entry", "process", "decision", "artifact"}
COMPONENT_ROLE = "artifact_component"


def fail(errors: list[str]) -> None:
    for error in errors:
        print(f"workflow validation error: {error}", file=sys.stderr)
    raise SystemExit(1)


def reachable_from(entries: set[str], outgoing: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    queue = deque(entries)
    while queue:
        node_id = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        queue.extend(outgoing.get(node_id, []))
    return seen


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []

    ids: list[str] = []
    node_by_id: dict[str, dict] = {}
    component_ids: set[str] = set()

    for node in nodes:
        node_id = node.get("id")
        if not node_id:
            errors.append("node missing id")
            continue
        ids.append(node_id)
        node_by_id[node_id] = node
        role = node.get("role")
        if role not in VALID_ROLES:
            errors.append(f"node {node_id} must declare role in {sorted(VALID_ROLES)}")
        if role == COMPONENT_ROLE:
            errors.append(f"node {node_id} cannot be a top-level artifact_component")
        components = node.get("components") or []
        if components and role != "artifact":
            errors.append(f"node {node_id} has components but is not role=artifact")
        for component in components:
            component_id = component.get("id")
            if not component_id:
                errors.append(f"component under {node_id} missing id")
                continue
            component_ids.add(component_id)
            if component.get("role") != COMPONENT_ROLE:
                errors.append(f"component {component_id} under {node_id} must be role={COMPONENT_ROLE}")

    duplicates = sorted({node_id for node_id in ids if ids.count(node_id) > 1})
    for node_id in duplicates:
        errors.append(f"duplicate node id {node_id}")
    for component_id in sorted(component_ids & set(node_by_id)):
        errors.append(f"artifact_component {component_id} must not also be a top-level node")

    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        src = edge.get("from")
        dst = edge.get("to")
        if src not in node_by_id:
            errors.append(f"edge references missing from-node {src}")
            continue
        if dst not in node_by_id:
            errors.append(f"edge references missing to-node {dst}")
            continue
        incoming[dst].append(src)
        outgoing[src].append(dst)

    entries = {node_id for node_id, node in node_by_id.items() if node.get("role") == "entry"}
    if not entries:
        errors.append("workflow must have at least one role=entry node")

    for node_id, node in node_by_id.items():
        role = node.get("role")
        if role == "entry":
            if incoming.get(node_id):
                errors.append(f"entry node {node_id} must not have incoming edges")
        elif not incoming.get(node_id):
            errors.append(f"non-entry node {node_id} has no incoming edge")

    reachable = reachable_from(entries, outgoing)
    for node_id in sorted(set(node_by_id) - reachable):
        errors.append(f"node {node_id} is not reachable from any entry")

    sent = node_by_id.get("sent_artifact")
    if sent:
        if sent.get("role") != "artifact":
            errors.append("sent_artifact must be role=artifact")
        upstream = incoming.get("sent_artifact", [])
        if not upstream:
            errors.append("sent_artifact must have an upstream producer")
        elif not any(node_by_id[src].get("role") in {"process", "decision", "artifact"} for src in upstream):
            errors.append("sent_artifact upstream must be process, decision, or artifact")

    for node_id, node in node_by_id.items():
        if node.get("components") and not outgoing.get(node_id):
            errors.append(f"artifact node {node_id} has components but no outgoing edge")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Park-IO workflow YAML as a closed system.")
    parser.add_argument("workflow", help="Path to inbox-workflow.yaml")
    args = parser.parse_args()

    path = Path(args.workflow)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        fail(errors)
    print(f"workflow validation passed: {path}")


if __name__ == "__main__":
    main()
