#!/usr/bin/env python3
"""Fetch the user's own X bookmarks/likes as a personal saved-items source."""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import ROOT, inbox_dir, load_sources, now_utc, safe_filename, write_source_output, log

TWITTER_BIN = "/Users/wendy/.local/bin/twitter"
TWITTER_AUTH_ENV = "/Users/wendy/work/input-to-park/twitter-auth.env"
DB_PATH = ROOT / "x-saved-items.json"
STATE_PATH = ROOT / "x-saved-state.json"
CANDIDATES_PATH = ROOT / "x-saved-source-candidates.json"
MAX_BOOKMARKS = int(os.environ.get("PARKIO_X_BOOKMARK_MAX", "30"))
MAX_LIKES = int(os.environ.get("PARKIO_X_LIKE_MAX", "20"))
SELF_HANDLE = os.environ.get("PARKIO_X_SELF_HANDLE", "xparkzz")
BACKFILL_RECENT_BOOKMARKS = int(os.environ.get("PARKIO_X_BACKFILL_RECENT_BOOKMARKS", "0") or "0")


def load_twitter_env() -> None:
    if not os.path.exists(TWITTER_AUTH_ENV):
        return
    with open(TWITTER_AUTH_ENV, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in {"TWITTER_AUTH_TOKEN", "TWITTER_CT0", "TWITTER_BROWSER", "TWITTER_CHROME_PROFILE"}:
                os.environ.setdefault(key, value)


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def twitter_json(args: list[str]) -> list[dict]:
    load_twitter_env()
    cmd = [TWITTER_BIN, *args, "--json"]
    result = None
    for attempt in range(2):
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=os.environ.copy(),
        )
        if result.returncode == 0:
            break
        if attempt == 0 and "Getting Twitter cookies" in (result.stderr or ""):
            continue
        break
    if result.returncode != 0:
        raise RuntimeError(f"twitter-cli exit={result.returncode}: {result.stderr.strip()[:500]}")
    payload = json.loads(result.stdout)
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, list):
        return payload
    return []


