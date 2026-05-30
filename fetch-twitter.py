#!/usr/bin/env python3
"""
fetch-twitter.py — Calls twitter-cli for each platform=twitter source.
Filters new tweets against state.json's last_id per handle.
"""
import json
import os
import re
import subprocess
import urllib.parse
from datetime import datetime

from lib import (
    inbox_dir,
    load_sources,
    load_state,
    save_state,
    safe_filename,
    write_source_output,
    log,
    today,
)

TWITTER_BIN = "/Users/wendy/.local/bin/twitter"
TWITTER_AUTH_ENV = "/Users/wendy/work/input-to-park/twitter-auth.env"
MAX_PER_HANDLE = 20
REFETCH_TODAY = os.environ.get("PARKIO_REFETCH_TODAY") == "1"
NESTED_TWEET_KEYS = (
    "retweetedStatus",
    "retweeted_status",
    "retweet",
    "retweetedTweet",
    "quotedStatus",
    "quoted_status",
    "quotedTweet",
    "quote",
)


def load_twitter_env():
    """Load persisted cookies for launchd, which cannot reliably read Keychain."""
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


def extract_handle(url):
    """https://x.com/dontbesilent → 'dontbesilent'"""
    p = urllib.parse.urlparse(url)
    return p.path.lstrip("/").split("/")[0]


def fetch_tweets(handle, max_count=MAX_PER_HANDLE):
    load_twitter_env()
    result = subprocess.run(
        [TWITTER_BIN, "user-posts", handle, "--max", str(max_count), "--json"],
        capture_output=True,
        text=True,
        timeout=60,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"twitter-cli exit={result.returncode}: {result.stderr.strip()[:300]}")
    payload = json.loads(result.stdout)
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def fetch_article(tweet_id):
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


def tweet_local_date(tweet):
    dt = str(tweet.get("createdAtLocal") or tweet.get("createdAtISO") or "")
    if len(dt) >= 10 and dt[:4].isdigit():
        return dt[:10]
    return ""


def tweet_metrics(tweet):
    metrics = tweet.get("metrics") or {}
    return {
        "likes": metrics.get("likes", tweet.get("likes", 0)) or 0,
        "rts": metrics.get("retweets", tweet.get("rts", 0)) or 0,
    }


def compact_text(value):
    return " ".join(str(value or "").split()).strip()


