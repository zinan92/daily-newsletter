#!/usr/bin/env python3
"""Open a digest batch by moving pending raw files into processed/<batch>/."""
from pathlib import Path
import json
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import (
    UNPROCESSED_DIR,
    batch_id,
    log,
    parse_frontmatter,
    profile_id_for_source,
    processed_batch_dir,
    render_frontmatter,
    today,
)
from stages.coarse_filter.filter import filter_markdown_items


def merge_or_move(src: Path, dst: Path) -> None:
    if not dst.exists():
        src.rename(dst)
        return

    src_text = src.read_text(encoding="utf-8")
    dst_text = dst.read_text(encoding="utf-8")
    src_fm, src_body = parse_frontmatter(src_text)
    dst_fm, dst_body = parse_frontmatter(dst_text)
    try:
        count = int(dst_fm.get("items", "0") or 0) + int(src_fm.get("items", "0") or 0)
    except ValueError:
        count = 0
    if count:
        dst_fm["items"] = str(count)
    if src_fm.get("last_fetch"):
        dst_fm["last_fetch"] = src_fm["last_fetch"]
    merged = render_frontmatter(dst_fm) + dst_body.rstrip() + "\n\n" + src_body.strip() + "\n"
    dst.write_text(merged, encoding="utf-8")
    src.unlink()


def write_rejects(target: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path = target / "coarse-rejects.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def filtered_source_text(src: Path) -> tuple[str | None, list[dict]]:
    text = src.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    replacement, rejected = filter_markdown_items(body, fm, src)
    if replacement is None:
        return None, rejected
    if replacement == "":
        return "", rejected
    return replacement, rejected


def destination_for(src: Path, target: Path) -> Path:
    rel = src.relative_to(UNPROCESSED_DIR)
    if rel.parts and rel.parts[0].startswith("20") and len(rel.parts[0]) == 10:
        try:
            fm, _ = parse_frontmatter(src.read_text(encoding="utf-8"))
        except OSError:
            fm = {}
        profile = fm.get("profile_id") or profile_id_for_source(
            {
                "name": fm.get("source_name", src.stem),
                "profile_id": fm.get("profile_id", ""),
            }
        )
        return target / profile / src.name
    return target / rel


def main() -> int:
    bid = batch_id()
    today_str = today()
    legacy_prefix = today_str[2:]
    target = processed_batch_dir(bid)
    pending = []
    if UNPROCESSED_DIR.exists():
        dated_dir = UNPROCESSED_DIR / today_str
        if dated_dir.exists():
            pending.extend(sorted(p for p in dated_dir.rglob("*.md")))
        pending.extend(
            sorted(
                p
                for p in UNPROCESSED_DIR.glob("*.md")
                if p.name.startswith(legacy_prefix)
            )
        )

    if not pending:
        log("open-batch", "no pending raw files")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    moved = 0
    rejected_count = 0
    for src in pending:
        replacement, rejected = filtered_source_text(src)
        write_rejects(target, rejected)
        rejected_count += len(rejected)
        if replacement == "":
            src.unlink()
            continue
        if replacement is not None:
            src.write_text(replacement, encoding="utf-8")
        dst = destination_for(src, target)
        dst.parent.mkdir(parents=True, exist_ok=True)
        merge_or_move(src, dst)
        moved += 1

    dated_dir = UNPROCESSED_DIR / today_str
    if dated_dir.exists() and not any(dated_dir.rglob("*.md")):
        shutil.rmtree(dated_dir)

    log("open-batch", f"opened batch {bid}: moved {moved} processed file(s) to {target}; rejected {rejected_count} low-value item(s)")
    print(bid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
