#!/usr/bin/env python3
"""Fetch Douyin profile updates for configured sources.

This is a lightweight update monitor. It records new videos into the daily
unprocessed inbox; heavy download/transcription is kept outside the critical
fetch path.
"""
import asyncio
import json
import re
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import PROFILE_LIBRARY_DIR, load_sources, load_state, log, profile_id_for_source, safe_filename, save_state, today, write_source_output

DOWNLOAD_CAPABILITY = Path.home() / "content-toolkit/capabilities/download"
COOKIE_FILE = Path.home() / "park-io/secrets/content-ops/douyin-cookies.json"
FETCH_LIMIT = 160

if DOWNLOAD_CAPABILITY.exists():
    sys.path.insert(0, str(DOWNLOAD_CAPABILITY))

try:
    from content_downloader.adapters.douyin.api_client import DouyinAPIClient
    DOUYIN_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - runtime dependency
    DouyinAPIClient = None
    DOUYIN_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def sec_uid_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return parsed.path.rstrip("/").split("/")[-1]


def aweme_author(aweme: dict) -> dict:
    return aweme.get("author") or {}


def is_source_author(aweme: dict, source_name: str, sec_uid: str) -> bool:
    author = aweme_author(aweme)
    author_sec_uid = str(author.get("sec_uid") or "")
    nickname = str(author.get("nickname") or "")
    return author_sec_uid == sec_uid or nickname == source_name


def published_date(raw: object) -> str:
    try:
        ts = int(raw or 0)
    except (TypeError, ValueError):
        return today()
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def title_text(aweme: dict) -> str:
    text = aweme.get("desc") or aweme.get("item_title") or str(aweme.get("aweme_id") or "Douyin update")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*#[^\s#]+", "", text).strip()
    return text[:90] or str(aweme.get("aweme_id") or "Douyin update")


def item_from_aweme(aweme: dict) -> dict:
    aweme_id = str(aweme.get("aweme_id") or "")
    stats = aweme.get("statistics") or {}
    desc = aweme.get("desc") or title_text(aweme)
    author = aweme_author(aweme)
    detail = [
        f"作者：{author.get('nickname', '') or '未知'}。",
        "",
        desc.strip(),
        "",
        f"点赞：{stats.get('digg_count', 0)}；评论：{stats.get('comment_count', 0)}；收藏：{stats.get('collect_count', 0)}；分享：{stats.get('share_count', 0)}。",
    ]
    return {
        "title": title_text(aweme),
        "url": f"https://www.douyin.com/video/{aweme_id}",
        "published": published_date(aweme.get("create_time")),
        "content": "\n".join(detail).strip(),
    }


def save_aweme_to_library(source: dict, aweme: dict) -> None:
    item = item_from_aweme(aweme)
    aweme_id = str(aweme.get("aweme_id") or "")
    date = item.get("published") or today()
    title = safe_filename(item.get("title", "douyin-video"))[:90]
    out_dir = PROFILE_LIBRARY_DIR / profile_id_for_source(source) / "items" / safe_filename(f"{date}_{title}_{aweme_id}")[:160]
    article = out_dir / "article.md"
    if article.exists():
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    article.write_text(
        "\n".join(
            [
                "---",
                f"source: {source['name']}",
                f"url: {item.get('url', '')}",
                f"published: {date}",
                f"aweme_id: {aweme_id}",
                f"author: {aweme_author(aweme).get('nickname', '')}",
                f"author_sec_uid: {aweme_author(aweme).get('sec_uid', '')}",
                "---",
                "",
                f"# {source['name']}：{item.get('title', 'Douyin update')}",
                "",
                item.get("content", ""),
                "",
            ]
        ),
        encoding="utf-8",
    )


def aweme_sort_key(aweme: dict) -> int:
    try:
        return int(aweme.get("create_time") or 0)
    except (TypeError, ValueError):
        return 0


async def fetch_awemes(sec_uid: str, cookies: dict[str, str], limit: int) -> list[dict]:
    if DouyinAPIClient is None:
        detail = DOUYIN_IMPORT_ERROR or "unknown import error"
        raise RuntimeError(f"DouyinAPIClient unavailable: {detail}")
    items: list[dict] = []
    seen: set[str] = set()
    max_cursor = 0
    async with DouyinAPIClient(cookies=cookies) as client:
        for _ in range(10):
            page = await asyncio.wait_for(client.get_user_post(sec_uid, max_cursor, 20), timeout=30)
            awemes = page.get("aweme_list") or []
            if not awemes:
                break
            for aweme in awemes:
                aweme_id = str(aweme.get("aweme_id") or "")
                if not aweme_id or aweme_id in seen:
                    continue
                seen.add(aweme_id)
                items.append(aweme)
                if len(items) >= limit:
                    return items
            next_cursor = int(page.get("max_cursor") or 0)
            if not page.get("has_more") or next_cursor == max_cursor:
                break
            max_cursor = next_cursor
    return items