def twitter_article(tweet_id: str) -> dict:
    if not tweet_id:
        return {}
    load_twitter_env()
    result = subprocess.run(
        [TWITTER_BIN, "article", str(tweet_id), "--json"],
        capture_output=True,
        text=True,
        timeout=60,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    data = payload.get("data") if isinstance(payload, dict) else payload
    return data if isinstance(data, dict) else {}


def tweet_local_date(tweet: dict) -> str:
    dt = str(tweet.get("createdAtLocal") or tweet.get("createdAtISO") or "")
    if len(dt) >= 10 and dt[:4].isdigit():
        return dt[:10]
    return ""


def author_name(tweet: dict) -> str:
    author = tweet.get("author")
    if isinstance(author, dict):
        return author.get("name") or author.get("screenName") or "unknown"
    return str(author or "unknown")


def author_handle(tweet: dict) -> str:
    author = tweet.get("author")
    if isinstance(author, dict):
        return author.get("screenName") or ""
    return ""


def tweet_url(tweet: dict) -> str:
    handle = author_handle(tweet)
    tid = str(tweet.get("id", ""))
    if handle and tid:
        return f"https://x.com/{handle}/status/{tid}"
    return ""


def one_line(text: str) -> str:
    return " ".join(str(text or "").split())


def tweet_id(tweet: dict) -> str:
    return str(tweet.get("id") or tweet.get("id_str") or tweet.get("rest_id") or "")


def article_text_for(tweet: dict) -> str:
    title = one_line(tweet.get("articleTitle") or tweet.get("title"))
    text = one_line(tweet.get("articleText") or tweet.get("article_text"))
    if not text:
        article = twitter_article(tweet_id(tweet))
        title = title or one_line(article.get("articleTitle") or article.get("title"))
        text = one_line(article.get("articleText") or article.get("text"))
    if not text:
        return ""
    return f"文章标题：{title}\n\n{text}" if title else text


def nested_tweet(tweet: dict) -> tuple[str, dict] | None:
    for key in ("quotedTweet", "quoted_status", "quotedStatus", "retweetedStatus", "retweeted_status", "retweet"):
        nested = tweet.get(key)
        if isinstance(nested, dict):
            label = "转发" if "retweet" in key.lower() else "引用"
            return label, nested
    return None


def content_for(tweet: dict, kind: str) -> str:
    parts = []
    article = article_text_for(tweet)
    text = one_line(tweet.get("text", ""))
    if article:
        parts.append(article)
    if text and text != "https://t.co/":
        parts.append(text)
    nested = nested_tweet(tweet)
    if nested:
        label, quoted = nested
        quoted_article = article_text_for(quoted)
        quoted_text = quoted_article or one_line(quoted.get("text", ""))
        quoted_author = quoted.get("author") or {}
        quoted_name = quoted_author.get("name") if isinstance(quoted_author, dict) else ""
        if quoted_text:
            prefix = f"{label} {quoted_name}：" if quoted_name else f"{label}内容："
            parts.append(prefix + quoted_text)
    urls = [u for u in tweet.get("urls", []) if isinstance(u, str)]
    if urls:
        parts.append("链接：" + " ".join(urls[:5]))
    metrics = tweet.get("metrics") or {}
    metric_text = []
    if metrics.get("bookmarks"):
        metric_text.append(f"bookmarks {metrics.get('bookmarks')}")
    if metrics.get("likes"):
        metric_text.append(f"likes {metrics.get('likes')}")
    if metrics.get("views"):
        metric_text.append(f"views {metrics.get('views')}")
    if metric_text:
        parts.append("公开互动：" + " · ".join(metric_text))
    if kind == "like":
        parts.append("这是你点赞保存的内容。")
    else:
        parts.append("这是你主动收藏的内容。")
    return "\n\n".join(parts).strip()


def item_from_tweet(tweet: dict, kind: str) -> dict:
    metrics = tweet.get("metrics") or {}
    return {
        "id": str(tweet.get("id", "")),
        "url": tweet_url(tweet),
        "text": content_for(tweet, kind),
        "author": author_name(tweet),
        "handle": author_handle(tweet),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "likes": metrics.get("likes", 0) or 0,
        "rts": metrics.get("retweets", 0) or 0,
        "saved_kind": kind,
        "tweet_created_at": tweet.get("createdAtISO") or tweet.get("createdAtLocal") or "",
    }


def tracked_handles() -> set[str]:
    handles = set()
    for src in load_sources():
        if src.get("platform") != "twitter":
            continue
        url = src.get("url", "")
        handle = url.rstrip("/").split("/")[-1].lower()
        if handle:
            handles.add(handle)
    return handles


def update_candidates(db: dict) -> None:
    tracked = tracked_handles()
    authors: dict[str, dict] = {}
    for record in db.values():
        handle = str(record.get("handle", "")).lower()
        if not handle:
            continue
        entry = authors.setdefault(
            handle,
            {
                "handle": handle,
                "name": record.get("author", handle),
                "saved_count": 0,
                "bookmark_count": 0,
                "like_count": 0,
                "already_tracked": handle in tracked,
                "latest_url": record.get("url", ""),
                "latest_first_seen_at": record.get("first_seen_at", ""),
            },
        )
        entry["saved_count"] += 1
        if record.get("saved_kind") == "bookmark":
            entry["bookmark_count"] += 1
        if record.get("saved_kind") == "like":
            entry["like_count"] += 1
        if str(record.get("first_seen_at", "")) > str(entry.get("latest_first_seen_at", "")):
            entry["latest_url"] = record.get("url", "")
            entry["latest_first_seen_at"] = record.get("first_seen_at", "")
    candidates = sorted(
        authors.values(),
        key=lambda x: (x["already_tracked"], -x["bookmark_count"], -x["saved_count"], x["handle"]),
    )
    save_json(CANDIDATES_PATH, candidates)


def main() -> None:
    db: dict = load_json(DB_PATH, {})
    source_state: dict = load_json(STATE_PATH, {})
    bootstrapped = set(source_state.get("bootstrapped_kinds", []))
    seen_this_run = set()
    new_items = []
    now = now_utc()

    commands = [
        ("bookmark", ["bookmarks", "-n", str(MAX_BOOKMARKS)]),
        ("like", ["likes", SELF_HANDLE, "-n", str(MAX_LIKES)]),
    ]
    log("fetch-twitter-saved", "START")
    for kind, args in commands:
        try:
            tweets = twitter_json(args)
            log("fetch-twitter-saved", f"  {kind}: {len(tweets)} fetched")
        except Exception as ex:
            log("fetch-twitter-saved", f"  {kind}: ERROR {type(ex).__name__}: {ex}")
            continue
        for index, tweet in enumerate(tweets):
            tid = str(tweet.get("id", ""))
            if not tid or tid in seen_this_run:
                continue
            seen_this_run.add(tid)
            url = tweet_url(tweet)
            if not url:
                continue
            is_new = tid not in db
            record = {
                "id": tid,
                "url": url,
                "author": author_name(tweet),
                "handle": author_handle(tweet),
                "saved_kind": kind,
                "tweet_created_date": tweet_local_date(tweet),
                "tweet_created_at": tweet.get("createdAtISO") or tweet.get("createdAtLocal") or "",
                "first_seen_at": db.get(tid, {}).get("first_seen_at", now),
                "last_seen_at": now,
                "text": tweet.get("text", ""),
                "articleTitle": tweet.get("articleTitle", ""),
                "urls": tweet.get("urls", []),
                "metrics": tweet.get("metrics", {}),
            }
            db[tid] = record
            backfill_item = kind == "bookmark" and BACKFILL_RECENT_BOOKMARKS > 0 and index < BACKFILL_RECENT_BOOKMARKS
            if not is_new and not backfill_item:
                continue
            # Delta is based on the local saved-item database, not tweet publish time.
            # First run per saved kind only establishes the baseline.
            if backfill_item or kind in bootstrapped:
                new_items.append(item_from_tweet(tweet, kind))
        bootstrapped.add(kind)

    save_json(DB_PATH, db)
    save_json(STATE_PATH, {"bootstrapped_kinds": sorted(bootstrapped), "last_fetch": now})
    update_candidates(db)

    if new_items:
        source = {
            "id": "901",
            "name": "我的 X 收藏",
            "platform": "twitter",
            "category": "personal-saved",
            "url": "https://x.com/i/bookmarks",
        }
        if BACKFILL_RECENT_BOOKMARKS > 0:
            out = inbox_dir() / f"{source['id']}-{safe_filename(source['name'])}.md"
            if out.exists():
                out.unlink()
        write_source_output(source, new_items)
    log("fetch-twitter-saved", f"DONE — {len(new_items)} new item(s) written")


if __name__ == "__main__":
    main()
