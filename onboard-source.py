#!/usr/bin/env python3
"""Build a historical profile for a newly added source.

This is intentionally separate from the daily fetch path. Daily refresh should
stay today-only; onboarding turns recent history into durable source context.
"""
import argparse
import importlib.util
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from lib import PROFILE_LIBRARY_DIR, ROOT, LLMUnavailable, llm_call, load_sources, log, profile_id_for_source, today

SOURCES_PATH = Path.home() / "park-io" / "sources.md"


def load_fetch_rss_module():
    path = ROOT / "fetch-rss.py"
    spec = importlib.util.spec_from_file_location("fetch_rss_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_fetch_twitter_module():
    path = ROOT / "fetch-twitter.py"
    spec = importlib.util.spec_from_file_location("fetch_twitter_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_text(path: Path, limit: int = 10000) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")[:limit]


def read_sources_section(title: str, limit: int = 10000) -> str:
    text = read_text(SOURCES_PATH, limit=60000)
    if not text:
        return ""
    pattern = re.compile(rf"^## {re.escape(title)}\s*$", re.M)
    match = pattern.search(text)
    if not match:
        return ""
    next_match = re.search(r"^## .+$", text[match.end():], re.M)
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.end():end].strip()[:limit]


def find_source(query: str) -> dict:
    q = query.lower().strip()
    matches = [
        src
        for src in load_sources()
        if q in src.get("name", "").lower() or q in src.get("url", "").lower()
    ]
    if not matches:
        raise SystemExit(f"source not found in sources.md: {query}")
    if len(matches) > 1:
        names = ", ".join(src["name"] for src in matches)
        raise SystemExit(f"source query is ambiguous: {names}")
    return matches[0]


def clean_llm_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    idx = text.find("# Source Profile")
    if idx >= 0:
        text = text[idx:]
    text = re.sub(r"\n-{3,}\n", "\n\n", text)
    return text.strip()


def recent_enough(item: dict, days: int) -> bool:
    if days <= 0:
        return True
    raw = str(item.get("published") or "")[:10]
    if not raw:
        return True
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return True
    return dt >= datetime.now() - timedelta(days=days)


def fetch_rss_history(source: dict, limit: int, days: int) -> list[dict]:
    fetch_rss = load_fetch_rss_module()
    entries = fetch_rss.parse_feed(fetch_rss.fetch_url(source["url"]))
    entries = [entry for entry in entries if entry.get("url")]
    entries.sort(key=lambda it: it.get("published") or "", reverse=True)
    recent = [entry for entry in entries if recent_enough(entry, days)]
    return (recent or entries)[:limit]


def fetch_twitter_history(source: dict, limit: int, days: int) -> list[dict]:
    fetch_twitter = load_fetch_twitter_module()
    handle = fetch_twitter.extract_handle(source["url"])
    tweets = fetch_twitter.fetch_tweets(handle, max_count=max(limit, 20))
    items = []
    for tweet in tweets:
        tweet = fetch_twitter.enrich_tweet(tweet)
        text = fetch_twitter.tweet_text(tweet)
        if not text:
            continue
        metrics = fetch_twitter.tweet_metrics(tweet)
        published = fetch_twitter.tweet_local_date(tweet)
        item = {
            "title": re.sub(r"\s+", " ", text)[:90].strip(" ，。,.") or "Tweet",
            "url": f"https://x.com/{handle}/status/{tweet.get('id', '')}",
            "published": published,
            "summary": text[:1200],
            "content": text[:2400],
            "likes": metrics.get("likes", 0),
            "rts": metrics.get("rts", 0),
        }
        if recent_enough(item, days):
            items.append(item)
    return items[:limit]


def fetch_history(source: dict, limit: int, days: int) -> list[dict]:
    platform = source["platform"]
    if platform == "rss":
        return fetch_rss_history(source, limit, days)
    if platform == "twitter":
        return fetch_twitter_history(source, limit, days)
    raise SystemExit(
        f"baseline onboarding for platform={platform} needs an external history collector or manual seed"
    )


