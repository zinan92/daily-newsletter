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

from lib import PARKIO, PROCESSED_DIR, parse_frontmatter, render_frontmatter, safe_filename, today


RAW_DIR = PARKIO / "_inbox" / "raw"
UNPROCESSED_DIR = PARKIO / "_inbox" / "unprocessed"
PROCESSED_MARKER_SUFFIX = ".to-md.json"
DEFAULT_LOOKBACK_DAYS = 1


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


def marker_path(path: Path) -> Path:
    return path.with_name(path.name + PROCESSED_MARKER_SUFFIX)


def raw_record_date(path: Path, fallback: str) -> str:
    parts = path.parts
    for part in reversed(parts):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", part):
            return part
    return fallback


def parse_dir_date(name: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%y-%m-%d"):
        try:
            return datetime.strptime(name[:10] if fmt == "%Y-%m-%d" else name[:8], fmt)
        except ValueError:
            continue
    return None


def write_marker(path: Path, dest: Path) -> None:
    marker_path(path).write_text(
        json.dumps(
            {
                "raw_path": str(path),
                "markdown_path": str(dest),
                "normalized_at": datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def should_skip_raw(path: Path, out_dir: Path, record: dict | None = None, *, skip_marked: bool = True) -> bool:
    if path.name.endswith(PROCESSED_MARKER_SUFFIX):
        return True
    if skip_marked and marker_path(path).exists():
        return True
    if record is not None:
        return output_path(record, out_dir).exists()
    return False


def existing_normalized_raw_paths(*, lookback_days: int = DEFAULT_LOOKBACK_DAYS, date: str | None = None) -> set[str]:
    """Raw paths already represented in unprocessed/processed Markdown."""
    date = date or today()
    try:
        today_dt = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        today_dt = datetime.now()
    roots: list[Path] = []
    for base in (UNPROCESSED_DIR, PROCESSED_DIR):
        if not base.exists():
            continue
        for child in base.iterdir():
            if not child.is_dir():
                continue
            child_dt = parse_dir_date(child.name)
            if child_dt and not (0 <= (today_dt - child_dt).days <= lookback_days):
                continue
            roots.append(child)
    seen: set[str] = set()
    for root in roots:
        for md in root.rglob("*.md"):
            if md.name.startswith("000-") or md.name.startswith("deep-"):
                continue
            try:
                fm, _ = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            raw_path = str(fm.get("raw_path") or "").strip()
            if raw_path:
                seen.add(raw_path)
    return seen


def raw_roots_for_pending(date: str, raw_dir: Path | None = None, *, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> list[tuple[str, Path]]:
    if raw_dir is not None:
        return [(date, raw_dir)]
    roots: list[tuple[str, Path]] = []
    today_dt = datetime.strptime(date, "%Y-%m-%d")
    for child in sorted(RAW_DIR.iterdir() if RAW_DIR.exists() else []):
        if not child.is_dir() or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", child.name):
            continue
        try:
            child_dt = datetime.strptime(child.name, "%Y-%m-%d")
        except ValueError:
            continue
        age_days = (today_dt - child_dt).days
        if 0 <= age_days <= lookback_days:
            roots.append((child.name, child))
    return roots or [(date, RAW_DIR / date)]


def normalize_raw_day(
    date: str | None = None,
    raw_dir: Path | None = None,
    out_dir: Path | None = None,
    *,
    pending_only: bool = False,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[Path]:
    date = date or today()
    written: list[Path] = []
    roots = raw_roots_for_pending(date, raw_dir, lookback_days=lookback_days) if pending_only else [(date, raw_dir or RAW_DIR / date)]
    existing_raw_paths = existing_normalized_raw_paths(lookback_days=lookback_days, date=date) if pending_only else set()
    for root_date, raw_root in roots:
        if not raw_root.exists():
            continue
        root_target = out_dir or UNPROCESSED_DIR / root_date / "items"
        root_target.mkdir(parents=True, exist_ok=True)
        for path in sorted(p for p in raw_root.rglob("*") if p.is_file()):
            if path.name.startswith("."):
                continue
            if str(path) in existing_raw_paths:
                continue
            if should_skip_raw(path, root_target, skip_marked=pending_only):
                continue
            record = normalize_record(path)
            raw_date = raw_record_date(path, root_date)
            target = root_target
            if out_dir is None and raw_date != root_date:
                target = UNPROCESSED_DIR / raw_date / "items"
                target.mkdir(parents=True, exist_ok=True)
            if should_skip_raw(path, target, record, skip_marked=pending_only):
                continue
            dest = output_path(record, target)
            dest.write_text(render_item_markdown(record), encoding="utf-8")
            write_marker(path, dest)
            written.append(dest)
    return written


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else today()
    written = normalize_raw_day(date, pending_only=True)
    print(f"[to-md] wrote {len(written)} markdown item(s)")
    from enrichment.media import run as media_enrichment

    media_enrichment.main(date=date, include_retry_failed=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
