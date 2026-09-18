#!/usr/bin/env python3
"""Three-layer coverage ledger: fetched → batched → published, one row per day.

Answers "of what we fetched on day D, how much entered a batch and how much
reached the reader?" and lists the backlog no batch has drained. A miss like
Jev (fetched, never batched) and a miss like Hypit (never fetched) then show
up on different layers instead of both reading as "the newsletter missed it".

Layers, all keyed by normalized item URL:
  fetched    raw/<D>/<profile>/*.json          (Stage 1 output)
  batched    processed/<label>*/ai/00-input-items.json  (what Stage 4 actually read)
  published  006_ai daily newsletter/<label>*.md        (what the reader got)

Run: python3 coverage_ledger.py --date 2026-09-17 [--write]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import PROCESSED_DIR, RAW_DIR, SENT_DIR, SOURCE_MANAGEMENT_DIR, UNPROCESSED_DIR, today  # noqa: E402

LEDGER_PATH = SOURCE_MANAGEMENT_DIR / "coverage-ledger.jsonl"
NON_ITEM_RAW = {"product-radar.json"}
URL_RE = re.compile(r"https?://[^\s)\]>\"']+")


def normalize_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return ""
    url = url.split("#", 1)[0]
    if "x.com/" in url or "twitter.com/" in url:
        url = url.split("?", 1)[0]
        url = url.replace("twitter.com/", "x.com/")
    return url.rstrip("/").lower()


def label_for(date: str) -> str:
    return date[2:]


def fetched_layer(date: str, raw_dir: Path | None = None) -> tuple[dict[str, str], Counter[str]]:
    """URL → profile for every raw item fetched on `date`, plus per-profile counts."""
    root = (raw_dir or RAW_DIR) / date
    urls: dict[str, str] = {}
    by_profile: Counter[str] = Counter()
    if not root.exists():
        return urls, by_profile
    for path in sorted(root.rglob("*.json")):
        if path.name.endswith(".to-md.json") or path.name in NON_ITEM_RAW:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        try:
            profile = path.parent.relative_to(root).parts[0]
        except (ValueError, IndexError):
            profile = path.parent.name
        url = normalize_url(data.get("url") or data.get("id") or path.stem)
        if not url:
            continue
        urls[url] = profile
        by_profile[profile] += 1
    return urls, by_profile


def batched_layer(date: str, processed_dir: Path | None = None) -> tuple[set[str], list[str]]:
    """URLs Stage 4 read in any batch labelled for `date` (morning, 晚, backfill…)."""
    base = processed_dir or PROCESSED_DIR
    label = label_for(date)
    urls: set[str] = set()
    batches: list[str] = []
    if not base.exists():
        return urls, batches
    for batch_dir in sorted(base.glob(f"{label}*")):
        if not batch_dir.is_dir():
            continue
        batches.append(batch_dir.name)
        inputs = batch_dir / "ai" / "00-input-items.json"
        if inputs.exists():
            try:
                rows = json.loads(inputs.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                rows = []
            for row in rows if isinstance(rows, list) else []:
                url = normalize_url((row or {}).get("url") or (row or {}).get("id"))
                if url:
                    urls.add(url)
            continue
        # Batch opened but AI stage not run yet: count the item files.
        for md in batch_dir.rglob("*.md"):
            if md.name.startswith(("000-", "deep-", "product-radar-", "review-")) or "ai" in md.relative_to(batch_dir).parts[:1]:
                continue
            match = re.search(r"^url:\s*(\S+)", md.read_text(encoding="utf-8", errors="replace"), flags=re.M)
            if match:
                urls.add(normalize_url(match.group(1)))
    return urls, batches


def published_layer(date: str, sent_dir: Path | None = None) -> tuple[set[str], list[str]]:
    """URLs that appear in the reader-facing newsletter files for `date`."""
    base = sent_dir or SENT_DIR
    label = label_for(date)
    urls: set[str] = set()
    files: list[str] = []
    if not base.exists():
        return urls, files
    for md in sorted(base.glob(f"{label}*.md")):
        files.append(md.name)
        for url in URL_RE.findall(md.read_text(encoding="utf-8", errors="replace")):
            urls.add(normalize_url(url))
    return urls, files


def backlog_layer(as_of: str, unprocessed_dir: Path | None = None) -> dict[str, int]:
    """Items still sitting in unprocessed/<day>/ for days on or before `as_of`."""
    base = unprocessed_dir or UNPROCESSED_DIR
    out: dict[str, int] = {}
    if not base.exists():
        return out
    for child in sorted(base.iterdir()):
        if not child.is_dir() or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", child.name) or child.name > as_of:
            continue
        count = sum(1 for _ in child.rglob("*.md"))
        if count:
            out[child.name] = count
    return out


def ratio(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def build_ledger_row(
    date: str,
    *,
    as_of: str | None = None,
    raw_dir: Path | None = None,
    processed_dir: Path | None = None,
    sent_dir: Path | None = None,
    unprocessed_dir: Path | None = None,
) -> dict[str, Any]:
    as_of = as_of or today()
    fetched, by_profile = fetched_layer(date, raw_dir)
    batched_all, batches = batched_layer(date, processed_dir)
    published_all, files = published_layer(date, sent_dir)
    backlog = backlog_layer(as_of, unprocessed_dir)

    fetched_urls = set(fetched)
    batched = fetched_urls & batched_all
    published = fetched_urls & published_all
    missed = sorted(fetched_urls - batched_all)
    stale_days = sorted(day for day in backlog if day < as_of)
    missed_by_profile: Counter[str] = Counter(fetched[url] for url in missed)

    return {
        "date": date,
        "as_of": as_of,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "fetched": len(fetched_urls),
        "fetched_by_profile": dict(sorted(by_profile.items())),
        "batched": len(batched),
        "batches": batches,
        "published": len(published),
        "published_total_urls": len(published_all),
        "newsletter_files": files,
        "batch_rate": ratio(len(batched), len(fetched_urls)),
        "publish_rate": ratio(len(published), len(batched)),
        "never_batched": len(missed),
        "never_batched_by_profile": dict(missed_by_profile.most_common()),
        "never_batched_examples": missed[:10],
        "pending_backlog": backlog,
        "stale_backlog": bool(stale_days),
        "stale_days": stale_days,
    }


def render_markdown(row: dict[str, Any]) -> str:
    def pct(value: float | None) -> str:
        return "—" if value is None else f"{value * 100:.0f}%"

    lines = [
        f"## 覆盖率 · {row['date']}",
        "",
        f"抓到 {row['fetched']} → 进批 {row['batched']}（{pct(row['batch_rate'])}）→ 进日报 {row['published']}（{pct(row['publish_rate'])}）",
    ]
    if row["never_batched"]:
        top = "、".join(f"{k} {v}" for k, v in list(row["never_batched_by_profile"].items())[:5])
        if row["date"] == row["as_of"]:
            lines.append(f"今天批处理之后抓到 {row['never_batched']} 条（明早进批）：{top}")
        else:
            lines.append(f"从未进批 {row['never_batched']} 条：{top}")
    backlog = row["pending_backlog"]
    if backlog:
        shown = list(backlog.items())[-5:]
        days = "、".join(f"{d} {n}" for d, n in shown)
        total = sum(backlog.values())
        more = f"（共 {len(backlog)} 天 {total} 条）" if len(backlog) > len(shown) else ""
        flag = "，其中有超期积压，批处理没读到" if row["stale_backlog"] else ""
        lines.append(f"待处理积压：{days}{more}{flag}")
    else:
        lines.append("待处理积压：0")
    return "\n".join(lines) + "\n"


def append_ledger(row: dict[str, Any], path: Path | None = None) -> Path:
    """One row per date; a rerun for the same date replaces the earlier row."""
    path = path or LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if existing.get("date") != row["date"]:
                rows.append(existing)
    rows.append(row)
    rows.sort(key=lambda r: str(r.get("date", "")))
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetched → batched → published coverage for one day.")
    parser.add_argument("--date", default=today())
    parser.add_argument("--as-of", default=None, help="Day the backlog is judged against (default: today)")
    parser.add_argument("--write", action="store_true", help="Append/replace the row in coverage-ledger.jsonl")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    args = parser.parse_args(argv)
    row = build_ledger_row(args.date, as_of=args.as_of)
    if args.write:
        append_ledger(row)
    print(json.dumps(row, ensure_ascii=False, indent=2) if args.json else render_markdown(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
