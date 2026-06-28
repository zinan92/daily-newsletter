#!/usr/bin/env python3
"""Maintain the personal collection index in Park-IO."""
from __future__ import annotations

import re
from pathlib import Path

from lib import LIBRARY_DIR, clean_collection_title, collection_source_code, today

INDEX_FILE = LIBRARY_DIR / "_manual-links.md"
URL_RE = re.compile(r"https?://[^\s<>)\]]+")


def default_index_text() -> str:
    return "\n".join(
        [
            "# 个人收藏索引",
            "",
            "这个文件是 `002_个人收藏` 的总索引。它记录每一条显式收藏的来源、作者、标题、tags 和处理状态。",
            "",
            "- 最近收藏排在最上面。",
            "- `Tags` 是人工/agent 后续补充的主题标签；脚本更新时会尽量保留已有 tags。",
            "- `状态` 用来检查这条内容是否已经落成单篇 markdown。",
            "",
            "## Index",
            "",
            "| 日期 | Source | 作者 | Title | Tags | 状态 | 文件 | 原文 |",
            "|---|---|---|---|---|---|---|---|",
            "",
            "## Pending",
            "",
            "这里可以临时粘贴还没处理的链接；正常情况下，新链接从飞书 `好文收藏` 群自动进入 Index。",
            "",
            "## Failed",
            "",
        ]
    )


def ensure_index_file() -> None:
    if not INDEX_FILE.exists():
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        INDEX_FILE.write_text(default_index_text(), encoding="utf-8")


def _section_text(text: str, section: str) -> str:
    match = re.search(rf"^## {re.escape(section)}\s*$", text, flags=re.M)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^## .+$", text[start:], flags=re.M)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end]


def pending_lines() -> list[str]:
    ensure_index_file()
    text = INDEX_FILE.read_text(encoding="utf-8")
    return [line.rstrip() for line in _section_text(text, "Pending").splitlines() if line.strip()]


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    out: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return clean_collection_title(line.removeprefix("# ").strip())
    return ""


