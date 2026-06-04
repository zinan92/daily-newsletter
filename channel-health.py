#!/usr/bin/env python3
"""Truthful per-channel health, derived from FETCH LOGS (ground truth) + a freshness probe.

Why this exists: state.json / source-health collapsed three different situations
into one green "成功无新增":
  - DOWN   : the fetch errored (timeout / connection refused / auth-cookie expired)
  - STALE  : the fetch "succeeded" but the upstream feed is frozen (e.g. wewe-rss
             bridge answers, but its newest article is weeks old)
  - QUIET  : the fetch succeeded against a fresh source, there is simply nothing new
  - NEW    : n new items were ingested
A green "无新增" that actually means DOWN is the bug this module removes — the logs
record `ERROR ...` and `n NEW / m entries`, so we classify from those, not from
state stamps that lie.

States: DOWN · STALE · QUIET · NEW · UNKNOWN (channel absent from the latest run).
Run:  python3 channel-health.py            # truthful table
      python3 channel-health.py --json     # machine output
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone

from lib import ROOT, load_sources, today  # noqa: F401

STALE_AFTER_DAYS = 10  # a feed whose newest item is older than this is "frozen", not "quiet"

# platform -> fetcher log basename
LOG_FOR = {
    "rss": "fetch-rss",
    "scrape": "fetch-scrape",
    "twitter": "fetch-twitter",
    "douyin": "fetch-douyin",
    "wechat-rss": "fetch-wechat-rss",
}


def log_basename(src: dict) -> str:
    platform = src.get("platform", "")
    if platform == "wechat" and "rss_url " in src.get("notes", ""):
        return "fetch-wechat-rss"
    return LOG_FOR.get(platform, "fetch")


def channel_needle(src: dict) -> str:
    """How the channel identifies itself in its fetcher log line."""
    if src.get("platform") == "twitter":
        return "@" + src.get("url", "").rstrip("/").split("/")[-1]
    return src.get("name", "")


def last_channel_line(log_path, needle: str) -> str | None:
    """The channel's MOST RECENT outcome line across the whole log.

    We scan the full file (not just the latest START block) so a fetch still
    in progress — where later channels haven't logged yet — falls back to each
    channel's last completed result instead of showing a misleading UNKNOWN.
    A channel prints e.g. '20 fetched' then 'N NEW today' / 'ERROR ...', so we
    take the last line that carries an outcome (NEW / ERROR), else the last mention.
    """
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    outcome = mention = None
    for ln in lines:
        if f"{needle}:" in ln:
            mention = ln
            if "NEW" in ln or "ERROR" in ln:
                outcome = ln
    return outcome or mention


def parse_line(line: str) -> dict:
    """Extract outcome from one fetcher log line. Pure → testable."""
    if "ERROR" in line:
        err = line.split("ERROR", 1)[1].strip(" :") or "error"
        return {"error": err, "new": None, "seen": None}
    m_new = re.search(r"(\d+)\s*NEW", line)
    m_seen = re.search(r"NEW\s*/\s*(\d+)", line) or re.search(r"(\d+)\s*(?:total|entries)", line)
    new = int(m_new.group(1)) if m_new else None
    seen = int(m_seen.group(1)) if m_seen else None
    return {"error": None, "new": new, "seen": seen}


def classify(parsed: dict | None, feed_age_days: int | None) -> str:
    """Map (parsed log outcome, optional feed freshness) → state. Pure → testable."""
    if parsed is None:
        return "UNKNOWN"
    if parsed.get("error"):
        return "DOWN"
    if feed_age_days is not None and feed_age_days > STALE_AFTER_DAYS:
        return "STALE"
    if parsed.get("new"):
        return "NEW"
    return "QUIET"


def pending_setup_error(src: dict) -> str | None:
    """Return an actionable setup error for active WeChat rows with no RSS feed yet."""
    if src.get("platform") != "wechat":
        return None
    notes = src.get("notes", "") or ""
    m = re.search(r"rss_url\s+pending\b[^|]*", notes, flags=re.I)
    if not m:
        return None
    return f"WeWe RSS 未配置：{m.group(0).strip()}"


def classify_source(src: dict, parsed: dict | None, feed_age_days: int | None) -> dict:
    pending = pending_setup_error(src)
    if pending:
        return {"state": "DOWN", "error": pending}
    return {"state": classify(parsed, feed_age_days), "error": (parsed or {}).get("error")}


def feed_age_days(src: dict) -> int | None:
    """For wechat-rss channels: age (days) of the newest item in the bridge feed.
    Detects a frozen bridge that still answers 200. None if not probeable."""
    if not (src.get("platform") == "wechat" and "rss_url " in src.get("notes", "")):
        return None
    m = re.search(r"rss_url\s+(https?://\S+)", src.get("notes", ""))
    if not m:
        return None
    try:
        with urllib.request.urlopen(m.group(1), timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        items = data.get("items") or []
        if not items:
            return 9999
        raw = items[0].get("date_modified") or items[0].get("date_published") or ""
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None  # probe failed → don't assert staleness (the run-state already covers DOWN)


def channel_rows() -> list[dict]:
    rows = []
    for src in load_sources():
        if src.get("active") not in (None, "true", True):
            continue
        platform = src.get("platform", "")
        if platform not in {"rss", "scrape", "twitter", "douyin", "wechat"}:
            continue
        log_path = ROOT / "logs" / f"{log_basename(src)}.log"
        line = last_channel_line(log_path, channel_needle(src))
        parsed = parse_line(line) if line else None
        age = feed_age_days(src)
        classified = classify_source(src, parsed, age)
        state = classified["state"]
        rows.append({
            "name": src.get("name", ""),
            "platform": platform,
            "state": state,
            "new": (parsed or {}).get("new"),
            "seen": (parsed or {}).get("seen"),
            "feed_age_days": age,
            "error": classified.get("error"),
            "evidence": (line or "未在最近一轮 fetch 出现").strip(),
        })
    return rows


def states_by_name() -> dict[str, dict]:
    """Per-source truthful health keyed by source name — for status.html / digest to consume."""
    return {r["name"]: r for r in channel_rows()}


_ICON = {"DOWN": "🔴", "STALE": "🟠", "QUIET": "⚪", "NEW": "🟢", "UNKNOWN": "❓"}
_ORDER = {"DOWN": 0, "STALE": 1, "UNKNOWN": 2, "NEW": 3, "QUIET": 4}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = sorted(channel_rows(), key=lambda r: (_ORDER.get(r["state"], 9), r["platform"], r["name"]))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    from collections import Counter
    tally = Counter(r["state"] for r in rows)
    print(f"渠道健康（来自 fetch 日志真值 + 新鲜度探测）— {today()}")
    print("  " + " · ".join(f"{_ICON[s]}{s} {tally[s]}" for s in ["DOWN", "STALE", "QUIET", "NEW", "UNKNOWN"] if tally[s]))
    print("-" * 78)
    def freshness(r):
        a = r["feed_age_days"]
        return "feed 空/无此号" if a == 9999 else (f"feed {a}d 前" if a not in (None, 0) else "")
    for r in rows:
        detail = r["error"] or freshness(r) or (f"{r['new']} new" if r["new"] else "0 new")
        print(f"  {_ICON[r['state']]} {r['state']:7} [{r['platform']:8}] {r['name'][:18]:18} {detail}")
    down = [r for r in rows if r["state"] in ("DOWN", "STALE")]
    if down:
        print("-" * 78)
        print(f"⚠ 需处理 {len(down)} 个渠道（挂了 / feed 冻结，不是没更新）：")
        for r in down:
            why = r["error"] or freshness(r) or "feed 冻结"
            print(f"    {_ICON[r['state']]} {r['name']} — {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
