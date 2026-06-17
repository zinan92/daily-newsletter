#!/usr/bin/env python3
"""Stage 2: normalize raw inputs to one markdown item per file.

This is the new contract for sources that already write raw artifacts. Existing
fetchers can still write legacy markdown into inbox/unprocessed until migrated.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import PARKIO, render_frontmatter, safe_filename, today


RAW_DIR = PARKIO / "_inbox" / "raw"
UNPROCESSED_DIR = PARKIO / "_inbox" / "unprocessed"


def title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip("# ").strip()
        if line:
            return line[:120]
    return fallback


def normalize_record(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            raise ValueError("top-level JSON list is not a single item")
        body = str(
            data.get("content")
            or data.get("text")
            or data.get("body")
            or data.get("summary")
            or data.get("description")
            or data.get("transcript")
            or ""
        )
        return {
            "id": str(data.get("id") or data.get("url") or path.stem),
            "source": str(data.get("source") or data.get("source_name") or ""),
            "source_name": str(data.get("source_name") or data.get("source") or ""),
            "profile_id": str(data.get("profile_id") or ""),
            "profile_name": str(data.get("profile_name") or data.get("source_name") or data.get("source") or ""),
            "platform": str(data.get("platform") or ""),
            "category": str(data.get("category") or ""),
            "channel": str(data.get("channel") or ""),
            "author": str(data.get("author") or ""),
            "title": str(data.get("title") or title_from_text(body, path.stem)),
            "url": str(data.get("url") or ""),
            "published_at": str(data.get("published_at") or data.get("published") or ""),
            "content_type": str(data.get("content_type") or data.get("type") or "text"),
            "duration": str(data.get("duration") or data.get("duration_seconds") or ""),
            "fetched_at": str(data.get("fetched_at") or datetime.now().isoformat(timespec="seconds")),
            "raw_path": str(path),
            "content": body,
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "id": path.stem,
        "source": "",
        "source_name": "",
        "profile_id": "",
        "profile_name": "",
        "platform": "",
        "category": "",
        "channel": "",
        "author": "",
        "title": title_from_text(text, path.stem),
        "url": "",
        "published_at": "",
        "content_type": "text",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "raw_path": str(path),
        "content": text,
    }


def render_item_markdown(record: dict) -> str:
    fm = {
        key: record.get(key, "")
        for key in (
            "id",
            "source",
            "source_name",
            "profile_id",
            "profile_name",
            "platform",
            "category",
            "channel",
            "author",
            "title",
            "url",
            "published_at",
            "content_type",
            "duration",
            "fetched_at",
            "raw_path",
        )
    }
    title = str(record.get("title") or "Untitled")
    body = str(record.get("content") or "").strip()
    return render_frontmatter(fm) + f"# {title}\n\n{body}\n"


def output_path(record: dict, out_dir: Path) -> Path:
    title = safe_filename(str(record.get("title") or "item"))[:70] or "item"
    ident = safe_filename(str(record.get("id") or record.get("url") or title))[-24:] or "item"
    return out_dir / f"{title}-{ident}.md"


def normalize_raw_day(date: str | None = None, raw_dir: Path | None = None, out_dir: Path | None = None) -> list[Path]:
    date = date or today()
    raw_root = raw_dir or RAW_DIR / date
    target = out_dir or UNPROCESSED_DIR / date / "items"
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for path in sorted(p for p in raw_root.rglob("*") if p.is_file()):
        if path.name.startswith("."):
            continue
        record = normalize_record(path)
        dest = output_path(record, target)
        dest.write_text(render_item_markdown(record), encoding="utf-8")
        written.append(dest)
    return written


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else today()
    written = normalize_raw_day(date)
    print(f"[to-md] wrote {len(written)} markdown item(s)")
    from enrichment.media import run as media_enrichment

    media_enrichment.main(date=date, include_retry_failed=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
