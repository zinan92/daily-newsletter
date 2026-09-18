#!/usr/bin/env python3
"""Term radar: new proper nouns that several independent sources mention on one day.

"Everyone is talking about Jev" is a cross-source frequency fact, not an
editorial judgment, so this stage is deterministic: pull Latin proper nouns
(CamelCase, Capitalized, short ALLCAPS, quoted names, product domains) out of
everything fetched on a day — tracked sources, the X home timeline, X saved
items, GitHub Trending, Product Radar signals — count how many *distinct*
sources mention each, and flag terms that ≥3 sources mention while the term is
still new (first seen ≤ 14 days ago in term-memory.json).

Outputs: _source management/term-candidates/<date>.md (+ memory update with
--write) and a Markdown section for the daily bundle.

Run: python3 term_radar.py --date 2026-09-17 [--write]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import RAW_DIR, SOURCE_MANAGEMENT_DIR, load_sources, today  # noqa: E402

MEMORY_PATH = SOURCE_MANAGEMENT_DIR / "term-memory.json"
CANDIDATES_DIR = SOURCE_MANAGEMENT_DIR / "term-candidates"
X_SAVED_PATH = ROOT / "x-saved-items.json"

MIN_SOURCES = 3
NEW_WITHIN_DAYS = 14
MEMORY_KEEP_DAYS = 90

# Terms that are proper nouns but not news: the platforms and companies every
# day's feed mentions. Lowercased for matching.
KNOWN_TERMS = {
    "openai", "anthropic", "claude", "chatgpt", "gpt", "codex", "google", "gemini", "deepmind", "microsoft",
    "copilot", "apple", "iphone", "mac", "macos", "ios", "android", "meta", "llama", "nvidia", "amazon", "aws",
    "tesla", "spacex", "x", "twitter", "youtube", "tiktok", "instagram", "facebook", "linkedin", "reddit",
    "github", "hacker news", "product hunt", "producthunt", "deepseek", "qwen", "kimi", "moonshot", "doubao",
    "bytedance", "alibaba", "tencent", "baidu", "huawei", "xiaomi", "mistral", "cursor", "vercel", "cloudflare",
    "notion", "figma", "slack", "discord", "telegram", "wechat", "obsidian", "python", "rust", "javascript",
    "typescript", "react", "node", "linux", "windows", "chrome", "safari", "docker", "kubernetes", "sql",
    "ai", "agi", "llm", "llms", "api", "apis", "sdk", "cli", "gpu", "gpus", "cpu", "ram", "url", "http", "https",
    "json", "html", "css", "pdf", "rss", "mcp", "rag", "ui", "ux", "seo", "ceo", "cto", "cfo", "vc", "yc", "ipo",
    "usa", "us", "uk", "eu", "china", "japan", "korea", "india", "europe", "america", "california", "beijing",
    "shanghai", "hong kong", "singapore", "new york", "san francisco", "london", "tokyo",
    "bitcoin", "btc", "eth", "ethereum", "solana", "usdc", "usdt", "sol", "nft", "defi", "web3", "crypto",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october", "november", "december",
    "sam altman", "altman", "dario", "amodei", "musk", "elon", "zuckerberg", "jensen", "huang", "karpathy",
    "claude code", "gpt-4", "gpt-5", "gpt-6", "o3", "o4", "sonnet", "opus", "haiku", "fable", "mythos", "astra",
    "ok", "okay", "thanks", "hello", "hi", "yes", "no", "lol", "omg", "wtf", "tbh", "imo", "fyi", "aka", "ps",
    "pro", "max", "plus", "ultra", "mini", "flash", "turbo", "beta", "alpha", "preview", "app", "apps", "web",
    "rt", "dm", "pm", "am", "id", "tv", "vs", "st", "nd", "rd", "th", "mrr", "arr", "saas", "b2b", "b2c",
    # Feed furniture: list prefixes, template company names, metadata field labels.
    "hn", "show hn", "ask hn", "launch hn", "tell hn", "revenue", "duration", "draft", "hey", "postgres",
    "stealth company", "stealth venture", "stealth startup", "anonymous startup", "hidden business", "stealth",
    "artificial intelligence", "machine learning", "deep learning", "neural", "open source", "opensource",
    "startup", "startups", "company", "inc", "llc", "ltd", "corp", "labs", "lab", "studio", "team", "founder",
    "engineering", "research", "science", "blog", "podcast", "newsletter", "episode", "season", "interview",
    "transcript", "summary", "title", "author", "source", "content", "text", "note", "notes", "quote",
    "grok", "xai", "perplexity", "midjourney", "runway", "sora", "veo", "kling", "hailuo", "suno", "elevenlabs",
    "afaict", "afaik", "iirc", "imho", "tl;dr", "tldr", "ip", "learn", "learning", "edit", "update", "thread",
    "usd", "cny", "rmb", "eur", "jpy", "hkd", "q1", "q2", "q3", "q4", "h1", "h2", "fy", "yoy", "qoq", "mom",
    # Established products that show up every week; not "new terms".
    "shopify", "stripe", "markdown", "openrouter", "cognition", "devin", "vibe coding", "vibecoding", "replit",
    "lovable", "bolt", "windsurf", "cline", "aider", "ollama", "langchain", "llamaindex", "huggingface",
    "hugging face", "openclaw", "hermes", "n8n", "zapier", "make", "airtable", "supabase", "firebase", "postgres",
    "duckdb", "sqlite", "redis", "kafka", "spark", "pytorch", "tensorflow", "jax", "cuda", "arm", "intel", "amd",
    "qualcomm", "samsung", "sony", "netflix", "disney", "uber", "airbnb", "stripe", "paypal", "visa",
}

# Hosting domains are not products.
GENERIC_DOMAIN_SUFFIXES = ("github.io", "vercel.app", "pages.dev", "netlify.app", "notion.site", "substack.com")
# Radar sources whose cards share boilerplate; count each as ONE source so a
# template phrase cannot look like ten independent mentions.
RADAR_SINGLE_SOURCE = {"TrustMRR", "Product Hunt"}

# Capitalized English words that start sentences or are just common; kept short
# because the lowercase-corpus check below catches most of the rest.
STOPWORDS = {
    "the", "this", "that", "these", "those", "there", "here", "then", "than", "they", "them", "their", "what",
    "when", "where", "which", "while", "who", "whom", "whose", "why", "how", "with", "without", "from", "into",
    "onto", "over", "under", "after", "before", "about", "above", "below", "between", "because", "but", "and",
    "for", "nor", "not", "yet", "so", "if", "else", "once", "only", "just", "also", "very", "more", "most", "some",
    "any", "all", "each", "every", "both", "few", "many", "much", "such", "own", "same", "other", "another",
    "new", "old", "first", "last", "next", "now", "today", "tomorrow", "yesterday", "tonight", "week", "month",
    "year", "day", "time", "people", "thing", "things", "one", "two", "three", "four", "five", "ten", "hundred",
    "thousand", "million", "billion", "i", "you", "he", "she", "it", "we", "me", "my", "your", "our", "his",
    "her", "its", "mine", "yours", "let", "get", "got", "make", "made", "take", "took", "give", "gave", "go",
    "went", "come", "came", "see", "saw", "look", "know", "think", "thought", "want", "need", "use", "used",
    "using", "try", "tried", "work", "works", "working", "read", "write", "writing", "build", "built", "building",
    "run", "running", "start", "started", "stop", "stopped", "open", "close", "free", "real", "big", "small",
    "good", "bad", "best", "better", "great", "nice", "cool", "wow", "please", "thank", "sorry", "welcome",
    "check", "note", "update", "updated", "breaking", "live", "watch", "video", "link", "thread", "post",
    "reply", "quote", "share", "follow", "like", "love", "hate", "wait", "still", "already", "never", "always",
    "sometimes", "maybe", "really", "actually", "finally", "probably", "everyone", "everything", "nothing",
    "someone", "something", "anyone", "anything", "nobody", "none", "yes", "no", "ok", "okay", "true", "false",
    "story", "news", "report", "reports", "reported", "says", "said", "say", "announce", "announced",
    "introducing", "launch", "launched", "launching", "release", "released", "available", "coming", "soon",
    "part", "step", "steps", "tip", "tips", "guide", "list", "top", "why", "what", "here's", "there's",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    # Unigrams left over from list prefixes and generic nouns ("Show HN", "Ask HN", "System One").
    "show", "ask", "tell", "hacker", "word", "words", "bring", "since", "system", "systems", "desktop", "design",
    "self", "active", "store", "must", "pace", "model", "models", "agent", "agents", "tool", "tools", "code",
    "data", "cloud", "search", "chat", "voice", "vision", "image", "images", "audio", "music", "game", "games",
    "home", "office", "work", "life", "world", "future", "past", "history", "science", "math", "art", "book",
    "books", "paper", "papers", "course", "class", "school", "student", "students", "teacher", "doctor", "law",
    "money", "price", "prices", "cost", "costs", "market", "markets", "stock", "stocks", "trade", "trading",
    "team", "teams", "user", "users", "human", "humans", "machine", "machines", "robot", "robots", "car", "cars",
    "phone", "phones", "computer", "computers", "internet", "email", "mail", "web", "site", "sites", "page",
    "pages", "file", "files", "text", "texts", "image", "photo", "photos", "camera", "screen", "window",
    "english", "chinese", "japanese", "korean", "french", "german", "spanish",
}

CAMEL_RE = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
CAP_RE = re.compile(r"\b[A-Z][a-z]{2,19}\b")
BIGRAM_RE = re.compile(r"\b([A-Z][a-z]{2,19}\s[A-Z][a-z]{2,19})\b")
CAPS_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,7}\b")
DOMAIN_RE = re.compile(r"\b[a-z0-9][a-z0-9-]{1,30}\.(?:ai|dev|app|io|so|xyz|sh)\b", re.I)
QUOTED_RE = re.compile(r"[「“\"']([A-Za-z][A-Za-z0-9 .\-]{1,24})[」”\"']")
STRIP_RE = re.compile(r"https?://\S+|[@#$]\w+|&\w+;")


def _clean(text: str) -> str:
    return STRIP_RE.sub(" ", str(text or ""))


def extract_terms(text: str) -> set[str]:
    """Proper-noun candidates in one text, in their surface form."""
    cleaned = _clean(text)
    found: set[str] = set()
    for match in CAMEL_RE.findall(cleaned):
        found.add(match)
    for match in CAPS_RE.findall(cleaned):
        found.add(match)
    # Unigrams and bigrams are matched separately: a consuming bigram match
    # ("After Jev") must not hide the name inside it.
    for match in CAP_RE.findall(cleaned):
        found.add(match)
    for match in BIGRAM_RE.findall(cleaned):
        found.add(match)
    for match in DOMAIN_RE.findall(cleaned):
        domain = match.lower()
        if not domain.endswith(GENERIC_DOMAIN_SUFFIXES):
            found.add(domain)
    for match in QUOTED_RE.findall(cleaned):
        term = match.strip()
        if len(term) >= 2 and not term.isdigit():
            found.add(term)
    return found


def lowercase_words(text: str) -> set[str]:
    """Standalone lowercase words in this text: a Capitalized token that also
    occurs lowercase as a plain word is a common word at a sentence start, not
    a name. Slugs, paths and domains (hypit-ai/hypit, hypit.ai) do not count,
    or every repo name would demote its own product."""
    return set(re.findall(r"(?<![\w/.\-])[a-z]{3,20}(?![\w/.\-])", _clean(text)))


def known_terms(extra: Iterable[str] = ()) -> set[str]:
    known = set(KNOWN_TERMS)
    for src in load_sources():
        for key in ("name", "profile_id", "profile_name"):
            value = str(src.get(key) or "").strip().lower()
            if value:
                known.add(value)
        handle = str(src.get("url") or "").rstrip("/").rsplit("/", 1)[-1].lower()
        if handle:
            known.add(handle)
    known.update(str(t).lower() for t in extra)
    return known


def iter_documents(date: str, raw_dir: Path | None = None, x_saved_path: Path | None = None) -> Iterable[tuple[str, str, str]]:
    """Yield (source_key, text, url) for everything fetched on `date`.

    source_key is what makes mentions independent: the tweeting handle for
    timeline/saved lanes, the profile for tracked sources, the post for
    Product Radar signals.
    """
    root = (raw_dir or RAW_DIR) / date
    if root.exists():
        for path in sorted(root.rglob("*.json")):
            if path.name.endswith(".to-md.json"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if path.name == "product-radar.json":
                for sig in (data or {}).get("signals", []) if isinstance(data, dict) else []:
                    text = " ".join(str(sig.get(k) or "") for k in ("title", "summary"))
                    radar_source = str(sig.get("source") or "radar")
                    key = f"radar:{radar_source}" if radar_source in RADAR_SINGLE_SOURCE else f"radar:{radar_source}:{sig.get('url')}"
                    yield key, text, str(sig.get("url") or "")
                continue
            if not isinstance(data, dict):
                continue
            profile = path.parent.name
            if profile in {"x-home", "x-saved"}:
                source = f"x:{str(data.get('handle') or data.get('author') or profile).lower()}"
            else:
                source = f"profile:{profile}"
            text = " ".join(
                str(data.get(k) or "") for k in ("title", "text", "content", "summary", "articleTitle", "articleText")
            )
            yield source, text, str(data.get("url") or "")
    saved = x_saved_path or X_SAVED_PATH
    if saved.exists():
        try:
            payload = json.loads(saved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        rows = payload.values() if isinstance(payload, dict) else payload
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            stamp = str(row.get("tweet_created_date") or row.get("first_seen_at") or "")[:10]
            if stamp != date:
                continue
            handle = str(row.get("handle") or row.get("author") or "saved").lower()
            text = " ".join(str(row.get(k) or "") for k in ("text", "articleTitle", "articleText"))
            yield f"x:{handle}", text, str(row.get("url") or "")


def count_mentions(documents: Iterable[tuple[str, str, str]], known: set[str]) -> dict[str, dict[str, Any]]:
    """term (lowercase key) → {surface counts, sources, urls} after stop/known/lowercase checks."""
    lowercase_seen: set[str] = set()
    per_term: dict[str, dict[str, Any]] = defaultdict(lambda: {"forms": defaultdict(int), "sources": set(), "urls": []})
    docs = list(documents)
    for _, text, _ in docs:
        lowercase_seen |= lowercase_words(text)
    for source, text, url in docs:
        for term in extract_terms(text):
            key = term.lower()
            if key in known or key in STOPWORDS:
                continue
            if " " in key and any(part in STOPWORDS or part in known for part in key.split()):
                continue
            if key in lowercase_seen and not term.isupper():
                continue
            if len(key) < 2 or key.isdigit():
                continue
            entry = per_term[key]
            entry["forms"][term] += 1
            entry["sources"].add(source)
            if url and url not in entry["urls"]:
                entry["urls"].append(url)
    return per_term


def load_memory(path: Path | None = None) -> dict[str, Any]:
    path = path or MEMORY_PATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_memory(memory: dict[str, Any], path: Path | None = None) -> None:
    path = path or MEMORY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def _days_between(a: str, b: str) -> int:
    return (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days


def build_candidates(
    date: str,
    mentions: dict[str, dict[str, Any]],
    memory: dict[str, Any],
    *,
    min_sources: int = MIN_SOURCES,
    new_within_days: int = NEW_WITHIN_DAYS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply the ≥N sources + still-new rule; return (candidates, updated memory)."""
    updated = dict(memory)
    candidates: list[dict[str, Any]] = []
    for key, entry in mentions.items():
        n_sources = len(entry["sources"])
        record = dict(updated.get(key) or {})
        first_seen = record.get("first_seen") or date
        if first_seen > date:
            first_seen = date
        days = dict(record.get("days") or {})
        days[date] = max(int(days.get(date, 0) or 0), n_sources)
        record.update({"first_seen": first_seen, "days": days})
        surface = max(entry["forms"].items(), key=lambda kv: (kv[1], kv[0]))[0]
        record["surface"] = surface
        if n_sources >= min_sources and _days_between(first_seen, date) <= new_within_days:
            flagged = list(record.get("candidate_dates") or [])
            if date not in flagged:
                flagged.append(date)
            record["candidate_dates"] = flagged
            candidates.append(
                {
                    "term": surface,
                    "key": key,
                    "sources": n_sources,
                    "first_seen": first_seen,
                    "days_seen": len(days),
                    "urls": entry["urls"][:3],
                    "source_kinds": sorted({s.split(":", 1)[0] for s in entry["sources"]}),
                }
            )
        updated[key] = record
    candidates.sort(key=lambda c: (-c["sources"], c["first_seen"], c["term"].lower()))
    # Keep memory bounded: drop terms unseen for MEMORY_KEEP_DAYS.
    cutoff = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=MEMORY_KEEP_DAYS)).strftime("%Y-%m-%d")
    updated = {k: v for k, v in updated.items() if max((v.get("days") or {date: 0}).keys()) >= cutoff}
    return candidates, updated


