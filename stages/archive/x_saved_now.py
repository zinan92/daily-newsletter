#!/usr/bin/env python3
"""X 收藏当小时进 002_个人收藏，不等第二天早上的日报。

Park 9/28：白天在 X 上收藏了一批文章，工作台「我收藏的」里一条都没有——抓取每小时都在跑，
但写进 002 只在 08:30 日报那趟的 archive 里，下午收藏的要到第二天早上才出现。

这一步跟在 fetch-all.sh 的抓取后面：读今天和昨天 raw/<date>/x-saved/ 里的 JSON，
还没进 002 的（按推文 URL 判断）用和早上完全相同的 archive_item 写进去，然后重建索引。

- 只读 raw，不写 to_md 的 .to-md.json 标记：早上的 to_md → 日报照常能看到这些收藏。
- 早上 archive 遇到已经归档过的 URL 会跳过，不会按新日期再写一份。
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import RAW_DIR, batch_label, log
from ingestion.collection_index import existing_collection_path_for_url, rebuild_collection_index
from stages.archive.run import archive_item, source_index
from stages.to_md.run import normalize_record, render_item_markdown

SAVED_FOLDER = "x-saved"
LOOKBACK_DAYS = 1


def raw_saved_files(raw_dir: Path | None = None, *, now: datetime | None = None) -> list[Path]:
    base = raw_dir or RAW_DIR
    now = now or datetime.now()
    files: list[Path] = []
    for back in range(LOOKBACK_DAYS, -1, -1):
        folder = base / (now - timedelta(days=back)).strftime("%Y-%m-%d") / SAVED_FOLDER
        if folder.is_dir():
            files.extend(sorted(folder.glob("*.json")))
    return files


def archive_saved(files: list[Path], *, batch: str | None = None) -> int:
    batch = batch or batch_label()
    sources = source_index()
    count = 0
    with tempfile.TemporaryDirectory() as tmp:
        item = Path(tmp) / "item.md"
        for path in files:
            try:
                record = normalize_record(path)
            except (OSError, ValueError) as ex:
                log("x-saved-now", f"  {path.name}: skip {type(ex).__name__}: {ex}")
                continue
            if not record["url"] or existing_collection_path_for_url(record["url"]) is not None:
                continue
            item.write_text(render_item_markdown(record), encoding="utf-8")
            count += archive_item(item, batch, sources)
    return count


def main() -> int:
    count = archive_saved(raw_saved_files())
    if count:
        rebuild_collection_index()
    log("x-saved-now", f"DONE — archived {count} new X saved item(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
