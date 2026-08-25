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
from typing import Any, Callable

from lib import INBOX, PROCESSED_DIR, SENT_DIR, llm_call


PRODUCT_HUNT_FEED = "https://www.producthunt.com/feed"
TRUSTMRR_HOME = "https://trustmrr.com/"
TRUSTMRR_FAQ = "https://trustmrr.com/faq"
HN_API = "https://hacker-news.firebaseio.com/v0"

USER_AGENT = "Park-IO Product Radar/1.0 (+local source monitor)"
PRODUCT_RADAR_PROMPT = Path(__file__).resolve().parent / "prompts" / "product-radar" / "top-three.md"
MAX_PRODUCT_CHOICES = 3
MAX_SIGNALS_PER_SOURCE = 12


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


@dataclass(frozen=True)
class ProductChoice:
    name: str
    value: str
    evidence_ids: tuple[str, ...] = ()


class ProductRadarAIError(RuntimeError):
    """Raised when the AI cannot produce a valid Product Radar selection."""

    def __init__(self, message: str, *, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


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
        if any(pattern_matches(lower, p) for p in patterns):
            tags.append(key)
    return tags


def pattern_matches(text: str, pattern: str) -> bool:
    if re.fullmatch(r"[a-z0-9_+-]+", pattern):
        return re.search(rf"(?<![a-z0-9]){re.escape(pattern)}(?![a-z0-9])", text) is not None
    return pattern in text


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


GENERIC_PRODUCT_FRAGMENTS = (
    "把 AI 从“能生成”推进到“能代办、能复盘、能交付”",
    "AI coding 后链路基础设施",
    "为 AI 生成代码后的运行、测试、安全和部署补基础设施",
)
SOURCE_NAMES = ("Product Hunt", "TrustMRR", "Hacker News")


def prompt_signals(signals: list[Signal]) -> list[dict[str, Any]]:
    selected: list[Signal] = []
    for source in SOURCE_NAMES:
        rows = sorted((s for s in signals if s.source == source), key=lambda s: s.score, reverse=True)
        selected.extend(rows[:MAX_SIGNALS_PER_SOURCE])
    selected.sort(key=lambda s: s.score, reverse=True)
    return [
        {
            "id": f"signal-{idx:03d}",
            "source": sig.source,
            "title": sig.title,
            "summary": sig.summary,
            "metric": sig.metric,
            "kind": sig.kind,
            "url": sig.url,
        }
        for idx, sig in enumerate(selected, 1)
    ]


def extract_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ProductRadarAIError("empty Product Radar AI response")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ProductRadarAIError("Product Radar AI response did not contain JSON")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ProductRadarAIError("Product Radar AI response contained invalid JSON") from exc
    if not isinstance(data, dict):
        raise ProductRadarAIError("Product Radar AI response must be a JSON object")
    return data


def parse_product_choices(raw: str, valid_evidence_ids: set[str]) -> list[ProductChoice]:
    data = extract_json_object(raw)
    rows = data.get("products")
    if not isinstance(rows, list):
        raise ProductRadarAIError("Product Radar AI response must contain a products array")
    if len(rows) > MAX_PRODUCT_CHOICES:
        raise ProductRadarAIError(f"Product Radar AI returned more than {MAX_PRODUCT_CHOICES} products")

    choices: list[ProductChoice] = []
    seen_names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ProductRadarAIError("each Product Radar product must be an object")
        name = str(row.get("name") or "").strip()
        value = str(row.get("value") or "").strip()
        if not name or not value or "\n" in name or "\n" in value:
            raise ProductRadarAIError("each Product Radar product needs a one-line name and value")
        if "*" in name or "*" in value:
            raise ProductRadarAIError("Product Radar reader text cannot contain Markdown emphasis")
        if any(source.lower() in f"{name} {value}".lower() for source in SOURCE_NAMES):
            raise ProductRadarAIError("Product Radar reader text cannot expose source names")
        if any(fragment in f"{name} {value}" for fragment in GENERIC_PRODUCT_FRAGMENTS):
            raise ProductRadarAIError("Product Radar AI returned a banned generic product direction")
        name_key = name.casefold()
        if name_key in seen_names:
            raise ProductRadarAIError("Product Radar AI returned duplicate products")
        seen_names.add(name_key)

        evidence = row.get("evidence_ids") or []
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            raise ProductRadarAIError("Product Radar evidence_ids must be an array of strings")
        unknown = set(evidence) - valid_evidence_ids
        if unknown:
            raise ProductRadarAIError(f"Product Radar AI referenced unknown evidence ids: {sorted(unknown)}")
        choices.append(ProductChoice(name=name, value=value, evidence_ids=tuple(evidence)))
    return choices


def generate_product_choices(
    signals: list[Signal],
    recent_product_names: set[str] | None = None,
    *,
    client: Callable[..., str] | None = None,
) -> tuple[list[ProductChoice], str, list[dict[str, Any]]]:
    rows = prompt_signals(signals)
    if not rows:
        return [], "", []
    prompt = PRODUCT_RADAR_PROMPT.read_text(encoding="utf-8")
    payload = {
        "recent_product_names": sorted(recent_product_names or set()),
        "signals": rows,
    }
    client = client or llm_call
    raw = client(prompt + "\n\nINPUT JSON:\n" + json.dumps(payload, ensure_ascii=False), max_tokens=1800, timeout=180)
    try:
        choices = parse_product_choices(raw, {row["id"] for row in rows})
    except ProductRadarAIError as exc:
        raise ProductRadarAIError(str(exc), raw_response=raw) from exc
    return choices, raw, rows


def render_markdown(choices: list[ProductChoice], run_date: str) -> str:
    if len(choices) > MAX_PRODUCT_CHOICES:
        raise ValueError(f"Product Radar supports at most {MAX_PRODUCT_CHOICES} reader choices")
    heading = "## Top Three Products to Build Today" if choices else "## No New Build Choices Today"
    lines = [
        f"# 产品雷达 — {run_date}",
        "",
        heading,
        "",
    ]
    if choices:
        lines.extend(f"{idx}. {choice.name}：{choice.value}" for idx, choice in enumerate(choices, 1))
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


def previous_product_names(run_date: str, *, lookback_days: int = 3) -> set[str]:
    try:
        current = datetime.strptime(run_date, "%Y-%m-%d").date()
    except ValueError:
        return set()
    since = current - timedelta(days=lookback_days)
    titles: set[str] = set()
    for path in SENT_DIR.glob("*.md"):
        match = re.fullmatch(r"(\d{2})-(\d{2})-(\d{2})\.md", path.name)
        if not match:
            continue
        year, month, day = match.groups()
        try:
            date = datetime.strptime(f"20{year}-{month}-{day}", "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (since <= date < current):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        section_match = re.search(r"^## 产品雷达\s*$([\s\S]*?)(?=^##\s|\Z)", text, flags=re.M)
        if not section_match:
            continue
        section = section_match.group(1)
        titles.update(re.findall(r"^\d+\.\s+([^：:\n]+)[：:]", section, flags=re.M))
        # Read the pre-Top-Three format during the three-day migration window.
        titles.update(re.findall(r"^###\s+\d+\.\s+(.+?)\s*$", section, flags=re.M))
    return titles


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
    base = PROCESSED_DIR / label
    return (
        base / f"product-radar-{label}.md",
        base / f"product-radar-{label}.html",
        base / f"product-radar-{label}.png",
    )


def build_product_radar(run_date: str, *, with_html: bool = False, with_png: bool = False) -> dict:
    signals, meta = collect_signals()
    previous_keys = previous_signal_keys(run_date)
    recent_names = previous_product_names(run_date)
    reader_signals = new_signals_only(signals, previous_keys)
    md_path, html_path, png_path = product_radar_paths(run_date)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path = md_path.parent / "product-radar-selection.json"
    raw_response_path = md_path.parent / "product-radar-raw-response.md"
    error_path = md_path.parent / "product-radar-error.json"
    for stale_path in (md_path, selection_path, raw_response_path, error_path):
        stale_path.unlink(missing_ok=True)
    try:
        choices, raw_response, prompt_rows = generate_product_choices(reader_signals, recent_names)
    except Exception as exc:
        error_path.write_text(json.dumps({
            "date": run_date,
            "error": f"{type(exc).__name__}: {exc}",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_response = getattr(exc, "raw_response", "")
        if raw_response:
            raw_response_path.write_text(raw_response, encoding="utf-8")
        raise
    markdown = render_markdown(choices, run_date)
    md_path.write_text(markdown, encoding="utf-8")
    selection_path.write_text(json.dumps({
        "date": run_date,
        "generated_at": datetime.now().isoformat(),
        "products": [asdict(choice) for choice in choices],
        "input_signals": prompt_rows,
        "recent_product_names": sorted(recent_names),
        "source_health": meta,
        "signal_counts": {
            "fetched": len(signals),
            "new": len(reader_signals),
            "repeated": len(signals) - len(reader_signals),
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if raw_response:
        raw_response_path.write_text(raw_response, encoding="utf-8")
    html_ok = False
    if with_html or with_png:
        write_html(markdown, html_path, run_date)
        html_ok = True
    png_ok = render_png(html_path, png_path) if with_png and html_ok else False
    raw_path = write_snapshot(signals, meta, run_date)
    return {
        "markdown": str(md_path),
        "html": str(html_path) if html_ok else "",
        "png": str(png_path) if png_ok else "",
        "raw": str(raw_path),
        "selection": str(selection_path),
        "products": len(choices),
        "signals": len(signals),
        "reader_signals": len(reader_signals),
        "repeated_signals": len(signals) - len(reader_signals),
        "meta": meta,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Product Radar from Product Hunt, TrustMRR, and Hacker News.")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--html", action="store_true", help="Also render an intermediate HTML artifact.")
    parser.add_argument("--png", action="store_true", help="Also render an intermediate PNG artifact.")
    args = parser.parse_args(argv)

    result = build_product_radar(args.date, with_html=args.html, with_png=args.png)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
