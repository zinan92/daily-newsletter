#!/usr/bin/env python3
"""fetch-twitter-home.py — Park's own X home timeline as a source, twice a day.

The 26 tracked X accounts see what they post; the home timeline sees what
*everyone Park follows* is talking about. Jev and Hypit spread there first.
This lane exists to feed "many people are saying it" signals (term radar) and
the daily batch, not to read every tweet:

- following (chronological) and for-you (algorithmic) feeds are merged.
- Tweets by accounts already in sources.md are skipped (fetched separately).
- Retweets collapse to the original tweet id; seen ids roll off after
  48 hours so a tweet surfacing in both feeds or both runs is written once.
- Every post is written to raw (the term radar counts small accounts too);
  posts with likes below PARKIO_X_HOME_MIN_LIKES (default 20) are tagged
  category ai-timeline-low, which the coarse filter keeps out of the AI batch.

Schedule: launchd runs this at 02:00, 08:00, 14:00 and 20:00 (Park,
2026-09-18: one pull sees at most ~200 following + ~170 for-you posts, so two
pulls a day cannot cover the timeline). The 02:00 and 08:00 runs land in
raw/<today>/ and are normalized by the 08:30 batch; the 14:00 and 20:00 runs
are normalized the next morning (to_md looks back one day) and drained by the
coarse filter (#17), so no run is lost.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.x.timeline import (  # noqa: E402
    is_rate_limited_error,
    load_twitter_env,
    tweet_author,
    tweet_handle,
    tweet_id,
    tweet_local_date,
    tweet_metrics,
    tweet_text,
    unwrap_tweet,
)
from lib import load_sources, load_state, log, save_state, write_source_output  # noqa: E402

TWITTER_BIN = os.environ.get("PARKIO_TWITTER_BIN", str(Path.home() / ".local/bin/twitter"))
STATE_KEY = "twitter-home:X 首页时间线"
MIN_LIKES = int(os.environ.get("PARKIO_X_HOME_MIN_LIKES", "20") or "20")
FOLLOWING_MAX = int(os.environ.get("PARKIO_X_HOME_FOLLOWING_MAX", "150") or "150")
FOR_YOU_MAX = int(os.environ.get("PARKIO_X_HOME_FOR_YOU_MAX", "100") or "100")
SEEN_HOURS = 48
HOME_SOURCE = {
    "id": "x-home",
    "profile_id": "x-home",
    "name": "X 首页时间线",
    "profile_name": "X 首页时间线",
    "platform": "twitter",
    "url": "https://x.com/home",
    "category": "ai-timeline",
    "priority": "high",
    "frequency": "12h",
    "active": "true",
}


def feed(kind: str, max_count: int) -> list[dict]:
    load_twitter_env()
    result = subprocess.run(
        [TWITTER_BIN, "feed", "-t", kind, "-n", str(max_count), "--json"],
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"twitter-cli exit={result.returncode}: {result.stderr.strip()[:300]}")
    payload = json.loads(result.stdout)
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"] or []
    return payload or []


def tracked_handles(sources: list[dict] | None = None) -> set[str]:
    handles: set[str] = set()
    for src in sources if sources is not None else load_sources():
        if src.get("platform") != "twitter":
            continue
        path = urllib.parse.urlparse(str(src.get("url") or "")).path.lstrip("/")
        handle = path.split("/")[0].lower()
        if handle and handle != "home":
            handles.add(handle)
    return handles


def original_tweet(tweet: dict) -> dict:
    """A retweet counts as its original tweet, so the same post is written once."""
    if tweet.get("isRetweet"):
        for key in ("retweetedStatus", "retweeted_status", "retweet", "retweetedTweet"):
            nested = unwrap_tweet(tweet.get(key))
            if isinstance(nested, dict) and tweet_id(nested):
                return nested
    return tweet


def prune_seen(seen: dict[str, str], now: datetime, hours: int = SEEN_HOURS) -> dict[str, str]:
    cutoff = (now - timedelta(hours=hours)).isoformat(timespec="seconds")
    return {tid: stamp for tid, stamp in seen.items() if stamp >= cutoff}


def select_tweets(
    tweets: list[dict],
    *,
    tracked: set[str],
    seen: dict[str, str],
    min_likes: int = MIN_LIKES,
    now: datetime | None = None,
) -> tuple[list[dict], dict[str, int]]:
    """Filter merged feed tweets into items; returns (items, reasons counter)."""
    now = now or datetime.now()
    stamp = now.isoformat(timespec="seconds")
    reasons = {"tracked_account": 0, "low_engagement": 0, "seen": 0, "empty": 0, "kept": 0}
    items: list[dict] = []
    picked: set[str] = set()
    for raw in tweets:
        tweet = original_tweet(raw)
        tid = tweet_id(tweet)
        if not tid:
            continue
        handle = tweet_handle(tweet, "").lower()
        if handle in tracked:
            reasons["tracked_account"] += 1
            continue
        metrics = tweet_metrics(tweet)
        low_engagement = int(metrics["likes"] or 0) < min_likes
        if low_engagement:
            reasons["low_engagement"] += 1
        if tid in seen or tid in picked:
            reasons["seen"] += 1
            continue
        text = tweet_text(tweet)
        if not text:
            reasons["empty"] += 1
            continue
        picked.add(tid)
        seen[tid] = stamp
        reasons["kept"] += 1
        items.append(
            {
                "id": tid,
                "url": f"https://x.com/{handle or 'i'}/status/{tid}",
                "text": text,
                "author": tweet_author(tweet, handle),
                "handle": handle,
                "conversation_id": tid,
                "time": tweet.get("createdAtLocal") or tweet.get("createdAtISO") or "",
                "published": tweet_local_date(tweet) or now.strftime("%Y-%m-%d"),
                "likes": metrics["likes"],
                "rts": metrics["rts"],
                "feed": raw.get("_feed", ""),
                # Low-engagement posts still count for the term radar (many
                # small accounts saying "Hypit" IS the signal), but they must
                # not enter the AI batch: the coarse filter rejects this category.
                "category": "ai-timeline-low" if low_engagement else "ai-timeline",
            }
        )
    return items, reasons


def main() -> int:
    state = load_state()
    entry = state.get(STATE_KEY, {})
    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    seen = prune_seen(dict(entry.get("seen") or {}), now)
    log("fetch-twitter-home", f"START — min_likes={MIN_LIKES}")
    merged: list[dict] = []
    errors: list[str] = []
    for kind, limit in (("following", FOLLOWING_MAX), ("for-you", FOR_YOU_MAX)):
        try:
            rows = feed(kind, limit)
            for row in rows:
                row["_feed"] = kind
            merged.extend(rows)
            log("fetch-twitter-home", f"  {kind}: {len(rows)} fetched")
        except Exception as ex:
            error = f"{type(ex).__name__}: {ex}"
            errors.append(f"{kind}: {error}")
            log("fetch-twitter-home", f"  {kind}: ERROR {error}")
    if not merged and errors:
        rate_limited = all(is_rate_limited_error(e) for e in errors)
        state[STATE_KEY] = {
            **entry,
            "last_fetch": day,
            "status": "failed",
            "error": "; ".join(errors),
            "seen": seen,
            "detail": "rate limited on both feeds" if rate_limited else "both feeds failed",
        }
        save_state(state)
        log("fetch-twitter-home", "DONE (failed)")
        return 0
    items, reasons = select_tweets(merged, tracked=tracked_handles(), seen=seen, now=now)
    if items:
        write_source_output(HOME_SOURCE, items)
    state[STATE_KEY] = {
        "last_fetch": day,
        "last_run_at": now.isoformat(timespec="seconds"),
        "status": "ok_new" if items else "ok_no_new",
        "fetched_count": len(merged),
        "new_count": len(items),
        "detail": (
            f"home feeds checked; {len(items)} new item(s) from {len(merged)} fetched "
            f"(tracked {reasons['tracked_account']}, low-engagement {reasons['low_engagement']}, seen {reasons['seen']})"
            + (f"; partial: {'; '.join(errors)}" if errors else "")
        ),
        "seen": seen,
    }
    save_state(state)
    log("fetch-twitter-home", f"  kept {len(items)} / {len(merged)}; {reasons}")
    log("fetch-twitter-home", "DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
