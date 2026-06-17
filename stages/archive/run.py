#!/usr/bin/env python3
"""Archive processed item files into the long-term profile library."""
import re
import shutil
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import (
    LIBRARY_DIR,
    PROFILE_LIBRARY_DIR,
    PROCESSED_DIR,
    batch_label,
    channel_for_source,
    item_identity,
    item_slug,
    load_sources,
    log,
    parse_frontmatter,
    parse_md_items,
    processed_batch_dir,
    render_frontmatter,
    safe_filename,
    today,
)


def profile_readme(profile_dir: Path, profile_id: str, profile_name: str) -> None:
    path = profile_dir / "profile.md"
    if path.exists():
        return
    path.write_text(
        "\n".join(
            [
                "---",
                f"profile_id: {profile_id}",
                f"profile_name: {profile_name}",
                "---",
                "",
                f"# {profile_name}",
                "",
                "## Channels",
                "",
                "- To be filled from sources.md.",
                "",
                "## Why Follow",
                "",
                "This profile is tracked because it may produce useful signal for the daily inbox.",
                "",
                "## Default Handling Rules",
                "",
                "- Attribute every item to this profile.",
                "- Keep source/channel in item metadata and filename, not in another folder layer.",
                "- Include user-curated media sources without score filtering.",
                "",
                "## Recent Baseline",
                "",
                "- Not enough archived items yet.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def source_index() -> dict[str, dict]:
    return {src["name"]: src for src in load_sources()}


def _date_from_batch(batch: str) -> str:
    match = re.match(r"^(\d{2})-(\d{2})-(\d{2})", batch)
    if match:
        yy, mm, dd = match.groups()
        return f"20{yy}-{mm}-{dd}"
    if re.fullmatch(r"\d{8}", batch):
        return f"{batch[:4]}-{batch[4:6]}-{batch[6:8]}"
    return today()


def library_date_dir(collected_date: str) -> Path:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    return LIBRARY_DIR


def library_item_filename(collected_date: str, source: dict, item: dict) -> str:
    platform = safe_filename(channel_for_source(source))
    author = safe_filename(str(source.get("name") or source.get("profile_name") or "unknown"))
    title = item_slug(item, max_len=96)
    stem = f"{collected_date}__{platform}__{author}__{title}"
    suffix = item_identity(item)
    return f"{stem}__{suffix}.md"


def selected_urls_from_ai(root: Path) -> set[str] | None:
    path = root / "ai" / "03-selection.json"
    events_path = root / "ai" / "02-events.json"
    if not path.exists() or not events_path.exists():
        return None
    try:
        selection = json.loads(path.read_text(encoding="utf-8"))
        events = json.loads(events_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    by_id = {str(event.get("event_id") or ""): event for event in events if isinstance(event, dict)}
    urls: set[str] = set()
    for bucket in ("brief_universe", "deep_candidates"):
        for row in selection.get(bucket, []):
            event = by_id.get(str(row.get("event_id") or row.get("parent_brief_event_id") or ""))
            if not event:
                continue
            for source in event.get("sources", []):
                url = str(source.get("url") or "")
                if url:
                    urls.add(url)
    return urls


def markdown_items_for_archive(path: Path, fm: dict, body: str) -> list[dict]:
    parsed = parse_md_items(body)
    if parsed:
        return parsed
    title = str(fm.get("title") or path.stem)
    for line in body.splitlines():
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            break
        if line.startswith("## "):
            title = line.removeprefix("## ").strip()
            break
    return [{
        "title": title,
        "url": str(fm.get("url") or fm.get("id") or ""),
        "content": body.strip(),
        "meta": f"source: {fm.get('source') or fm.get('source_name') or ''} · [link]({fm.get('url') or ''})",
        "published": str(fm.get("published_at") or fm.get("published") or ""),
        "source": str(fm.get("source") or fm.get("source_name") or ""),
    }]


def archive_item(path: Path, batch: str, sources: dict[str, dict], selected_urls: set[str] | None = None) -> int:
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    profile_id = str(fm.get("profile_id", "") or path.parent.name).strip()
    if not profile_id:
        profile_id = "unknown-profile"
    profile_name = str(fm.get("profile_name", "") or fm.get("source_name", "") or profile_id).strip()

    collected_date = _date_from_batch(batch)
    items_dir = library_date_dir(collected_date)
    archived = 0
    for item in markdown_items_for_archive(path, fm, body):
        if selected_urls is not None and item.get("url", "") not in selected_urls:
            continue
        source_name = item.get("source") or fm.get("source_name", profile_name)
        source = {
            **sources.get(source_name, {}),
            "name": source_name,
            "profile_id": profile_id,
            "platform": sources.get(source_name, {}).get("platform") or fm.get("platform", ""),
            "category": sources.get(source_name, {}).get("category") or fm.get("category", ""),
            "url": sources.get(source_name, {}).get("url") or item.get("url", ""),
        }
        item_fm = {
            "id": item.get("url", "") or item.get("title", ""),
            "profile_id": profile_id,
            "profile_name": profile_name,
            "source_name": source_name,
            "platform": source.get("platform", ""),
            "channel": channel_for_source(source),
            "url": item.get("url", ""),
            "published_at": item.get("published", ""),
            "batch_id": batch,
            "status": "archived",
            "collected_at": collected_date,
            "library_archived_at": datetime.now().isoformat(timespec="seconds"),
        }
        item_body = "\n".join(
            [
                f"# {item.get('title') or 'Untitled'}",
                "",
                item.get("meta", ""),
                "",
                item.get("content", "").strip(),
                "",
            ]
        )
        dest = items_dir / library_item_filename(collected_date, source, item)
        dest.write_text(render_frontmatter(item_fm) + item_body, encoding="utf-8")
        archived += 1
    return archived


def sources_by_profile() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for src in load_sources():
        profile = src.get("profile_id", "").strip()
        if not profile:
            continue
        grouped.setdefault(profile, []).append(src)
    return grouped


def recent_item_titles(profile_dir: Path, limit: int = 8) -> list[str]:
    items_dir = profile_dir / "items"
    if not items_dir.exists():
        return []
    candidates = sorted(items_dir.iterdir(), key=lambda p: p.name, reverse=True)
    titles = []
    for child in candidates:
        article = child / "article.md" if child.is_dir() else child
        if not article.exists() or not article.is_file():
            continue
        try:
            text = article.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("# "):
                titles.append(line.removeprefix("# ").strip())
                break
        if len(titles) >= limit:
            break
    return titles


def ensure_profile_baseline() -> None:
    grouped = sources_by_profile()
    for profile_id, sources in grouped.items():
        profile_dir = PROFILE_LIBRARY_DIR / profile_id
        if not profile_dir.exists():
            continue
        profile_name = sources[0].get("name", profile_id)
        profile_readme(profile_dir, profile_id, profile_name)
        path = profile_dir / "profile.md"
        text = path.read_text(encoding="utf-8")
        changed = False
        channels = "\n".join(
            f"- {src.get('platform', '')} · {src.get('name', '')} · {src.get('url', '')}"
            for src in sources
        )
        sections = {
            "## Channels": channels,
            "## Why Follow": "Tracked source for Daily Inbox signal. Use source-specific content and recent archive history to refine this description over time.",
            "## Default Handling Rules": "\n".join(
                [
                    "- Attribute every item to this profile.",
                    "- Keep source/channel in item metadata and filename, not in another folder layer.",
                    "- Every item enters scoring; source authority and user-curation are scoring context, not bypass rules.",
                ]
            ),
            "## Recent Baseline": "\n".join(f"- {title}" for title in recent_item_titles(profile_dir)) or "- Not enough archived items yet.",
        }
        for heading, body in sections.items():
            if heading not in text:
                text = text.rstrip() + f"\n\n{heading}\n\n{body}\n"
                changed = True
            elif heading == "## Channels":
                pattern = rf"{re.escape(heading)}\n\n(?:[\s\S]*?)(?=\n## |\Z)"
                replacement = f"{heading}\n\n{body}\n"
                new_text = re.sub(pattern, replacement, text)
                if new_text != text:
                    text = new_text
                    changed = True
        if changed:
            path.write_text(text, encoding="utf-8")


def batch_date_from_name(name: str) -> datetime | None:
    match = re.match(r"^(\d{2})-(\d{2})-(\d{2})", name)
    if not match:
        return None
    yy, mm, dd = match.groups()
    try:
        return datetime.strptime(f"20{yy}-{mm}-{dd}", "%Y-%m-%d")
    except ValueError:
        return None


def cleanup_old_processed(retention_hours: int = 72) -> int:
    cutoff = datetime.now() - timedelta(hours=retention_hours)
    removed = 0
    if not PROCESSED_DIR.exists():
        return removed
    for child in PROCESSED_DIR.iterdir():
        if not child.is_dir():
            continue
        day = batch_date_from_name(child.name)
        if day and day < cutoff:
            shutil.rmtree(child)
            removed += 1
    return removed


def main() -> int:
    batch = batch_label()
    root = processed_batch_dir()
    if not root.exists():
        log("archive-items", f"no processed batch to archive: {root}")
        return 0
    item_files = sorted(p for p in root.rglob("*.md") if not p.name.startswith("000-"))
    sources = source_index()
    selected_urls = selected_urls_from_ai(root)
    count = 0
    for path in item_files:
        try:
            count += archive_item(path, batch, sources, selected_urls)
        except Exception as ex:
            log("archive-items", f"  {path}: ERROR {type(ex).__name__}: {ex}")
    ensure_profile_baseline()
    removed = cleanup_old_processed()
    log("archive-items", f"DONE — archived {count} item(s) from {root}; removed {removed} old processed batch(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
