"""Event identity and grouping rules for Park-IO digest generation."""

import json
import os
import re

from digest_config import OFFICIAL_CATEGORY_ORDER, SOURCE_AUTHORITY, SOURCE_ROLES


def normalized_topic_text(item: dict) -> str:
    values = [
        item.get("source", ""),
        item.get("title", ""),
        item.get("content", ""),
        " ".join(item.get("tags", [])),
    ]
    return " ".join(values).lower()


def source_role_for_item(item: dict) -> str:
    return SOURCE_ROLES.get(item.get("source", ""), "other")


def stable_item_key(item: dict) -> str:
    return item.get("url") or item.get("id") or item.get("title") or "unknown"


def is_manually_curated(item: dict) -> bool:
    return source_role_for_item(item) in {"user_saved", "wechat_article"}


def can_use_canonical_event_rules(item: dict) -> bool:
    role = source_role_for_item(item)
    source = item.get("source", "")
    return (
        role in {"company_official", "company_person"}
        or source in {"claude-code-releases", "openai-codex-releases"}
    )


def event_key(item: dict) -> str:
    """Deterministic identity for an item. Cross-source same-event MERGING is
    handled separately by semantic clustering in build_events — this function
    only assigns a stable, unique-by-default identity. (The old ~40 hardcoded
    keyword rules were brittle and rotted; they were replaced by _semantic_cluster.)
    """
    source = item.get("source", "")
    url = item.get("url", "")

    if is_manually_curated(item):
        return stable_item_key(item)
    if source == "claude-code-releases":
        return url or item.get("title") or "claude-code-release"
    if source == "openai-codex-releases":
        return url or item.get("title") or "openai-codex-release"
    if source in {"Claude Blog", "OpenAI Blog"}:
        return url or item.get("title") or "official-blog-post"
    if SOURCE_ROLES.get(source) in {"application_practice", "creator_growth"} and "闲鱼" in normalized_topic_text(item):
        return f"{source}:xianyu-practice"
    if SOURCE_ROLES.get(source) in {"application_practice", "creator_growth"}:
        return url or item.get("title") or "application-practice"
    # Unique by default: items only merge via semantic clustering or thread id,
    # never by an incidental shared tag.
    return url or item.get("title") or "unknown"


def source_rank(item: dict) -> int:
    return SOURCE_AUTHORITY.get(item.get("source", ""), 50)


def line_union(items: list[dict]) -> list[str]:
    order = ["development", "trading", "content"]
    seen = {line for item in items for line in item.get("line_fit", [])}
    return [line for line in order if line in seen]


def tags_union(items: list[dict]) -> list[str]:
    tags = []
    for item in items:
        for tag in item.get("tags", []):
            if tag not in tags:
                tags.append(tag)
    return tags[:4]


def conversation_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        conv = item.get("conversation_id", "")
        if conv:
            counts[conv] = counts.get(conv, 0) + 1
    return counts


_SEM_CACHE: dict = {}


def _parse_group_json(raw: str, n: int) -> list[list[int]]:
    """Extract a JSON list-of-lists of indices from the model output."""
    raw = (raw or "").strip()
    candidates = [raw]
    m = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    if m:
        candidates.insert(0, m.group(1).strip())
    m = re.search(r"\[\s*\[.*\]\s*\]", raw, re.DOTALL)
    if m:
        candidates.insert(0, m.group(0))
    for c in candidates:
        try:
            data = json.loads(c)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list) and all(isinstance(g, list) for g in data):
            return [[i for i in g if isinstance(i, int) and 0 <= i < n] for g in data]
    return []


