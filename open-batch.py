#!/usr/bin/env python3
"""Open a digest batch by moving pending raw files into processed/<batch>/."""
from pathlib import Path
import shutil

from lib import (
    PROCESSED_DIR,
    UNPROCESSED_DIR,
    batch_id,
    log,
    parse_frontmatter,
    profile_id_for_source,
    processed_batch_dir,
    render_frontmatter,
)


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
    target = processed_batch_dir(bid)
    pending = []
    if UNPROCESSED_DIR.exists():
        pending.extend(sorted(p for p in UNPROCESSED_DIR.rglob("*.md")))

    if not pending:
        log("open-batch", "no pending raw files")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    moved = 0
    for src in pending:
        dst = destination_for(src, target)
        dst.parent.mkdir(parents=True, exist_ok=True)
        merge_or_move(src, dst)
        moved += 1

    for child in sorted(UNPROCESSED_DIR.iterdir()) if UNPROCESSED_DIR.exists() else []:
        if child.is_dir():
            shutil.rmtree(child)

    log("open-batch", f"opened batch {bid}: moved {moved} raw file(s) to {target}")
    print(bid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