def item_lines(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        published = (item.get("published") or "")[:10]
        title = item.get("title", "").strip()
        summary = re.sub(r"\s+", " ", item.get("summary", "")).strip()
        if summary:
            summary = f" — {summary[:220]}"
        lines.append(f"{i}. {published} | {title} | {item.get('url', '')}{summary}")
    return "\n".join(lines)


def fallback_profile(source: dict, items: list[dict]) -> str:
    titles = [item.get("title", "").strip() for item in items if item.get("title")]
    themes = []
    theme_words = {
        "Agent / 编程工作流": ("agent", "opencode", "openclaw", "claude code", "codex"),
        "模型训练 / 研究访谈": ("anthropic", "gemini", "training", "model", "模型", "训练"),
        "AI 商业化 / 创业": ("startup", "founder", "商业", "创业", "组织"),
    }
    joined = "\n".join(titles).lower()
    for label, needles in theme_words.items():
        if any(needle.lower() in joined for needle in needles):
            themes.append(label)
    themes_text = "、".join(themes) if themes else "AI 访谈、技术人物、产品与商业化"
    recent = "\n".join(f"- {title}" for title in titles[:10])
    return f"""# Source Profile — {source['name']}

_Generated: {datetime.now().isoformat(timespec="seconds")} · Onboarding date: {today()}_

## Owner Judgment

这是一个适合作为 Podcast / YouTube 长访谈观察源的频道。它不应该每天用旧视频打扰日报，但值得保留历史档案，用来判断新视频是在延续既有主题，还是出现了新的 AI 技术、商业化或内容选题信号。

## Source Persona

- 主要角色：中文长访谈 / AI 与商业内容源。
- 当前主题重心：{themes_text}。
- 对 Park-IO 的价值：帮助内容线寻找长视频选题和人物线索，帮助产品线理解 Agent、模型训练和 AI 应用落地的讨论语境。

## Scoring Calibration

- 4-5 分：嘉宾或主题直接涉及 Agent、Claude/Codex、模型训练、AI 产品化、创业组织变化，并能给我们的产品线或内容线带来可执行判断。
- 3 分：主题相关但主要是背景知识、人物访谈或宽泛趋势。
- 1-2 分：娱乐化、重复发布、剪辑片段、与三条线关系弱的内容。

## Historical Digest

最近内容显示这个 source 更像“背景理解 + 选题来源”，不是即时新闻源。日报只应在新视频主题明确贴近我们的三条线时展开。

## Representative Recent Items

{recent}
"""


def generate_profile(source: dict, items: list[dict]) -> str:
    user_context = read_sources_section("User Context", limit=8000)
    prompt = f"""你是 Park-IO 的第一 owner。现在新增了一个 source，需要做一次历史建档。

注意：这不是今天日报。不要把历史内容当今天新闻推给用户。你的任务是根据最近历史，建立这个 source 之后用于评分和摘要的背景档案。

请保持短而可执行：总长度 900-1400 个中文字符。不要写过程说明，不要寒暄，不要使用无法从标题推断的身份细节；不确定就写“从近期标题看”。

请用中文输出一份 Markdown source profile，结构必须包含：

# Source Profile — {source['name']}

## Owner Judgment
- 2-3 条 bullet

## Source Persona
- 3-5 条 bullet，基于近期标题归纳

## Historical Digest
- 3-5 条 bullet，提炼主题，不要逐条流水账

## Scoring Calibration
- 4-5 分 / 3 分 / 过滤，各 1-2 条

## How To Use In Daily Summary
- 3 条 bullet，强调只解释新发布内容里的新判断

用户基线：
{user_context}

Source:
- name: {source['name']}
- platform: {source['platform']}
- url: {source['url']}
- category: {source['category']}
- priority: {source['priority']}

Recent history:
{item_lines(items)}
"""
    try:
        return clean_llm_markdown(llm_call(prompt, max_tokens=2200, timeout=180))
    except Exception as ex:
        log("onboard-source", f"LLM profile failed: {type(ex).__name__}: {ex}")
        return fallback_profile(source, items)


def write_profile(source: dict, items: list[dict], profile: str) -> Path:
    profile_dir = PROFILE_LIBRARY_DIR / profile_id_for_source(source)
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "items").mkdir(parents=True, exist_ok=True)
    path = profile_dir / "profile.md"
    recent = item_lines(items)
    metadata = f"""---
source_id: {source['id']}
source_name: {source['name']}
platform: {source['platform']}
url: {source['url']}
generated_at: {datetime.now().isoformat(timespec="seconds")}
history_items: {len(items)}
---

"""
    appendix = f"""

## Recent Items Used For Onboarding

{recent}
"""
    path.write_text(metadata + profile.strip() + appendix, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a historical source profile.")
    parser.add_argument("source", help="source name or URL substring from sources.md")
    parser.add_argument("--limit", type=int, default=30, help="number of recent feed items to inspect")
    parser.add_argument("--days", type=int, default=7, help="prefer items from the recent N days; falls back to latest items if none")
    args = parser.parse_args()

    source = find_source(args.source)
    log("onboard-source", f"START — {source['name']}")
    items = fetch_history(source, args.limit, args.days)
    if not items:
        raise SystemExit(f"no history items found for {source['name']}")
    profile = generate_profile(source, items)
    path = write_profile(source, items, profile)
    log("onboard-source", f"DONE — wrote {path}")
    print(path)


if __name__ == "__main__":
    main()