def _semantic_cluster(items: list[dict]) -> dict[str, str]:
    """Group official/code/people items that report the SAME event (e.g. an
    official post + someone reposting it) using one LLM judgment call. Replaces
    the old hardcoded keyword cascade so clustering can't rot.

    Returns {url: shared_event_key} only for items that actually merge (group
    size >= 2). Safe by design: disabled via PARKIO_SEMANTIC_CLUSTER=0, cached
    per candidate-set, and on any failure returns {} (no merge — items stay
    distinct rather than crashing the digest).
    """
    if os.environ.get("PARKIO_SEMANTIC_CLUSTER", "1") != "1":
        return {}
    candidates = [it for it in items if can_use_canonical_event_rules(it) and it.get("url")]
    if len(candidates) < 2:
        return {}
    cache_key = frozenset(it["url"] for it in candidates)
    if cache_key in _SEM_CACHE:
        return _SEM_CACHE[cache_key]

    lines = []
    for i, it in enumerate(candidates):
        title = (it.get("title") or "")[:120]
        snippet = (it.get("content") or "")[:280]
        lines.append(f"[{i}] 来源:{it.get('source','')} | 标题:{title} | 摘要:{snippet}")
    prompt = (
        "下面是若干条 AI 行业资讯。请把**报道同一件事/同一公告**的条目分到同一组"
        "（例如官方账号发布 + 另一个人转发同一条消息/同一功能）。\n"
        "规则：只有明确是同一事件才合并；不确定就让它单独成组。\n"
        "只输出 JSON：一个数组，每个元素是该组的编号数组，必须覆盖 0.."
        f"{len(candidates) - 1} 的每个编号且不重复，例如 [[0,3],[1],[2,4]]。不要解释。\n\n"
        + "\n".join(lines)
    )
    mapping: dict[str, str] = {}
    try:
        from lib import llm_call

        groups = _parse_group_json(llm_call(prompt, max_tokens=1500), len(candidates))
        for group in groups:
            if len(group) >= 2:
                anchor = candidates[group[0]]["url"]
                for idx in group:
                    mapping[candidates[idx]["url"]] = f"event:{anchor}"
    except Exception:
        mapping = {}
    _SEM_CACHE[cache_key] = mapping
    return mapping


def build_events(items: list[dict], limit: int | None = 8, title_func=None) -> list[dict]:
    title_func = title_func or (lambda item: item.get("title", ""))
    # Same-thread tweets (>=2 in this batch sharing a conversation_id) merge into
    # one event (gotcha #9) — the parent tweet plus its replies. Standalone
    # tweets keep their normal event_key, so cross-source keyword merges are
    # unaffected (gotcha #10). Only fetches that captured conversation_id carry
    # it; older items have none and fall through unchanged.
    conv_counts = conversation_counts(items)
    # Semantic same-event grouping for official/code/people items (replaces the
    # old keyword cascade). {url: shared_key}; empty if disabled or on failure.
    sem = _semantic_cluster(items)
    buckets: dict[str, list[dict]] = {}
    for item in items:
        conv = item.get("conversation_id", "")
        url = item.get("url", "")
        if conv and conv_counts.get(conv, 0) >= 2:
            key = f"thread:{conv}"
        elif url and url in sem:
            key = sem[url]
        else:
            key = event_key(item)
        bucket = buckets.setdefault(key, [])
        if item.get("url") and any(existing.get("url") == item.get("url") for existing in bucket):
            continue
        bucket.append(item)

    events = []
    for key, group in buckets.items():
        group = sorted(
            group,
            key=lambda it: (-it.get("score", 3), -source_rank(it), it.get("title", "")),
        )
        primary = group[0]
        events.append(
            {
                "event_key": key,
                "items": group,
                "primary": primary,
                "score": max(it.get("score", 3) for it in group),
                "line_fit": line_union(group),
                "tags": tags_union(group),
            }
        )
    events.sort(
        key=lambda ev: (
            -ev["score"],
            -max(source_rank(it) for it in ev["items"]),
            title_func(ev["primary"]),
        )
    )
    if limit is None:
        return events
    return events[:limit]


def event_sources(event: dict) -> set[str]:
    return {item.get("source", "") for item in event.get("items", [])}


def source_role(name: str) -> str:
    return SOURCE_ROLES.get(name, "other")


def event_layer(event: dict) -> str:
    roles = {source_role(name) for name in event_sources(event)}
    if "longform_interview" in roles:
        return "长访谈 / 深度理解"
    if "user_saved" in roles:
        return "我的收藏"
    if "wechat_article" in roles:
        return "公众号文章"
    if roles & {"application_practice", "creator_growth"}:
        return "应用层实践"
    return "厂商动态"


