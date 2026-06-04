#!/usr/bin/env python3
"""
fetch-rss.py — Fetches RSS/Atom feeds for sources where platform=rss.
Filters new entries against state.json's last_published per source.
Appends new entries to inbox/unprocessed/<YY-MM-DD-profile>.md.
"""
import re
import json
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import (
    is_youtube_short,
    load_sources,
    load_state,
    save_state,
    write_source_output,
    log,
    today,
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
NS = {"atom": "http://www.w3.org/2005/Atom"}
YOUTUBE_FALLBACK_HANDLES = {
    "OpenAI YouTube": "OpenAI",
    "ChatGPT YouTube": "ChatGPT",
    "Anthropic YouTube": "anthropic-ai",
    "Claude YouTube": "claude",
}


def fetch_url(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def decode_js_string(text: str) -> str:
    try:
        return json_loads_string(text)
    except Exception:
        return unescape(text.replace("\\u0026", "&").replace("\\/", "/"))


def json_loads_string(text: str) -> str:
    import json

    return json.loads('"' + text.replace('"', '\\"') + '"')


def parse_date(s):
    """Parse RSS pubDate or Atom date, return ISO string or None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).isoformat()
    except Exception:
        pass
    try:
        return parsedate_to_datetime(s).isoformat()
    except Exception:
        return None


def published_local_date(iso_text: str) -> str:
    if not iso_text:
        return ""
    try:
        dt = datetime.fromisoformat(iso_text)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return iso_text[:10]


def youtube_relative_is_today(text: str) -> bool:
    text = text.lower()
    return any(
        token in text
        for token in (
            "minute ago",
            "minutes ago",
            "hour ago",
            "hours ago",
            "just now",
            "分前",
            "時間前",
        )
    )


def parse_youtube_videos_page(html: str) -> list:
    items = []
    seen = set()
    chunks = re.split(r'\{"richItemRenderer"', html)
    for chunk in chunks:
        video_match = re.search(r'"videoId":"([A-Za-z0-9_-]{6,})"', chunk)
        if not video_match:
            continue
        video_id = video_match.group(1)
        if video_id in seen:
            continue
        title_match = re.search(r'"title":\{"content":"([^"]+)"', chunk)
        if not title_match:
            continue
        meta_values = [
            decode_js_string(x)
            for x in re.findall(r'"text":\{"content":"([^"]+)"', chunk[:9000])
        ]
        relative = next((v for v in meta_values if " ago" in v.lower() or v.lower() == "just now"), "")
        if not relative:
            relative = next((v for v in meta_values if "前" in v), "")
        if not youtube_relative_is_today(relative):
            continue
        seen.add(video_id)
        title = decode_js_string(title_match.group(1))
        url = f"https://www.youtube.com/watch?v={video_id}"
        items.append(
            {
                "title": title,
                "url": url,
                "published": today(),
                "summary": f"YouTube official channel video. Published {relative}.",
            }
        )
    return items


def youtube_titles_with_ytdlp(handle: str, limit: int = 8) -> dict:
    try:
        result = subprocess.run(
            [
                "/opt/homebrew/bin/yt-dlp",
                "--flat-playlist",
                "--dump-single-json",
                "--playlist-end",
                str(limit),
                "--no-warnings",
                f"https://www.youtube.com/@{handle}/videos",
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
    except Exception:
        return {}
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    out = {}
    for entry in payload.get("entries", []) or []:
        video_id = entry.get("id")
        if video_id:
            out[video_id] = {
                "title": entry.get("title") or "",
                "url": entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
                "duration": entry.get("duration"),
            }
    return out


def fetch_youtube_fallback(src: dict) -> list:
    handle = YOUTUBE_FALLBACK_HANDLES.get(src["name"])
    if not handle:
        return []
    url = f"https://www.youtube.com/@{handle}/videos"
    html = fetch_url(url, timeout=30)
    items = parse_youtube_videos_page(html)
    titles = youtube_titles_with_ytdlp(handle, limit=8)
    kept = []
    for item in items:
        video_id = item["url"].rsplit("=", 1)[-1]
        meta = titles.get(video_id) or {}
        if meta.get("title"):
            item["title"] = meta["title"]
        if meta.get("url"):
            item["url"] = meta["url"]
        if meta.get("duration"):
            item["summary"] += f" Duration: {int(meta['duration'])} seconds."
        # Owner wants long videos only — drop Shorts at ingestion.
        if is_youtube_short(item.get("url", ""), meta.get("duration")):
            log("fetch-rss", f"  skip YouTube short: {item.get('title', '')[:40]}")
            continue
        kept.append(item)
    return kept


def parse_feed(xml_text):
    """Parse RSS or Atom XML, return list of entry dicts."""
    items = []
    root = ET.fromstring(xml_text)
    tag = root.tag.lower()

    if tag.endswith("}feed") or tag == "feed":
        # Atom
        entries = root.findall("atom:entry", NS)
        if len(entries) == 0:
            entries = root.findall("entry")
        for entry in entries:
            title = (
                entry.findtext("atom:title", "", NS)
                or entry.findtext("title", "")
            ).strip()
            link_el = entry.find("atom:link", NS)
            if link_el is None:
                link_el = entry.find("link")
            link = ""
            if link_el is not None:
                link = link_el.get("href") or link_el.text or ""
            published = (
                entry.findtext("atom:updated", "", NS)
                or entry.findtext("atom:published", "", NS)
                or entry.findtext("updated", "")
                or entry.findtext("published", "")
            )
            summary = (
                entry.findtext("atom:summary", "", NS)
                or entry.findtext("atom:content", "", NS)
                or entry.findtext("summary", "")
                or entry.findtext("content", "")
                or ""
            )
            items.append(
                {
                    "title": title,
                    "url": link,
                    "published": parse_date(published),
                    "summary": summary[:3000],
                }
            )
    elif tag == "rss":
        for item in root.findall(".//item"):
            items.append(
                {
                    "title": (item.findtext("title") or "").strip(),
                    "url": (item.findtext("link") or "").strip(),
                    "published": parse_date(item.findtext("pubDate")),
                    "summary": (item.findtext("description") or "")[:3000],
                }
            )
    return items


def main():
    state = load_state()
    sources = [s for s in load_sources() if s["platform"] == "rss"]
    log("fetch-rss", f"START — {len(sources)} sources")

    for src in sources:
        key = f"rss:{src['name']}"
        try:
            used_youtube_fallback = False
            try:
                xml_text = fetch_url(src["url"])
                entries = parse_feed(xml_text)
            except HTTPError as ex:
                if "youtube.com/feeds/videos.xml" not in src["url"]:
                    raise
                log("fetch-rss", f"  {src['name']}: RSS {ex.code}, trying YouTube page fallback")
                entries = fetch_youtube_fallback(src)
                used_youtube_fallback = True
            log("fetch-rss", f"  {src['name']}: {len(entries)} total entries")

            new_items = []
            if used_youtube_fallback:
                seen_urls = state.get(key, {}).get("seen_urls", {})
                for e in entries:
                    if e.get("url") in seen_urls:
                        continue
                    new_items.append(e)
                    seen_urls[e["url"]] = today()
            else:
                seen_urls = state.get(key, {}).get("seen_urls", {})
                last_seen = state.get(key, {}).get("last_published")
                for e in entries:
                    url = e.get("url", "")
                    if url and url in seen_urls:
                        continue
                    if last_seen and e["published"] and e["published"] <= last_seen:
                        continue
                    if e.get("published") and published_local_date(e["published"]) != today():
                        continue
                    if e.get("published"):
                        e["published"] = published_local_date(e["published"])
                    new_items.append(e)
                    if url:
                        seen_urls[url] = today()

            log("fetch-rss", f"  {src['name']}: {len(new_items)} NEW")
            if new_items:
                write_source_output(src, new_items)
            if used_youtube_fallback:
                state[key] = {
                    "seen_urls": seen_urls,
                    "last_fetch": today(),
                }
            else:
                published_dates = [e["published"] for e in entries if e.get("published")]
                latest_seen = max(published_dates) if published_dates else last_seen
                state[key] = {
                    "seen_urls": seen_urls,
                    "last_published": latest_seen,
                    "last_fetch": today(),
                }
        except Exception as ex:
            state[key] = {**state.get(key, {}), "last_fetch": today(), "status": "failed", "error": f"{type(ex).__name__}: {ex}"}
            log("fetch-rss", f"  {src['name']}: ERROR {type(ex).__name__}: {ex}")

    save_state(state)
    log("fetch-rss", "DONE")


if __name__ == "__main__":
    main()