def awemes_to_deliver(awemes: list[dict], delivered_ids: set[str], today_str: str, recency_days: int = 2) -> list[dict]:
    """Which fetched videos should be written into the inbox for the digest.

    Pure → unit-testable. Delivery is gated on ``delivered_ids`` (videos already
    written to a digest), NOT on library archival. The previous logic keyed
    delivery off ``published == today`` while deduping against the library — so a
    video first seen the day after it was posted was archived (→ permanently
    "processed") yet never delivered: the silent swallow the owner hit. Here a
    video is delivered when it has never been delivered AND was published within
    the recency window (so a late first-sight still ships, without backfilling the
    whole profile).
    """
    try:
        cutoff = datetime.strptime(today_str, "%Y-%m-%d").date() - timedelta(days=recency_days)
    except ValueError:
        cutoff = datetime.now().date() - timedelta(days=recency_days)
    out: list[dict] = []
    for aweme in awemes:
        aid = str(aweme.get("aweme_id") or "")
        if not aid or aid in delivered_ids:
            continue
        try:
            published = datetime.strptime(published_date(aweme.get("create_time")), "%Y-%m-%d").date()
        except ValueError:
            continue
        if published >= cutoff:
            out.append(aweme)
    return out


def library_aweme_ids(source: dict) -> set[str]:
    library_dir = PROFILE_LIBRARY_DIR / profile_id_for_source(source) / "items"
    if not library_dir.exists():
        return set()
    ids: set[str] = set()
    for path in library_dir.rglob("*"):
        for match in re.findall(r"(?<!\d)\d{16,20}(?!\d)", str(path)):
            ids.add(match)
    return ids


def main() -> None:
    state = load_state()
    sources = [s for s in load_sources() if s["platform"] == "douyin"]
    log("fetch-douyin", f"START — {len(sources)} sources")
    if not sources:
        return
    if not COOKIE_FILE.exists():
        log("fetch-douyin", f"ERROR cookies not found: {COOKIE_FILE}")
        return
    cookies = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    for src in sources:
        key = f"douyin:{src['name']}"
        try:
            sec_uid = sec_uid_from_url(src["url"])
            awemes = asyncio.run(fetch_awemes(sec_uid, cookies, limit=FETCH_LIMIT))
            awemes = [a for a in awemes if is_source_author(a, src["name"], sec_uid)]
            awemes.sort(key=aweme_sort_key, reverse=True)
            prior = state.get(key, {})
            processed_ids = set(prior.get("processed_ids", [])) | library_aweme_ids(src)
            # delivered_ids tracks what已经写进 digest，与 library 归档解耦（修复吞没 bug）。
            # 首次迁移：用 processed_ids 播种，避免一次性回灌整个历史 profile。
            if "delivered_ids" in prior:
                delivered_ids = set(prior.get("delivered_ids", []))
            else:
                delivered_ids = set(processed_ids)
            for aweme in awemes:
                save_aweme_to_library(src, aweme)
            fetched_ids = {str(a.get("aweme_id") or "") for a in awemes if a.get("aweme_id")}
            new_awemes = awemes_to_deliver(awemes, delivered_ids, today())
            if new_awemes:
                write_source_output(src, [item_from_aweme(a) for a in new_awemes])
            new_ids = {str(a.get("aweme_id") or "") for a in new_awemes if a.get("aweme_id")}
            delivered_ids |= new_ids
            state[key] = {
                "last_fetch": today(),
                "profile_count": len(fetched_ids),
                "processed_ids": sorted(processed_ids | new_ids),
                "delivered_ids": sorted(delivered_ids),
                "seen_ids": sorted(processed_ids | new_ids),
                "latest_ids": [str(a.get("aweme_id") or "") for a in awemes[:20] if a.get("aweme_id")],
            }
            log("fetch-douyin", f"  {src['name']}: {len(new_awemes)} NEW / {len(fetched_ids)} total")
        except Exception as ex:
            state[key] = {**state.get(key, {}), "last_fetch": today(), "status": "failed", "error": f"{type(ex).__name__}: {ex}"}
            log("fetch-douyin", f"  {src['name']}: ERROR {type(ex).__name__}: {ex}")
    save_state(state)
    log("fetch-douyin", "DONE")


if __name__ == "__main__":
    main()