def event_company(event: dict) -> str:
    source = event["primary"].get("source", "")
    if source in {"OpenAI X", "ChatGPT X", "OpenAI Blog", "OpenAI YouTube", "ChatGPT YouTube", "openai-codex-releases", "Sam Altman", "Greg Brockman", "Kevin Weil", "Mark Chen"}:
        return "OpenAI / ChatGPT / Codex"
    if source in {"Anthropic News", "Anthropic Engineering", "Claude Blog", "Anthropic X", "Claude X", "Claude Devs X", "Anthropic YouTube", "Claude YouTube", "claude-code-releases", "Dario Amodei", "Daniela Amodei", "Mike Krieger"}:
        return "Anthropic / Claude"
    text = normalized_topic_text(event["primary"]) + " " + " ".join(event.get("tags", []))
    key = event.get("event_key", "")
    if key.startswith("openai-") or "openai" in text or "chatgpt" in text or "codex" in text:
        return "OpenAI / ChatGPT / Codex"
    if "claude" in text or "anthropic" in text:
        return "Anthropic / Claude"
    if "google" in text or "gemini" in text:
        return "Google / Gemini"
    if "xai" in text or "grok" in text:
        return "xAI / Grok"
    if "meta" in text or "llama" in text:
        return "Meta / Llama"
    return "其他厂商"


def event_official_category(event: dict) -> str:
    key = event.get("event_key", "")
    text = normalized_topic_text(event["primary"]) + " " + " ".join(event.get("tags", []))
    source = event["primary"].get("source", "")
    if source in {"claude-code-releases", "openai-codex-releases"}:
        return "开发与集成层"
    if key in {
        "openai-chatgpt-codex-mobile",
        "codex-goal-command",
        "claude-design-token-limits",
        "claude-small-business",
    }:
        return "产品体验层"
    if key in {
        "anthropic-claude-code-toolchain-update",
        "anthropic-stainless-acquisition",
        "claude-prompt-cache-diagnostics",
        "codex-windows-sandbox",
    }:
        return "开发与集成层"
    if key in {"claude-usage-credits", "codex-enterprise-adoption", "openai-guaranteed-capacity"} or any(
        word in text for word in ("usage credit", "credits", "rate limit", "quota", "trial", "pricing", "计费", "额度", "限额", "免费试用", "企业试用")
    ):
        return "商业化与使用规则层"
    if any(word in text for word in ("model", "gpt-realtime", "realtime", "opus", "haiku", "sonnet", "性能", "速度", "latency", "上下文")):
        return "模型与性能层"
    if any(word in text for word in ("pwc", "stainless", "acquires", "acquisition", "partnership", "合作", "收购", "生态", "企业采用")):
        return "外部合作与生态信号"
    return "产品体验层"


def group_official_events_by_category(events: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {name: [] for name in OFFICIAL_CATEGORY_ORDER}
    for event in events:
        category = event_official_category(event)
        groups.setdefault(category, []).append(event)
    return [(name, groups[name]) for name in OFFICIAL_CATEGORY_ORDER if groups.get(name)]


def event_practice_group(event: dict) -> str:
    text = normalized_topic_text(event["primary"]) + " " + " ".join(event.get("tags", []))
    if any(word in text for word in ("xiaohongshu", "douyin", "content", "内容", "小红书", "抖音")):
        return "内容与分发实践"
    return "工具用法 / 产品实践"


def group_events_for_digest(events: list[dict]) -> list[tuple[str, list[dict]]]:
    order = [
        "厂商动态 / Anthropic / Claude",
        "厂商动态 / OpenAI / ChatGPT / Codex",
        "厂商动态 / Google / Gemini",
        "厂商动态 / xAI / Grok",
        "厂商动态 / Meta / Llama",
        "厂商动态 / 其他厂商",
        "我的收藏",
        "公众号文章",
        "应用层实践 / 工具用法 / 产品实践",
        "应用层实践 / 内容与分发实践",
    ]
    groups: dict[str, list[dict]] = {name: [] for name in order}
    for event in events:
        layer = event_layer(event)
        if layer == "厂商动态":
            key = f"{layer} / {event_company(event)}"
        elif layer == "应用层实践":
            key = f"{layer} / {event_practice_group(event)}"
        else:
            key = layer
        groups.setdefault(key, []).append(event)
    return [(name, groups[name]) for name in order if groups.get(name)]


def group_official_events(events: list[dict]) -> list[tuple[str, list[dict]]]:
    order = [
        "Anthropic / Claude",
        "OpenAI / ChatGPT / Codex",
        "Google / Gemini",
        "xAI / Grok",
        "Meta / Llama",
        "其他厂商",
    ]
    groups: dict[str, list[dict]] = {name: [] for name in order}
    for event in events:
        company = event_company(event)
        groups.setdefault(company, []).append(event)
    return [(name, groups[name]) for name in order if groups.get(name)]
