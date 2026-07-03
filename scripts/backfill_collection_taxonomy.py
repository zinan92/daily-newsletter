#!/usr/bin/env python3
"""Backfill category/tags frontmatter for Park-IO personal collection items."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingestion.collection_index import rebuild_collection_index
from ingestion.collection_taxonomy import classify_collection_text, tag_string
from lib import LIBRARY_DIR

SKIP_NAMES = {"README.md", "_manual-links.md"}


def split_frontmatter(text: str) -> tuple[list[str], str]:
    if not text.startswith("---\n"):
        return [], text
    end = text.find("\n---\n", 4)
    if end == -1:
        return [], text
    lines = text[4:end].splitlines()
    body = text[end + 5 :]
    return lines, body


def field_map(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return fallback


def set_frontmatter_field(lines: list[str], key: str, value: str, after: tuple[str, ...]) -> list[str]:
    prefix = f"{key}:"
    replacement = f"{key}: {value}"
    for idx, line in enumerate(lines):
        if line.startswith(prefix):
            lines[idx] = replacement
            return lines
    insert_at = len(lines)
    for idx, line in enumerate(lines):
        if ":" not in line:
            continue
        current_key = line.split(":", 1)[0].strip()
        if current_key in after:
            insert_at = idx + 1
    lines.insert(insert_at, replacement)
    return lines


def render_frontmatter(lines: list[str], body: str) -> str:
    return "---\n" + "\n".join(lines) + "\n---\n" + body.lstrip("\n")


def update_file(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines, body = split_frontmatter(text)
    if not lines:
        lines = []
    fields = field_map(lines)
    title = first_heading(body, path.stem)
    url = fields.get("source_url") or fields.get("url") or fields.get("id") or ""
    source = fields.get("source") or fields.get("source_name") or fields.get("platform") or ""
    author = fields.get("author") or fields.get("handle") or ""
    taxonomy = classify_collection_text(
        title=title,
        body=body,
        url=url,
        source=source,
        author=author,
        existing_tags=fields.get("tags") or "",
    )
    lines = set_frontmatter_field(lines, "category", taxonomy.category, ("status", "origin", "published"))
    lines = set_frontmatter_field(lines, "tags", tag_string(taxonomy.tags), ("category",))
    new_text = render_frontmatter(lines, body)
    if new_text == text:
        return taxonomy.category
    path.write_text(new_text, encoding="utf-8")
    return taxonomy.category


def main() -> int:
    counts: Counter[str] = Counter()
    updated = 0
    for path in sorted(LIBRARY_DIR.glob("*.md")):
        if path.name in SKIP_NAMES:
            continue
        category = update_file(path)
        if not category:
            continue
        counts[category] += 1
        updated += 1
    rebuild_collection_index(preserve_existing_tags=False)
    print(f"updated {updated} collection item(s)")
    for category, count in sorted(counts.items()):
        print(f"{category}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