def render_markdown(date: str, candidates: list[dict[str, Any]]) -> str:
    lines = [f"## 新名词雷达 · {date}", ""]
    if not candidates:
        lines.append("今天没有跨 3 个来源以上的新名词。")
        return "\n".join(lines) + "\n"
    lines.append(f"跨来源 ≥{MIN_SOURCES} 且首见 ≤{NEW_WITHIN_DAYS} 天的名词，按来源数排序：")
    lines.append("")
    for c in candidates:
        age = "今天首见" if c["first_seen"] == date else f"首见 {c['first_seen']}"
        links = " ".join(f"[{i + 1}]({u})" for i, u in enumerate(c["urls"]))
        lines.append(f"- **{c['term']}** · {c['sources']} 个来源 · {age} · {links}")
    return "\n".join(lines) + "\n"


def run(date: str, *, write: bool = False, raw_dir: Path | None = None, memory_path: Path | None = None,
        candidates_dir: Path | None = None, x_saved_path: Path | None = None) -> tuple[list[dict[str, Any]], str]:
    known = known_terms()
    mentions = count_mentions(iter_documents(date, raw_dir, x_saved_path), known)
    memory = load_memory(memory_path)
    candidates, updated = build_candidates(date, mentions, memory)
    markdown = render_markdown(date, candidates)
    if write:
        save_memory(updated, memory_path)
        out_dir = candidates_dir or CANDIDATES_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{date}.md").write_text(markdown, encoding="utf-8")
        (out_dir / f"{date}.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=1), encoding="utf-8")
    return candidates, markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-source new-term candidates for one day.")
    parser.add_argument("--date", default=today())
    parser.add_argument("--write", action="store_true", help="Update term-memory.json and write term-candidates/<date>.md")
    args = parser.parse_args(argv)
    _, markdown = run(args.date, write=args.write)
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
