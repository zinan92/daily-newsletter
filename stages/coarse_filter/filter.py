"""Low-cost item filter between unprocessed raw capture and processed batches.

This stage is intentionally conservative. It removes obvious social-feed noise
before the expensive AI/newsletter path, while preserving official, manual,
media, WeChat, and other source types for the normal AI processing channel.
Rejected rows are written to a batch-local debug log so mistakes can be
recovered without polluting the long-term library.
"""
from __future__ import annotations

import re
from pathlib import Path

from lib import parse_md_items, render_frontmatter


PROTECTED_SOURCE_NAMES = {
    "我的 X 收藏",
    "手动公众号文章",
    "Sam Altman",
    "Greg Brockman",
    "Kevin Weil",
    "Mark Chen",
    "Dario Amodei",
    "Daniela Amodei",
    "Mike Krieger",
    "Anthropic News",
    "Anthropic Engineering",
    "Claude Blog",
    "OpenAI Blog",
    "OpenAI X",
    "ChatGPT X",
    "Anthropic X",
    "Claude X",
    "Claude Devs X",
    "openai-codex-releases",
    "claude-code-releases",
}

PROTECTED_PLATFORMS = {"wechat", "douyin"}
PROTECTED_CATEGORIES = {
    "ai-official",
    "video-official",
    "wechat-ai",
    "wechat-manual",
    "manual-link",
    "personal-saved",
    "saved",
}

LOW_VALUE_PATTERNS = (
    ("life_philosophy", re.compile(r"(人生|人性|人品|自洽|主线任务|走上人生巅峰|痛苦|理解与翻译|意义系统|高塔早已崩塌)")),
    ("relationship_or_lowbrow", re.compile(r"(女朋友|女生|男生|打炮|situationship|ship|泡妞|追女生|黄色|低俗)")),
    ("political_or_society_meme", re.compile(r"(特朗普|Trump|政治笑话|赢麻了|阴阳人|王朔|民族自豪|德国人.*诺贝尔)")),
    ("consumer_chatter", re.compile(r"(iPhone\\s*17|iPhone\\s*18|iphone\\s*17|iphone\\s*18|上 iPhone|等 iPhone|换手机)")),
    ("food_or_lifestyle", re.compile(r"(海底捞|捞币|小嗨杯|山姆|Costco|沃尔玛|外卖|消费性价比)")),
    ("empty_reaction", re.compile(r"^(笑死|牛逼|卧槽|卧龙附近必有凤雏|感觉是个好主意|妈的|又赢麻了|绷不住|哈哈哈|转发|mark|收藏了)[！!。…\\s]*(?:https?://\\S+)?$")),
)

AI_OR_PRODUCT_TERMS = (
    "ai",
    "agent",
    "codex",
    "claude",
    "chatgpt",
    "gpt",
    "llm",
    "openai",
    "anthropic",
    "cursor",
    "mcp",
    "模型",
    "大模型",
    "代码",
    "开发",
    "工具",
    "内容",
    "流量",
    "分发",
    "变现",
    "小红书",
    "公众号",
    "产品",
    "自动化",
    "工作流",
    "赚钱",
)


def source_is_protected(fm: dict, item: dict) -> bool:
    source = (item.get("source") or fm.get("source_name") or "").strip()
    platform = (fm.get("platform") or "").strip().lower()
    category = (fm.get("category") or "").strip().lower()
    if source in PROTECTED_SOURCE_NAMES:
        return True
    if platform in PROTECTED_PLATFORMS:
        return True
    if category in PROTECTED_CATEGORIES:
        return True
    if "youtube" in source.lower() or "podcast" in source.lower():
        return True
    return False


def item_text(item: dict) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "content", "meta", "source", "author", "handle")
    )


def has_domain_signal(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in AI_OR_PRODUCT_TERMS)


def compact_content_without_urls(text: str) -> str:
    text = re.sub(r"https?://\\S+", "", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def should_keep_item(fm: dict, item: dict) -> tuple[bool, str]:
    if source_is_protected(fm, item):
        return True, "protected_source"

    text = item_text(item)
    compact = compact_content_without_urls(text)

    # Plain links or tiny reactions are not useful enough to process/archive.
    if len(compact) < 18 and not has_domain_signal(compact):
        return False, "too_short_without_domain_signal"

    for reason, pattern in LOW_VALUE_PATTERNS:
        if pattern.search(text) and not has_domain_signal(text):
            return False, reason

    # If a normal social post has no domain signal and mostly looks like a
    # general quote/status update, keep it out of the durable pipeline.
    if not has_domain_signal(text) and len(compact) < 90:
        return False, "no_domain_signal_short_social_post"

    return True, "kept"


def render_items(fm: dict, items: list[dict]) -> str:
    body_parts = []
    for item in items:
        title = item.get("title") or "Untitled"
        meta = item.get("meta") or f"source: {item.get('source', '')} · [link]({item.get('url', '')})"
        content = (item.get("content") or "").strip()
        body_parts.append(f"## {title}\n{meta}\n\n{content}".rstrip())
    fm = dict(fm)
    fm["items"] = str(len(items))
    return render_frontmatter(fm) + "\n\n".join(body_parts).strip() + "\n"


def single_item_from_markdown(text: str, fm: dict, source_path: Path) -> dict:
    title = str(fm.get("title") or source_path.stem)
    for line in text.splitlines():
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            break
        if line.startswith("## "):
            title = line.removeprefix("## ").strip()
            break
    return {
        "title": title,
        "url": str(fm.get("url") or fm.get("id") or ""),
        "content": text.strip(),
        "published": str(fm.get("published_at") or fm.get("published") or ""),
        "meta": f"source: {fm.get('source') or fm.get('source_name') or ''} · [link]({fm.get('url') or ''})",
        "source": str(fm.get("source") or fm.get("source_name") or ""),
        "author": str(fm.get("author") or fm.get("profile_name") or ""),
        "handle": "",
    }


def filter_markdown_items(text: str, fm: dict, source_path: Path) -> tuple[str | None, list[dict]]:
    items = parse_md_items(text)
    if not items:
        item = single_item_from_markdown(text, fm, source_path)
        keep, reason = should_keep_item(fm, item)
        if keep:
            return None, []
        return "", [{
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "source": item.get("source") or fm.get("source_name", ""),
            "file": str(source_path),
            "reason": reason,
        }]

    kept: list[dict] = []
    rejected: list[dict] = []
    for item in items:
        keep, reason = should_keep_item(fm, item)
        if keep:
            kept.append(item)
        else:
            rejected.append(
                {
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "source": item.get("source") or fm.get("source_name", ""),
                    "file": str(source_path),
                    "reason": reason,
                }
            )
    if not kept:
        return "", rejected
    if len(kept) == len(items):
        return None, []
    return render_items(fm, kept), rejected
