#!/usr/bin/env python3
"""Build or refresh a profile baseline from recent source history.

Daily fetch remains today-only. This script is the explicit onboarding path:
    look back across a profile's recent source history, write the context into
    .system/source-profiles/<profile_id>/profile.md, and keep blockers visible.
"""
import argparse
import importlib.util
import re
from datetime import datetime
from pathlib import Path

from lib import PROFILE_LIBRARY_DIR, ROOT, SOURCES_PATH, llm_call, load_sources, log, profile_id_for_source



def load_module(filename: str, name: str):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_sources_section(title: str, limit: int = 8000) -> str:
    text = SOURCES_PATH.read_text(encoding="utf-8") if SOURCES_PATH.exists() else ""
    match = re.search(rf"^## {re.escape(title)}\s*$", text, re.M)
    if not match:
        return ""
    next_match = re.search(r"^## .+$", text[match.end():], re.M)
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.end():end].strip()[:limit]


def clean_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def profile_sources(query: str) -> list[dict]:
    q = query.lower().strip()
    sources = load_sources()
    matches = [
        src for src in sources
        if q == src.get("profile_id", "").lower()
        or q in src.get("name", "").lower()
        or q in src.get("url", "").lower()
    ]
    if not matches:
        raise SystemExit(f"profile/source not found in sources.md: {query}")
    profile = profile_id_for_source(matches[0])
    return [src for src in sources if profile_id_for_source(src) == profile]


def fetch_rss(source: dict, limit: int) -> list[dict]:
    mod = load_module("fetch-rss.py", "fetch_rss_module")
    try:
        entries = mod.parse_feed(mod.fetch_url(source["url"]))
    except Exception:
        if "youtube.com/feeds/videos.xml" not in source["url"]:
            raise
        entries = mod.fetch_youtube_fallback(source)
    entries = [entry for entry in entries if entry.get("url")]
    entries.sort(key=lambda it: it.get("published") or "", reverse=True)
    return [
        {
            "source": source["name"],
            "platform": source["platform"],
            "title": entry.get("title", ""),
            "url": entry.get("url", ""),
            "published": entry.get("published", ""),
            "summary": re.sub(r"\s+", " ", entry.get("summary", "")).strip()[:500],
        }
        for entry in entries[:limit]
    ]


def fetch_twitter(source: dict, limit: int) -> list[dict]:
    mod = load_module("fetch-twitter.py", "fetch_twitter_module")
    handle = mod.extract_handle(source["url"])
    tweets = mod.fetch_tweets(handle, max_count=max(limit, 20))
    items = []
    for tweet in tweets:
        tweet = mod.enrich_tweet(tweet)
        text = mod.tweet_text(tweet)
        if not text:
            continue
        metrics = mod.tweet_metrics(tweet)
        items.append(
            {
                "source": source["name"],
                "platform": source["platform"],
                "title": re.sub(r"\s+", " ", text)[:100].strip(" ，。,."),
                "url": f"https://x.com/{handle}/status/{tweet.get('id', '')}",
                "published": mod.tweet_local_date(tweet),
                "summary": text[:700],
                "likes": metrics.get("likes", 0),
                "rts": metrics.get("rts", 0),
            }
        )
    return items[:limit]


def collect_history(sources: list[dict], per_source: int) -> tuple[list[dict], list[str]]:
    items: list[dict] = []
    blockers: list[str] = []
    for source in sources:
        try:
            if source["platform"] == "rss":
                items.extend(fetch_rss(source, per_source))
            elif source["platform"] == "twitter":
                items.extend(fetch_twitter(source, per_source))
            else:
                blockers.append(f"{source['name']}: platform={source['platform']} has no baseline history collector")
        except Exception as ex:
            blockers.append(f"{source['name']}: {type(ex).__name__}: {str(ex)[:180]}")
    items.sort(key=lambda item: item.get("published") or "", reverse=True)
    return items, blockers


def item_lines(items: list[dict], limit: int) -> str:
    lines = []
    for idx, item in enumerate(items[:limit], 1):
        published = (item.get("published") or "")[:10]
        source = item.get("source", "")
        title = item.get("title", "")
        url = item.get("url", "")
        summary = item.get("summary", "")
        if len(summary) > 220:
            summary = summary[:219].rstrip() + "..."
        lines.append(f"{idx}. {published} | {source} | {title} | {url} — {summary}")
    return "\n".join(lines)


def channels_md(sources: list[dict]) -> str:
    return "\n".join(
        f"- {src['platform']} · {src['name']} · {src['url']}"
        for src in sources
    )


def generate_baseline(profile_id: str, sources: list[dict], items: list[dict], blockers: list[str]) -> str:
    user_context = read_sources_section("User Context")
    blockers_text = "\n".join(f"- {row}" for row in blockers) or "- none"
    prompt = f"""你是 Park-IO 的第一 owner。请为一个 source profile 建立 onboarding baseline。

这不是日报，不要把历史内容当作今天新闻。目标是让后续 daily delta 更容易评分和合并。

输出中文 Markdown，900-1500 字，结构固定：

# Source Profile — {profile_id}

## Channels
保留给定 channel 列表。

## Baseline Summary
3-5 条 bullet，总结这个 profile 近期主要讲什么。

## Source Persona
3-5 条 bullet，说明它在信息拓扑里的角色。

## Scoring Calibration
写 4-5 分、3 分、过滤的判断标准。

## How To Use In Daily Summary
3 条 bullet，说明未来只处理 delta 时应该怎样用它。

## Baseline Gaps
列出无法自动回看的来源或外部 blocker；如果没有就写 none。

用户上下文：
{user_context}

Profile: {profile_id}

Channels:
{channels_md(sources)}

Recent items:
{item_lines(items, 50)}

Blockers:
{blockers_text}
"""
    return clean_markdown(llm_call(prompt, max_tokens=2600, timeout=180))


def write_profile(profile_id: str, sources: list[dict], items: list[dict], blockers: list[str], body: str) -> Path:
    profile_dir = PROFILE_LIBRARY_DIR / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "items").mkdir(exist_ok=True)
    path = profile_dir / "profile.md"
    fm = "\n".join(
        [
            "---",
            f"profile_id: {profile_id}",
            f"profile_name: {profile_id}",
            f"generated_at: {datetime.now().isoformat(timespec='seconds')}",
            f"baseline_items: {len(items)}",
            f"baseline_blockers: {len(blockers)}",
            "---",
            "",
        ]
    )
    appendix = "\n\n## Recent Items Used For Baseline\n\n" + item_lines(items, 80)
    path.write_text(fm + body.strip() + appendix + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a profile baseline from recent source history.")
    parser.add_argument("profile_or_source", help="profile_id, source name, or URL substring")
    parser.add_argument("--per-source", type=int, default=12)
    args = parser.parse_args()

    sources = profile_sources(args.profile_or_source)
    profile_id = profile_id_for_source(sources[0])
    log("onboard-baseline", f"START — {profile_id}: {len(sources)} source(s)")
    items, blockers = collect_history(sources, args.per_source)
    if not items and blockers:
        raise SystemExit("no baseline items collected:\n" + "\n".join(blockers))
    body = generate_baseline(profile_id, sources, items, blockers)
    path = write_profile(profile_id, sources, items, blockers, body)
    log("onboard-baseline", f"DONE — wrote {path}")
    print(path)
    if blockers:
        print("Blockers:")
        for blocker in blockers:
            print(f"- {blocker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
