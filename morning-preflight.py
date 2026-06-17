#!/usr/bin/env python3
"""Block scheduled morning push when recoverable source auth is broken."""
from __future__ import annotations

import sys
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_generate_status():
    spec = importlib.util.spec_from_file_location("generate_status", ROOT / "generate-status.py")
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("cannot load generate-status.py")
    spec.loader.exec_module(module)
    return module


generate_status = load_generate_status()


BLOCKING_DEP_NAMES = ("WeWe", "公众号", "YouTube")


def blocking_rows() -> list[dict]:
    rows = []
    for row in generate_status.dependency_checks():
        name = str(row.get("name") or "")
        status = str(row.get("status") or "")
        if status == "ok":
            continue
        if any(token in name for token in BLOCKING_DEP_NAMES):
            rows.append(row)
    return rows


def main() -> int:
    rows = blocking_rows()
    if not rows:
        print("[morning-preflight] ok")
        return 0
    print("[morning-preflight] blocked: recoverable source auth needs attention")
    for row in rows:
        print(f"- {row.get('name')}: {row.get('detail')}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