def _author_from_text(text: str) -> str:
    patterns = [
        r"author:\s*([^·\n]+)",
        r"作者[：:]\s*([^\n]+)",
        r"\*\*source:[^·\n]+·\s*author:\s*([^·\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).strip()
    return ""


def _source_from_filename(path: Path) -> str:
    parts = path.stem.split("_", 2)
    if len(parts) >= 2 and re.fullmatch(r"\d{6}", parts[0]):
        return parts[1]
    return ""


def _date_from_filename(path: Path, fm: dict[str, str]) -> str:
    prefix = path.stem.split("_", 1)[0]
    if re.fullmatch(r"\d{6}", prefix):
        return prefix
    for key in ("captured_at", "library_archived_at", "published_at", "published"):
        value = fm.get(key, "")
        match = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
        if match:
            return f"{match.group(1)[2:]}{match.group(2)}{match.group(3)}"
    return today().replace("-", "")[2:]


def _record_key(row: dict[str, str]) -> str:
    return row.get("url") or row.get("file") or row.get("title") or ""


def _escape_cell(value: str) -> str:
    value = str(value or "").replace("\n", " ").strip()
    value = value.replace("|", "\\|")
    return value or "-"


def _short_title(value: str, limit: int = 72) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _split_table_row(line: str) -> list[str]:
    cells: list[str] = []
    current = []
    escaped = False
    for char in line.strip().strip("|"):
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def _link_url(cell: str) -> str:
    match = re.search(r"\]\((https?://[^)]+)\)", cell)
    return match.group(1) if match else ""


def _wikilink_file(cell: str) -> str:
    match = re.search(r"\[\[([^|\]]+)", cell)
    return match.group(1).strip() if match else ""


def existing_tags() -> dict[str, str]:
    ensure_index_file()
    text = INDEX_FILE.read_text(encoding="utf-8")
    tags: dict[str, str] = {}
    for line in _section_text(text, "Index").splitlines():
        if not line.startswith("|") or "---" in line or "日期" in line:
            continue
        cells = _split_table_row(line)
        if len(cells) < 8:
            continue
        value = cells[4].strip()
        if not value or value == "-":
            continue
        url = _link_url(cells[7])
        file_name = _wikilink_file(cells[6])
        if url:
            tags[url] = value
        if file_name:
            tags[file_name] = value
    return tags


def collection_record_from_file(path: Path, tag_overrides: dict[str, str] | None = None) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = _parse_frontmatter(text)
    url = (
        fm.get("source_url")
        or fm.get("url")
        or (fm.get("id") if fm.get("id", "").startswith("http") else "")
    )
    source = _source_from_filename(path) or collection_source_code(
        {"platform": fm.get("source_platform") or fm.get("source"), "name": fm.get("source_name")},
        {"url": url, "source": fm.get("source")},
        url,
    )
    title = _first_heading(text) or clean_collection_title(path.stem)
    author = fm.get("author") or _author_from_text(text) or fm.get("handle") or "-"
    status = fm.get("status") or "archived"
    tag_overrides = tag_overrides or {}
    tags = tag_overrides.get(url) or tag_overrides.get(path.name) or fm.get("tags") or "-"
    return {
        "date": _date_from_filename(path, fm),
        "source": source,
        "author": author,
        "title": title,
        "tags": tags,
        "status": status,
        "file": path.name,
        "url": url,
    }


def collection_records() -> list[dict[str, str]]:
    tag_overrides = existing_tags()
    records: list[dict[str, str]] = []
    for path in sorted(LIBRARY_DIR.glob("*.md")):
        if path.name in {"README.md", INDEX_FILE.name}:
            continue
        try:
            records.append(collection_record_from_file(path, tag_overrides))
        except OSError:
            continue
    return sorted(records, key=lambda row: (row.get("date", ""), row.get("title", "")), reverse=True)


def render_index(
    records: list[dict[str, str]],
    *,
    pending: list[str] | None = None,
    failed: list[dict[str, str]] | None = None,
) -> str:
    lines = [
        "# 个人收藏索引",
        "",
        "这个文件是 `002_个人收藏` 的总索引。它记录每一条显式收藏的来源、作者、标题、tags 和处理状态。",
        "",
        "- 最近收藏排在最上面。",
        "- `Tags` 是人工/agent 后续补充的主题标签；脚本更新时会尽量保留已有 tags。",
        "- `状态` 用来检查这条内容是否已经落成单篇 markdown。",
        "",
        "## Index",
        "",
        "| 日期 | Source | 作者 | Title | Tags | 状态 | 文件 | 原文 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for record in records:
        file_name = record.get("file", "")
        title = _short_title(record.get("title", "") or file_name)
        file_link = f"[[{file_name}|打开]]" if file_name else "-"
        url = record.get("url", "")
        source_link = f"[link]({url})" if url else "-"
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_cell(record.get("date", "")),
                    _escape_cell(record.get("source", "")),
                    _escape_cell(record.get("author", "")),
                    _escape_cell(title),
                    _escape_cell(record.get("tags", "")),
                    _escape_cell(record.get("status", "")),
                    file_link,
                    source_link,
                ]
            )
            + " |"
        )
    lines.extend(["", "## Pending", ""])
    lines.append("这里可以临时粘贴还没处理的链接；正常情况下，新链接从飞书 `好文收藏` 群自动进入 Index。")
    lines.append("")
    for line in pending or []:
        lines.append(line)
    lines.extend(["", "## Failed", ""])
    for row in failed or []:
        date = row.get("date") or today()
        url = row.get("url") or ""
        error = str(row.get("error") or "unknown error").replace("\n", " ").strip()
        lines.append(f"- {date} · {url} · {error}")
    lines.append("")
    return "\n".join(lines)


def rebuild_collection_index(
    *,
    pending: list[str] | None = None,
    failed: list[dict[str, str]] | None = None,
) -> None:
    ensure_index_file()
    INDEX_FILE.write_text(
        render_index(collection_records(), pending=pending, failed=failed),
        encoding="utf-8",
    )


def existing_collection_path_for_url(url: str) -> Path | None:
    if not url:
        return None
    for path in sorted(LIBRARY_DIR.glob("*.md")):
        if path.name in {"README.md", INDEX_FILE.name}:
            continue
        try:
            if url in path.read_text(encoding="utf-8", errors="replace"):
                return path
        except OSError:
            continue
    return None
