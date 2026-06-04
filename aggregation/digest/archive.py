#!/usr/bin/env python3
"""Archive processed item files into the long-term profile library."""
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import (
    INDEPENDENT_LINKS_DIR,
    PROFILE_LIBRARY_DIR,
    PROCESSED_DIR,
    batch_label,
    item_filename,
    load_sources,
    log,
    parse_frontmatter,
    parse_md_items,
    processed_batch_dir,
    render_frontmatter,
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


def archive_item(path: Path, batch: str, sources: dict[str, dict]) -> int:
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    profile_id = str(fm.get("profile_id", "") or path.parent.name).strip()
    if not profile_id:
        profile_id = "unknown-profile"
    profile_name = str(fm.get("profile_name", "") or fm.get("source_name", "") or profile_id).strip()

    if profile_id in {"unknown-profile", "x-saved", "manual-link"}:
        items_dir = INDEPENDENT_LINKS_DIR
        items_dir.mkdir(parents=True, exist_ok=True)
    else:
        profile_dir = PROFILE_LIBRARY_DIR / profile_id
        items_dir = profile_dir / "items"
        items_dir.mkdir(parents=True, exist_ok=True)
        profile_readme(profile_dir, profile_id, profile_name)

    archived = 0
    for item in parse_md_items(body):
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
            "url": item.get("url", ""),
            "published_at": item.get("published", ""),
            "batch_id": batch,
            "status": "archived",
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
        dest = items_dir / item_filename(source, item)
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
                    "- User-curated podcast, YouTube, Douyin, WeChat, and saved X items bypass score filtering.",
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
    count = 0
    for path in item_files:
        try:
            count += archive_item(path, batch, sources)
        except Exception as ex:
            log("archive-items", f"  {path}: ERROR {type(ex).__name__}: {ex}")
    ensure_profile_baseline()
    removed = cleanup_old_processed()
    log("archive-items", f"DONE — archived {count} item(s) from {root}; removed {removed} old processed batch(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