def normalize_tweet_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [rejoin_spaces(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def rejoin_spaces(value):
    return re.sub(r"[ \t]+", " ", str(value or "")).strip()


def tweet_id(tweet):
    return str(
        tweet.get("id")
        or tweet.get("id_str")
        or tweet.get("rest_id")
        or ""
    )


def tweet_conversation_id(tweet):
    """Thread/conversation id, so replies in the same thread can be merged into
    one event (gotcha #9). Falls back to the in-reply-to root, else "" (the
    caller defaults a standalone tweet to its own id)."""
    for key in ("conversationId", "conversationIdStr", "conversation_id", "conversation_id_str"):
        val = tweet.get(key)
        if val:
            return str(val)
    for key in ("inReplyToStatusId", "inReplyToStatusIdStr", "in_reply_to_status_id", "in_reply_to_status_id_str"):
        val = tweet.get(key)
        if val:
            return str(val)
    return ""


def unwrap_tweet(value):
    if not isinstance(value, dict):
        return None
    for key in ("tweet", "data", "result", "legacy"):
        nested = value.get(key)
        if isinstance(nested, dict):
            unwrapped = unwrap_tweet(nested)
            if unwrapped:
                return {**value, **unwrapped}
    return value


def nested_tweets(tweet):
    nested = []
    for key in NESTED_TWEET_KEYS:
        value = unwrap_tweet(tweet.get(key))
        if isinstance(value, dict):
            label = "转发" if "retweet" in key.lower() else "引用"
            nested.append((label, value))
    return nested


def article_text_from(tweet):
    article_title = compact_text(tweet.get("articleTitle") or tweet.get("title"))
    article_text = normalize_tweet_text(tweet.get("articleText") or tweet.get("article_text"))
    if not article_text:
        return ""
    if article_title:
        return f"长文《{article_title}》\n\n{article_text}"
    return article_text


def primary_tweet_text(tweet):
    candidates = [
        tweet.get("text"),
        tweet.get("fullText"),
        tweet.get("full_text"),
        tweet.get("rawText"),
        article_text_from(tweet),
    ]
    note = tweet.get("note_tweet") or tweet.get("noteTweet")
    if isinstance(note, dict):
        candidates.extend([note.get("text"), note.get("fullText")])
    legacy = tweet.get("legacy")
    if isinstance(legacy, dict):
        candidates.extend([legacy.get("full_text"), legacy.get("text")])
    texts = []
    for value in candidates:
        text = normalize_tweet_text(value)
        if text and text not in texts and text != "https://t.co/":
            texts.append(text)
    return "\n\n".join(texts)


def link_fallback_text(tweet):
    media = tweet.get("media") or []
    urls = tweet.get("urls") or []
    media_urls = []
    for media_item in media if isinstance(media, list) else []:
        if isinstance(media_item, dict) and media_item.get("url"):
            media_urls.append(str(media_item["url"]))
    expanded_urls = []
    for url_item in urls if isinstance(urls, list) else []:
        if isinstance(url_item, dict):
            expanded_urls.append(str(url_item.get("expandedUrl") or url_item.get("expanded_url") or url_item.get("url") or ""))
        else:
            expanded_urls.append(str(url_item))
    fallback_parts = [u for u in media_urls + expanded_urls if u and u != "https://t.co/"]
    return "\n".join(fallback_parts).strip()


def tweet_text(tweet):
    """Extract tweet text across twitter-cli schema variants.

    twitter-cli has changed field names before. Empty tweet text is poison for
    the downstream digest, so keep the extraction centralized and conservative.
    """
    primary = primary_tweet_text(tweet)
    nested_parts = []
    for label, nested in nested_tweets(tweet):
        nested_text = tweet_text(nested)
        if nested_text:
            nested_parts.append((label, nested_text))

    if nested_parts:
        longest_label, longest_text = max(nested_parts, key=lambda pair: len(pair[1]))
        if not primary:
            return f"{longest_label}内容：{longest_text}"
        if len(primary) < 120 and len(longest_text) > len(primary) * 2:
            return f"{longest_label}内容：{longest_text}\n\n转发者补充：{primary}"
        combined = [primary]
        combined.extend(f"{label}内容：{text}" for label, text in nested_parts)
        return "\n\n".join(combined)

    if primary:
        return primary
    return link_fallback_text(tweet)


def enrich_tweet(tweet):
    """Attach quoted/linked X Article content when twitter-cli exposes only a stub."""
    out = dict(tweet)
    main_id = tweet_id(out)
    if main_id and not article_text_from(out):
        article = fetch_article(main_id)
        if article.get("articleText"):
            out["articleTitle"] = article.get("articleTitle") or article.get("title") or ""
            out["articleText"] = article.get("articleText") or ""
            out["text"] = article.get("text") or out.get("text") or ""
    for key in NESTED_TWEET_KEYS:
        nested = unwrap_tweet(out.get(key))
        if not isinstance(nested, dict):
            continue
        nested_id = tweet_id(nested)
        if nested_id and not article_text_from(nested):
            article = fetch_article(nested_id)
            if article.get("articleText"):
                nested = dict(nested)
                nested["articleTitle"] = article.get("articleTitle") or article.get("title") or ""
                nested["articleText"] = article.get("articleText") or ""
                nested["text"] = article.get("text") or nested.get("text") or ""
                nested["author"] = article.get("author") or nested.get("author") or {}
                out[key] = nested
    return out


def tweet_author(tweet, handle):
    author = tweet.get("author")
    if isinstance(author, dict):
        return author.get("name") or author.get("screenName") or handle
    return tweet.get("author", f"@{handle}")


def tweet_handle(tweet, handle):
    author = tweet.get("author")
    if isinstance(author, dict):
        return author.get("screenName") or handle
    return handle


def main():
    state = load_state()
    sources = [s for s in load_sources() if s["platform"] == "twitter"]
    log("fetch-twitter", f"START — {len(sources)} sources")

    for src in sources:
        handle = extract_handle(src["url"])
        key = f"twitter:{handle}"
        try:
            tweets = fetch_tweets(handle)
            log("fetch-twitter", f"  @{handle}: {len(tweets)} fetched")

            last_id = state.get(key, {}).get("last_id")
            new_items = []
            for t in tweets:
                t = enrich_tweet(t)
                tid = tweet_id(t)
                if not tid:
                    continue
                if tweet_local_date(t) != today():
                    continue
                if last_id and int(tid) <= int(last_id) and not REFETCH_TODAY:
                    continue
                metrics = tweet_metrics(t)
                text = tweet_text(t)
                if not text:
                    log("fetch-twitter", f"  @{handle}: skip empty tweet text id={tid}")
                    continue
                new_items.append(
                    {
                        "id": tid,
                        "url": f"https://x.com/{handle}/status/{tid}",
                        "text": text,
                        "author": tweet_author(t, handle),
                        "handle": tweet_handle(t, handle),
                        "conversation_id": tweet_conversation_id(t) or tid,
                        "time": t.get("createdAtLocal") or t.get("createdAtISO") or t.get("time", ""),
                        "published": tweet_local_date(t),
                        "likes": metrics["likes"],
                        "rts": metrics["rts"],
                    }
                )

            log("fetch-twitter", f"  @{handle}: {len(new_items)} NEW today")
            if new_items:
                if REFETCH_TODAY:
                    out = inbox_dir() / f"{src['id']}-{safe_filename(src['name'])}.md"
                    if out.exists():
                        out.unlink()
                write_source_output(src, new_items)
                newest_id = max(int(t["id"]) for t in new_items)
                state[key] = {"last_id": str(newest_id), "last_fetch": today()}
            else:
                prev = state.get(key, {})
                state[key] = {"last_id": prev.get("last_id", ""), "last_fetch": today()}
        except Exception as ex:
            log("fetch-twitter", f"  @{handle}: ERROR {type(ex).__name__}: {ex}")

    save_state(state)
    log("fetch-twitter", "DONE")


if __name__ == "__main__":
    main()
