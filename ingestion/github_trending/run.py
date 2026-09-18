#!/usr/bin/env python3
"""fetch-github-trending.py — GitHub Trending (daily) as a raw source.

Tools like Hypit (8k stars in two days) spread through GitHub Trending and
people's timelines, not through the official accounts we track. Each repo's
first appearance on the daily board becomes one raw item that flows through
to_md → coarse_filter → AI like any other source; the same page also feeds the
Product Radar signal list (see product_radar.fetch_github_trending).

No token needed: the public page is parsed with regexes kept deliberately
loose (GitHub changes class names; the article/h2/p/"stars today" anchors have
been stable for years). A parse that yields zero repos is recorded as a
failure so source health turns red instead of silently going quiet.
"""
from __future__ import annotations

import html
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import load_sources, load_state, log, save_state, today, write_source_output  # noqa: E402

TRENDING_URL = "https://github.com/trending?since=daily"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36 Park-IO/1.0"
STATE_KEY = "github:GitHub Trending"
REPEAT_WINDOW_DAYS = 7
DEFAULT_SOURCE = {
    "id": "github-trending",
    "profile_id": "github-trending",
    "name": "GitHub Trending",
    "profile_name": "GitHub Trending",
    "platform": "github",
    "url": TRENDING_URL,
    "category": "ai",
    "priority": "high",
    "frequency": "daily",
    "active": "true",
}

ARTICLE_RE = re.compile(r"<article[^>]*class=\"[^\"]*Box-row[^\"]*\"[^>]*>(.*?)</article>", re.S)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
HREF_RE = re.compile(r"href=\"/([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)\"")
DESC_RE = re.compile(r"<p[^>]*class=\"[^\"]*col-9[^\"]*\"[^>]*>(.*?)</p>", re.S)
LANG_RE = re.compile(r"itemprop=\"programmingLanguage\"[^>]*>(.*?)</span>", re.S)
STARS_TODAY_RE = re.compile(r"([\d,]+)\s+stars?\s+today")
TOTAL_STARS_RE = re.compile(r"href=\"/[^\"]+/stargazers\"[^>]*>(.*?)</a>", re.S)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment or ""))).strip()


def _int(value: str) -> int:
    digits = re.sub(r"[^\d]", "", value or "")
    return int(digits) if digits else 0


def parse_trending(page_html: str) -> list[dict]:
    """One dict per repo on the board, in board order (rank 1 first)."""
    repos: list[dict] = []
    for rank, block in enumerate(ARTICLE_RE.findall(page_html or ""), 1):
        h2 = H2_RE.search(block)
        href = HREF_RE.search(h2.group(1) if h2 else block)
        if not href:
            continue
        full_name = href.group(1)
        desc = DESC_RE.search(block)
        lang = LANG_RE.search(block)
        stars_today = STARS_TODAY_RE.search(_text(block))
        total = TOTAL_STARS_RE.search(block)
        repos.append(
            {
                "rank": rank,
                "full_name": full_name,
                "owner": full_name.split("/", 1)[0],
                "repo": full_name.split("/", 1)[1],
                "url": f"https://github.com/{full_name}",
                "description": _text(desc.group(1)) if desc else "",
                "language": _text(lang.group(1)) if lang else "",
                "stars_today": _int(stars_today.group(1)) if stars_today else 0,
                "stars_total": _int(_text(total.group(1))) if total else 0,
            }
        )
    return repos


def fetch_page(url: str = TRENDING_URL, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def trending_source() -> dict:
    for src in load_sources():
        if src.get("platform") == "github":
            return {**DEFAULT_SOURCE, **src}
    return dict(DEFAULT_SOURCE)


def new_repos(repos: list[dict], seen: dict[str, str], day: str, window_days: int = REPEAT_WINDOW_DAYS) -> list[dict]:
    """Repos not seen on the board within the repeat window (first appearance or a comeback)."""
    cutoff = (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=window_days)).strftime("%Y-%m-%d")
    fresh: list[dict] = []
    for repo in repos:
        last = seen.get(repo["full_name"], "")
        if last and last >= cutoff:
            continue
        fresh.append(repo)
    return fresh


def prune_seen(seen: dict[str, str], day: str, keep_days: int = 60) -> dict[str, str]:
    cutoff = (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    return {name: last for name, last in seen.items() if last >= cutoff}


def to_item(repo: dict, day: str) -> dict:
    stars = f"今日 +{repo['stars_today']:,} star" if repo["stars_today"] else ""
    total = f"累计 {repo['stars_total']:,} star" if repo["stars_total"] else ""
    lang = f"语言 {repo['language']}" if repo["language"] else ""
    meta = " · ".join(part for part in (f"GitHub Trending 日榜第 {repo['rank']} 名", stars, total, lang) if part)
    text = f"{repo['description'] or '（仓库没有描述）'}\n\n{meta}\n{repo['url']}"
    return {
        "id": f"github-trending:{repo['full_name']}:{day}",
        "url": repo["url"],
        "title": f"{repo['full_name']} — {repo['description'][:100] or 'GitHub Trending'}",
        "text": text,
        "content": text,
        "author": repo["owner"],
        "handle": repo["owner"],
        "published": day,
        "time": day,
        "likes": repo["stars_today"],
        "rts": 0,
        "rank": repo["rank"],
        "language": repo["language"],
        "stars_today": repo["stars_today"],
        "stars_total": repo["stars_total"],
    }


def main() -> int:
    state = load_state()
    day = today()
    src = trending_source()
    entry = state.get(STATE_KEY, {})
    seen: dict[str, str] = dict(entry.get("seen") or {})
    log("fetch-github-trending", "START")
    try:
        page = fetch_page(src.get("url") or TRENDING_URL)
        repos = parse_trending(page)
        if not repos:
            raise RuntimeError("trending page parsed to 0 repos; markup may have changed")
        fresh = new_repos(repos, seen, day)
        items = [to_item(repo, day) for repo in fresh]
        if items:
            write_source_output(src, items)
        for repo in repos:
            seen[repo["full_name"]] = day
        state[STATE_KEY] = {
            "last_fetch": day,
            "status": "ok_new" if items else "ok_no_new",
            "fetched_count": len(repos),
            "new_count": len(items),
            "detail": f"daily board checked; {len(items)} new repo(s) of {len(repos)} on the board",
            "seen": prune_seen(seen, day),
        }
        log("fetch-github-trending", f"  board {len(repos)} repos, {len(items)} new")
    except Exception as ex:
        error = f"{type(ex).__name__}: {ex}"
        state[STATE_KEY] = {**entry, "last_fetch": day, "status": "failed", "error": error}
        log("fetch-github-trending", f"  ERROR {error}")
    save_state(state)
    log("fetch-github-trending", "DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
