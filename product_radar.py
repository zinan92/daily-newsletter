#!/usr/bin/env python3
"""Build the Product Radar reader artifact.

Product Radar is the third Daily Inbox product: product-discovery and
build-direction intelligence from Product Hunt, Hacker News, and TrustMRR.
It intentionally stays separate from the main brief/deep-read AI pipeline.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import email.utils
import html
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import INBOX, SENT_DIR


PRODUCT_HUNT_FEED = "https://www.producthunt.com/feed"
TRUSTMRR_HOME = "https://trustmrr.com/"
TRUSTMRR_FAQ = "https://trustmrr.com/faq"
HN_API = "https://hacker-news.firebaseio.com/v0"

USER_AGENT = "Park-IO Product Radar/1.0 (+local source monitor)"


TAG_PATTERNS: dict[str, tuple[str, list[str]]] = {
    "ai_agents": (
        "AI Agent / 自动化",
        ["ai", "agent", "agents", "automation", "workflow", "assistant", "llm", "gpt", "claude", "prompt"],
    ),
    "devtools": (
        "开发者工具 / 基础设施",
        ["developer", "devtool", "api", "sdk", "code", "coding", "github", "database", "infra", "hosting", "deploy"],
    ),
    "growth_sales": (
        "增长 / 销售 / 获客",
        ["sales", "lead", "marketing", "seo", "email", "crm", "growth", "ads", "founder", "customer"],
    ),
    "revenue_saas": (
        "收入验证 / 微 SaaS",
        ["revenue", "mrr", "saas", "stripe", "subscription", "billing", "pricing", "marketplace", "startup"],
    ),
    "consumer_productivity": (
        "个人效率 / 消费产品",
        ["productivity", "calendar", "notes", "todo", "mobile", "app", "creator", "content", "video", "design"],
    ),
    "security_privacy": (
        "安全 / 隐私 / 可信执行",
        ["security", "privacy", "secure", "untrusted", "sandbox", "auth", "login", "credential", "fraud"],
    ),
    "data_research": (
        "数据 / 搜索 / 分析",
        ["data", "analytics", "search", "crawler", "scrape", "monitor", "research", "database", "ranking"],
    ),
}


@dataclass
class Signal:
    source: str
    title: str
    url: str
    summary: str = ""
    published: str = ""
    metric: str = ""
    kind: str = ""
    score: int = 0
    tags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def fetch_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def fetch_json(url: str, timeout: int = 30):
    return json.loads(fetch_text(url, timeout=timeout))


def strip_tags(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed
    except (TypeError, ValueError):
        return None


def utc_iso_from_unix(ts: int | float | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("/"):
        return urllib.parse.urljoin("https://trustmrr.com", url)
    return url


def money_to_number(value: str) -> float:
    raw = (value or "").replace(",", "").strip().lower()
    if not raw:
        return 0.0
    m = re.search(r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*([km])?", raw)
    if not m:
        return 0.0
    amount = float(m.group(1))
    suffix = m.group(2)
    if suffix == "k":
        amount *= 1_000
    elif suffix == "m":
        amount *= 1_000_000
    return amount


def tag_signal(text: str) -> list[str]:
    lower = text.lower()
    tags: list[str] = []
    for key, (_, patterns) in TAG_PATTERNS.items():
        if any(p in lower for p in patterns):
            tags.append(key)
    return tags


def score_signal(signal: Signal) -> Signal:
    text = " ".join([signal.title, signal.summary, signal.metric, signal.kind])
    tags = tag_signal(text)
    score = 20 + len(tags) * 8
    reasons: list[str] = []

    if signal.source == "Product Hunt":
        score += 12
        reasons.append("新产品供给")
    elif signal.source == "Hacker News":
        score += 8
        m_score = re.search(r"([0-9]+)\s+points?", signal.metric)
        m_comments = re.search(r"([0-9]+)\s+comments?", signal.metric)
        points = int(m_score.group(1)) if m_score else 0
        comments = int(m_comments.group(1)) if m_comments else 0
        if points:
            score += min(24, int(math.log(points + 1) * 5))
            reasons.append(f"HN {points} points")
        if comments:
            score += min(18, int(math.log(comments + 1) * 4))
            reasons.append(f"{comments} comments")
    elif signal.source == "TrustMRR":
        score += 16
        revenue = money_to_number(signal.metric)
        if revenue:
            score += min(28, int(math.log10(revenue + 10) * 6))
            reasons.append("收入已验证")

    if "ai_agents" in tags and "devtools" in tags:
        score += 8
        reasons.append("AI + devtools 交叉")
    if "revenue_saas" in tags:
        score += 6

    signal.tags = tags
    signal.score = score
    signal.reasons = reasons
    return signal


def parse_product_hunt_feed(atom_xml: str) -> list[Signal]:
    root = ET.fromstring(atom_xml)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    signals: list[Signal] = []
    for entry in root.findall("a:entry", ns):
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        published = (entry.findtext("a:published", default="", namespaces=ns) or "").strip()
        content = entry.findtext("a:content", default="", namespaces=ns) or ""
        summary = strip_tags(content)
        summary = re.split(r"\bDiscussion\b|\bLink\b", summary, maxsplit=1)[0].strip(" |")
        url = ""
        for link in entry.findall("a:link", ns):
            if link.attrib.get("rel") == "alternate" or not url:
                url = link.attrib.get("href", "")
        if not title or not url:
            continue
        signals.append(score_signal(Signal(
            source="Product Hunt",
            title=title,
            url=url,
            summary=summary,
            published=published,
            kind="new product",
        )))
    return signals


def fetch_product_hunt() -> tuple[list[Signal], dict]:
    raw = fetch_text(PRODUCT_HUNT_FEED)
    signals = parse_product_hunt_feed(raw)
    updated = ""
    try:
        root = ET.fromstring(raw)
        updated = root.findtext("{http://www.w3.org/2005/Atom}updated", default="")
    except ET.ParseError:
        pass
    return signals, {
        "source": "Product Hunt",
        "method": "official Atom feed",
        "url": PRODUCT_HUNT_FEED,
        "fetched": len(signals),
        "updated": updated,
    }


def hn_item_url(item_id: int) -> str:
    return f"{HN_API}/item/{item_id}.json"


def parse_hn_item(item: dict, list_name: str) -> Signal | None:
    if not item or item.get("deleted") or item.get("dead"):
        return None
    title = (item.get("title") or "").strip()
    if not title:
        return None
    url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('id')}"
    text = strip_tags(item.get("text") or "")
    points = int(item.get("score") or 0)
    comments = int(item.get("descendants") or 0)
    metric = f"{points} points · {comments} comments · {list_name}"
    summary = text[:240] if text else urllib.parse.urlparse(url).netloc
    return score_signal(Signal(
        source="Hacker News",
        title=title,
        url=url,
        summary=summary,
        published=utc_iso_from_unix(item.get("time")),
        metric=metric,
        kind=list_name,
    ))


def fetch_hacker_news(max_items: int = 140) -> tuple[list[Signal], dict]:
    story_lists = {
        "topstories": 70,
        "showstories": 30,
        "askstories": 25,
        "newstories": 30,
    }
    ids_by_list: dict[int, str] = {}
    errors: list[str] = []
    for list_name, limit in story_lists.items():
        try:
            ids = fetch_json(f"{HN_API}/{list_name}.json")[:limit]
            for item_id in ids:
                ids_by_list.setdefault(int(item_id), list_name)
        except Exception as exc:  # pragma: no cover - live network guard
            errors.append(f"{list_name}: {type(exc).__name__}")

    selected_ids = list(ids_by_list)[:max_items]
    items: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        future_map = {pool.submit(fetch_json, hn_item_url(item_id), 20): item_id for item_id in selected_ids}
        for fut in concurrent.futures.as_completed(future_map):
            try:
                item = fut.result()
                if isinstance(item, dict):
                    items.append(item)
            except Exception as exc:  # pragma: no cover - live network guard
                errors.append(f"item {future_map[fut]}: {type(exc).__name__}")

    signals = []
    for item in items:
        parsed = parse_hn_item(item, ids_by_list.get(int(item.get("id") or 0), "stories"))
        if parsed:
            signals.append(parsed)
    signals.sort(key=lambda s: s.score, reverse=True)
    return signals, {
        "source": "Hacker News",
        "method": "official Firebase API",
        "url": "https://github.com/HackerNews/API",
        "fetched": len(signals),
        "errors": errors[:8],
    }


def parse_trustmrr_homepage(page_html: str) -> list[Signal]:
    signals: list[Signal] = []
    seen: set[str] = set()
    # Product cards and rows are server-rendered into the HTML. Limit each match
    # to the nearest closing anchor; this is sufficient for cards and conservative
    # for rows with nested founder links.
    for match in re.finditer(r'<a\b[^>]*href="(/startup/[^"#?]+)"[^>]*>([\s\S]{0,9000}?)</a>', page_html):
        path, block = match.groups()
        slug = path.rsplit("/", 1)[-1]
        if slug in seen:
            continue
        seen.add(slug)
        title = ""
        for pattern in (
            r"<h3[^>]*>([\s\S]*?)</h3>",
            r'<div[^>]*class="[^"]*font-medium[^"]*"[^>]*>([\s\S]*?)</div>',
        ):
            m = re.search(pattern, block)
            if m:
                title = strip_tags(m.group(1))
                break
        if not title:
            alt = re.search(r'alt="([^"]+)"', block)
            title = html.unescape(alt.group(1)) if alt else slug.replace("-", " ").title()
        category = ""
        cat = re.search(r'<p[^>]*class="[^"]*text-\[10px\][^"]*"[^>]*>([\s\S]*?)</p>', block)
        if cat:
            category = strip_tags(cat.group(1))
        if not category:
            desc = re.search(r'<div[^>]*class="[^"]*text-xs text-muted-foreground[^"]*"[^>]*>([\s\S]*?)</div>', block)
            if desc:
                category = strip_tags(desc.group(1))

        revenue = ""
        price = ""
        multiple = ""
        rev = re.search(r"Revenue</p>\s*<p[^>]*>([^<]+)</p>", block)
        if rev:
            revenue = strip_tags(rev.group(1))
        price_m = re.search(r"Price</p>\s*<p[^>]*>([^<]+)</p>", block)
        if price_m:
            price = strip_tags(price_m.group(1))
        multi_m = re.search(r"Multiple</p>\s*<p[^>]*>([^<]+)</p>", block)
        if multi_m:
            multiple = strip_tags(multi_m.group(1))

        # Leaderboard rows expose MRR without a local label; if no card revenue
        # exists, grab the first visible money value inside the startup row.
        if not revenue:
            money = re.search(r">\s*(\$[0-9][0-9,.]*[kmKM]?)\s*<", block)
            if money:
                revenue = money.group(1)

        metric_parts = []
        if revenue:
            metric_parts.append(f"Revenue/MRR {revenue}")
        if price:
            metric_parts.append(f"Price {price}")
        if multiple:
            metric_parts.append(f"Multiple {multiple}")
        metric = " · ".join(metric_parts)
        summary_parts = [p for p in [category, metric] if p]
        signals.append(score_signal(Signal(
            source="TrustMRR",
            title=title,
            url=normalize_url(path),
            summary="；".join(summary_parts),
            metric=metric,
            kind="verified revenue",
        )))
    signals.sort(key=lambda s: s.score, reverse=True)
    return signals


def fetch_trustmrr() -> tuple[list[Signal], dict]:
    raw = fetch_text(TRUSTMRR_HOME)
    signals = parse_trustmrr_homepage(raw)
    api_note = "public scrape"
    try:
        faq = fetch_text(TRUSTMRR_FAQ, timeout=20)
        if "TrustMRR API" in faq and "Bearer tmrr_" in faq:
            api_note = "public scrape; API exists but needs tmrr_ key"
    except Exception:
        pass
    return signals, {
        "source": "TrustMRR",
        "method": api_note,
        "url": TRUSTMRR_HOME,
        "fetched": len(signals),
    }


def top_signals(signals: list[Signal], source: str, limit: int = 8) -> list[Signal]:
    rows = [s for s in signals if s.source == source]
    rows.sort(key=lambda s: s.score, reverse=True)
    return rows[:limit]


def tag_label(tag: str) -> str:
    return TAG_PATTERNS.get(tag, (tag, []))[0]


def group_tag_counts(signals: list[Signal]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for sig in signals:
        for tag in sig.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def format_metric(sig: Signal) -> str:
    pieces = []
    if sig.metric:
        pieces.append(sig.metric)
    if sig.reasons:
        pieces.append(" / ".join(sig.reasons[:2]))
    return "；".join(pieces)


def source_item_line(sig: Signal) -> str:
    summary = sig.summary.strip()
    if len(summary) > 110:
        summary = summary[:107].rstrip() + "..."
    metric = format_metric(sig)
    suffix = f"｜{metric}" if metric else ""
    return f"- **[{sig.title}]({sig.url})**：{summary or sig.kind}{suffix}"


def opportunity_title(tag: str) -> str:
    return {
        "ai_agents": "把 AI 从“能生成”推进到“能代办、能复盘、能交付”",
        "devtools": "为 AI 生成代码后的运行、测试、安全和部署补基础设施",
        "growth_sales": "用 AI 做更窄的获客、线索和内容转化工作台",
        "revenue_saas": "从已收钱的微 SaaS 反推小而硬的付费问题",
        "consumer_productivity": "把个人效率产品做成更低摩擦的日常入口",
        "security_privacy": "围绕可信执行、隐私和权限边界做开发者级产品",
        "data_research": "把数据监控、搜索和变化发现做成决策前置雷达",
    }.get(tag, tag_label(tag))


def opportunity_action(tag: str) -> str:
    return {
        "ai_agents": "先选一个高频工作流，做“输入源 → 自动处理 → 人审 → 输出”的端到端闭环，避免只做聊天壳。",
        "devtools": "优先做 AI coding 后链路：sandbox、日志、测试、权限、部署或回滚，而不是再做一个编辑器。",
        "growth_sales": "用垂直行业的公开数据和真实销售动作定义产品，先证明线索能转化，再补自动化。",
        "revenue_saas": "用 TrustMRR 的收入/售价/倍数找低估的小产品，再拆解它们解决的刚需和获客来源。",
        "consumer_productivity": "切入口要足够日常，最好能拿到用户已有内容或日程作为输入，而不是让用户重新建系统。",
        "security_privacy": "把“AI 生成内容不可完全信任”作为需求起点，卖可信执行、隔离和审计能力。",
        "data_research": "做面向产品经理/创始人的监控面板：从新产品、讨论热度和收入信号中自动产出 build brief。",
    }.get(tag, "先做一个小闭环验证付费意愿，再扩大源和自动化。")


def build_opportunities(signals: list[Signal], limit: int = 4) -> list[dict]:
    by_tag: dict[str, list[Signal]] = {}
    for sig in signals:
        for tag in sig.tags:
            by_tag.setdefault(tag, []).append(sig)
    ranked = []
    for tag, rows in by_tag.items():
        source_bonus = len({r.source for r in rows}) * 12
        score = sum(r.score for r in rows[:8]) + source_bonus
        ranked.append((score, tag, rows))
    ranked.sort(reverse=True, key=lambda x: x[0])

    out = []
    used_urls: set[str] = set()
    for _, tag, rows in ranked[:limit]:
        rows.sort(key=lambda s: s.score, reverse=True)
        evidence = []
        used_sources = set()
        for source in ["Product Hunt", "TrustMRR", "Hacker News"]:
            source_rows = [r for r in rows if r.source == source and r.url not in used_urls]
            if not source_rows:
                source_rows = [r for r in rows if r.source == source]
            if source_rows:
                evidence.append(source_rows[0])
                used_sources.add(source)
        if len(evidence) < 2:
            for row in rows:
                if row not in evidence and row.url not in used_urls:
                    evidence.append(row)
                if len(evidence) >= 3:
                    break
        if len(evidence) < 2:
            for row in rows:
                if row not in evidence:
                    evidence.append(row)
                if len(evidence) >= 3:
                    break
        used_urls.update(e.url for e in evidence)
        out.append({
            "tag": tag,
            "title": opportunity_title(tag),
            "action": opportunity_action(tag),
            "evidence": evidence[:3],
            "sources": sorted(used_sources),
        })
    return out


def data_quality_lines(meta: list[dict]) -> list[str]:
    lines = []
    for row in meta:
        errors = row.get("errors") or []
        status = "OK" if row.get("fetched", 0) else "PARTIAL"
        detail = f"{row['source']}：{status}，{row.get('method')}，抓到 {row.get('fetched', 0)} 条"
        if errors:
            detail += f"，错误 {len(errors)} 个"
        lines.append(f"- {detail}。")
    lines.append("- TrustMRR 当前使用公开页面抓取；它有 API，但需要登录生成 `tmrr_` key，未配置前不假装是 API 数据。")
    return lines


def render_markdown(
    signals: list[Signal],
    meta: list[dict],
    run_date: str,
    *,
    total_signals: int | None = None,
    repeated_signals: int = 0,
) -> str:
    counts = group_tag_counts(signals)
    top_tags = "、".join(tag_label(tag) for tag, _ in counts[:3]) or "暂无稳定主题"
    ph = top_signals(signals, "Product Hunt", 8)
    tmrr = top_signals(signals, "TrustMRR", 8)
    hn = top_signals(signals, "Hacker News", 10)
    opportunities = build_opportunities(signals)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: list[str] = [
        f"# 产品雷达 — {run_date}",
        "",
        "## 今日判断",
        f"- 今天的新增产品信号集中在 **{top_tags}**。Product Hunt 负责发现“新供给”，Hacker News 负责暴露“真实需求和争议”，TrustMRR 负责验证“哪些小产品真的在收钱”。",
        "- 读法不是追热点，而是回答一个问题：**我们现在应该考虑造什么，为什么这个方向可能有人付钱。**",
        "",
        "## 可行动机会",
    ]

    if opportunities:
        for idx, opp in enumerate(opportunities, 1):
            lines.append(f"### {idx}. {opp['title']}")
            evidence = "；".join(f"{e.source} 的 [{e.title}]({e.url})" for e in opp["evidence"])
            lines.append(f"- **证据**：{evidence}。")
            lines.append(f"- **切入方式**：{opp['action']}")
            lines.append("")
    else:
        lines.append("- 今天没有足够新的产品/需求/收入信号形成可行动机会。")
        lines.append("")

    lines.extend([
        "## 新产品雷达（Product Hunt）",
        "",
    ])
    lines.extend(source_item_line(sig) for sig in ph)
    if not ph:
        lines.append("- Product Hunt feed 本次没有新增产品；重复出现的滚动榜单条目已从读者版隐藏。")

    lines.extend([
        "",
        "## 真实收入信号（TrustMRR）",
        "",
    ])
    lines.extend(source_item_line(sig) for sig in tmrr)
    if not tmrr:
        lines.append("- TrustMRR 本次没有新增收入信号；重复出现的在售项目已从读者版隐藏。")

    lines.extend([
        "",
        "## 需求与痛点（Hacker News）",
        "",
    ])
    lines.extend(source_item_line(sig) for sig in hn)
    if not hn:
        lines.append("- Hacker News API 本次没有新增可用条目。")

    lines.extend([
        "",
        "## 信号分布",
        "",
    ])
    for tag, count in counts[:8]:
        lines.append(f"- **{tag_label(tag)}**：{count} 条")
    if not counts:
        lines.append("- 暂无可统计标签。")

    lines.extend([
        "",
        "## 数据质量",
        "",
        *data_quality_lines(meta),
        f"- 读者版新增信号：{len(signals)} 条；完整抓取快照：{total_signals if total_signals is not None else len(signals)} 条；隐藏近期重复：{repeated_signals} 条。",
        f"- 生成时间：{generated}。",
        "",
    ])
    return "\n".join(lines).rstrip() + "\n"


def write_html(markdown: str, html_path: Path, run_date: str) -> None:
    try:
        from aggregation.digest.summarize import render_html_from_markdown

        html_text = render_html_from_markdown(markdown, run_date, [], html_path.parent)
    except Exception:
        body = "\n".join(f"<p>{html.escape(line)}</p>" for line in markdown.splitlines())
        html_text = f"<!doctype html><meta charset='utf-8'><body>{body}</body>"
    html_path.write_text(html_text, encoding="utf-8")


def trim_png_tail(path: Path, margin: int = 72, tolerance: int = 18) -> None:
    """Crop the long uniform tail Chrome sometimes leaves on dark pages."""
    try:
        from PIL import Image
    except ModuleNotFoundError:
        return
    if not path.exists():
        return
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        if height <= 1400:
            return
        bg = rgb.getpixel((max(width - 2, 0), height - 2))
        x_step = max(width // 180, 1)
        threshold = max(width // x_step // 80, 8)

        def row_has_content(y: int) -> bool:
            changed = 0
            for x in range(0, width, x_step):
                pixel = rgb.getpixel((x, y))
                if any(abs(pixel[i] - bg[i]) > tolerance for i in range(3)):
                    changed += 1
                    if changed >= threshold:
                        return True
            return False

        last_content_y = height - 1
        for y in range(height - 1, 0, -1):
            if row_has_content(y):
                last_content_y = y
                break
        crop_bottom = min(height, last_content_y + margin)
        if crop_bottom < height - 100:
            img.crop((0, 0, width, crop_bottom)).save(path)


def render_png(html_path: Path, png_path: Path) -> bool:
    try:
        from aggregation.digest.html_to_long_image import render_with_chrome_cli

        for attempt in range(2):
            try:
                render_with_chrome_cli(html_path, png_path, 1200)
                trim_png_tail(png_path)
                return True
            except Exception:
                if attempt == 0:
                    time.sleep(2)
                    continue
                raise
    except Exception:
        return False


def collect_signals() -> tuple[list[Signal], list[dict]]:
    collectors = [fetch_product_hunt, fetch_trustmrr, fetch_hacker_news]
    all_signals: list[Signal] = []
    meta: list[dict] = []
    for collector in collectors:
        started = time.time()
        try:
            signals, row = collector()
            row["duration_sec"] = round(time.time() - started, 2)
            all_signals.extend(signals)
            meta.append(row)
        except Exception as exc:
            meta.append({
                "source": collector.__name__.replace("fetch_", ""),
                "method": "unknown",
                "url": "",
                "fetched": 0,
                "errors": [f"{type(exc).__name__}: {exc}"],
                "duration_sec": round(time.time() - started, 2),
            })
    all_signals.sort(key=lambda s: s.score, reverse=True)
    return dedupe_signals(all_signals), meta


def dedupe_signals(signals: list[Signal]) -> list[Signal]:
    seen: set[str] = set()
    out: list[Signal] = []
    for sig in signals:
        key = sig.url.rstrip("/") or f"{sig.source}:{sig.title.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(sig)
    return out


def signal_key(signal: Signal | dict) -> str:
    if isinstance(signal, dict):
        url = str(signal.get("url") or "").strip().rstrip("/")
        source = str(signal.get("source") or "")
        title = str(signal.get("title") or "")
    else:
        url = signal.url.strip().rstrip("/")
        source = signal.source
        title = signal.title
    return url or f"{source}:{title}".lower()


def previous_signal_keys(run_date: str, *, lookback_days: int = 14) -> set[str]:
    try:
        current = datetime.strptime(run_date, "%Y-%m-%d").date()
    except ValueError:
        return set()
    since = current - timedelta(days=lookback_days)
    keys: set[str] = set()
    raw_root = INBOX / "raw"
    if not raw_root.exists():
        return keys
    for path in raw_root.glob("*/product-radar.json"):
        try:
            date = datetime.strptime(path.parent.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (since <= date < current):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in data.get("signals", []):
            key = signal_key(row)
            if key:
                keys.add(key)
    return keys


def new_signals_only(signals: list[Signal], previous_keys: set[str]) -> list[Signal]:
    return [sig for sig in signals if signal_key(sig) not in previous_keys]


def write_snapshot(signals: list[Signal], meta: list[dict], run_date: str) -> Path:
    raw_dir = INBOX / "raw" / run_date
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / "product-radar.json"
    path.write_text(json.dumps({
        "date": run_date,
        "generated_at": datetime.now().isoformat(),
        "meta": meta,
        "signals": [asdict(s) for s in signals],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def product_radar_paths(run_date: str) -> tuple[Path, Path, Path]:
    label = datetime.strptime(run_date, "%Y-%m-%d").strftime("%y-%m-%d")
    return (
        SENT_DIR / f"product-radar-{label}.md",
        SENT_DIR / f"product-radar-{label}.html",
        SENT_DIR / f"product-radar-{label}.png",
    )


def build_product_radar(run_date: str, *, with_png: bool = True) -> dict:
    signals, meta = collect_signals()
    previous_keys = previous_signal_keys(run_date)
    reader_signals = new_signals_only(signals, previous_keys)
    markdown = render_markdown(
        reader_signals,
        meta,
        run_date,
        total_signals=len(signals),
        repeated_signals=len(signals) - len(reader_signals),
    )
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    md_path, html_path, png_path = product_radar_paths(run_date)
    md_path.write_text(markdown, encoding="utf-8")
    write_html(markdown, html_path, run_date)
    png_ok = render_png(html_path, png_path) if with_png else False
    raw_path = write_snapshot(signals, meta, run_date)
    return {
        "markdown": str(md_path),
        "html": str(html_path),
        "png": str(png_path) if png_ok else "",
        "raw": str(raw_path),
        "signals": len(signals),
        "reader_signals": len(reader_signals),
        "repeated_signals": len(signals) - len(reader_signals),
        "meta": meta,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Product Radar from Product Hunt, TrustMRR, and Hacker News.")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--no-png", action="store_true", help="Skip long-image rendering.")
    args = parser.parse_args(argv)

    result = build_product_radar(args.date, with_png=not args.no_png)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
