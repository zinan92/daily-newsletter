#!/usr/bin/env python3
"""Import WeChat articles exported by an external collector.

This is the automation bridge for public-account discovery. The pipeline does
not try to scrape WeChat account timelines directly; instead, any reliable
collector can drop JSON/Markdown/HTML files into PARKIO_WECHAT_EXPORT_DIR, and
this stage imports matched configured accounts into the library and today's raw
inbox.
"""
import json
import os
import re
import sys
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import PARKIO, PROFILE_LIBRARY_DIR, load_sources, load_state, log, profile_id_for_source, safe_filename, save_state, today, write_source_output

EXPORT_DIR = Path(os.environ.get("PARKIO_WECHAT_EXPORT_DIR", PARKIO / "outbox" / "wechat-exporter")).expanduser()
IMPORT_ALL = os.environ.get("PARKIO_WECHAT_EXPORT_IMPORT_ALL") == "1"


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "svg"}:
            self.skip_depth += 1
        if tag in {"p", "div", "section", "br", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "div", "section", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        raw = unescape("".join(self.parts))
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)[:12000]


def clean_html(text: str) -> str:
    parser = TextExtractor()
    parser.feed(text)
    return parser.text()


def normalize_date(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return today()
    if re.fullmatch(r"\d{10}", raw):
        return datetime.fromtimestamp(int(raw)).strftime("%Y-%m-%d")
    if re.fullmatch(r"\d{13}", raw):
        return datetime.fromtimestamp(int(raw) / 1000).strftime("%Y-%m-%d")
    m = re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", raw)
    if not m:
        return today()
    parts = re.split(r"[-/]", m.group(0))
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def flatten_json(value: object) -> Iterable[dict]:
    if isinstance(value, dict):
        article_like = any(k in value for k in ("title", "url", "link", "content", "html", "account", "nickname"))
        if article_like:
            yield value
        for key in ("items", "articles", "data", "list"):
            child = value.get(key)
            if isinstance(child, (list, dict)):
                yield from flatten_json(child)
    elif isinstance(value, list):
        for item in value:
            yield from flatten_json(item)


def item_from_json(data: dict) -> dict:
    title = str(data.get("title") or data.get("name") or data.get("headline") or "微信公众号文章").strip()
    url = str(data.get("url") or data.get("link") or data.get("article_url") or "").strip()
    account = str(data.get("account") or data.get("nickname") or data.get("source") or data.get("author") or "").strip()
    user_name = str(data.get("user_name") or data.get("wechat_id") or data.get("biz") or "").strip()
    published = normalize_date(data.get("published") or data.get("date") or data.get("time") or data.get("create_time"))
    content = str(data.get("content") or data.get("text") or data.get("summary") or "").strip()
    html = str(data.get("html") or data.get("raw_html") or "").strip()
    if html and len(content) < 300:
        content = clean_html(html)
    parts = []
    if account:
        parts.append(f"公众号：{account}")
    if user_name:
        parts.append(f"WeChat ID：{user_name}")
    if content:
        parts.append(content)
    return {
        "title": title,
        "url": url,
        "published": published,
        "content": "\n\n".join(parts),
        "account": account,
        "user_name": user_name,
        "raw": html,
    }


def item_from_file(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        items = list(flatten_json(data))
        return item_from_json(items[0]) if items else None
    title = path.stem
    if path.suffix.lower() in {".html", ".htm"}:
        content = clean_html(text)
        raw = text
    else:
        content = text.strip()
        raw = ""
    return {"title": title, "url": "", "published": today(), "content": content, "account": "", "raw": raw}


def load_export_items() -> list[dict]:
    items: list[dict] = []
    for path in sorted(EXPORT_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".html", ".htm"}:
            continue
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            items.extend(item_from_json(row) for row in flatten_json(data))
        else:
            item = item_from_file(path)
            if item:
                items.append(item)
    return [item for item in items if item.get("title") and (item.get("url") or item.get("content"))]


def match_source(item: dict, sources: list[dict]) -> dict | None:
    account = str(item.get("account") or "").lower()
    user_name = str(item.get("user_name") or "").lower()
    content = f"{item.get('title', '')}\n{item.get('content', '')}".lower()
    for src in sources:
        name = src["name"].lower()
        notes = src.get("notes", "").lower()
        if name and (name in account or name in content):
            return src
        user_name_match = re.search(r"user_name\s+([a-z0-9_]+)", notes)
        if user_name_match:
            configured = user_name_match.group(1)
            if configured == user_name or configured in content:
                return src
    return None


def save_to_library(src: dict, item: dict) -> str:
    date = item.get("published", "") or today()
    title = safe_filename(item.get("title", "wechat-article"))[:80]
    out_dir = PROFILE_LIBRARY_DIR / profile_id_for_source(src) / "items" / safe_filename(f"{date}-{title}")[:120]
    out_dir.mkdir(parents=True, exist_ok=True)
    article = out_dir / "article.md"
    article.write_text(
        "\n".join(
            [
                "---",
                f"source: {src['name']}",
                f"url: {item.get('url', '')}",
                f"published: {date}",
                "---",
                "",
                f"# {item.get('title', '微信公众号文章')}",
                "",
                item.get("content", ""),
                "",
            ]
        ),
        encoding="utf-8",
    )
    raw = str(item.get("raw") or "")
    if raw:
        (out_dir / "raw.html").write_text(raw, encoding="utf-8")
    return str(article)


def main() -> None:
    sources = [s for s in load_sources() if s["platform"] == "wechat"]
    log("fetch-wechat-exporter", f"START — dir={EXPORT_DIR}")
    state = load_state()
    if not EXPORT_DIR.exists():
        state["wechat-exporter"] = {
            "last_fetch": today(),
            "status": "not_configured",
            "export_dir": str(EXPORT_DIR),
            "files": 0,
            "imported": 0,
        }
        save_state(state)
        log("fetch-wechat-exporter", "not configured: export dir does not exist")
        return
    export_files = [
        path
        for path in EXPORT_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in {".json", ".md", ".html", ".htm"}
    ]
    imported_by_source: dict[str, list[dict]] = {}
    for item in load_export_items():
        src = match_source(item, sources)
        if not src:
            continue
        key = f"wechat:{src['name']}"
        seen = set(state.get(key, {}).get("seen_urls", []))
        identity = item.get("url") or f"{src['name']}:{item.get('published')}:{item.get('title')}"
        library_path = save_to_library(src, item)
        state.setdefault(key, {})["last_fetch"] = today()
        state[key]["library_path"] = library_path
        if identity in seen:
            continue
        seen.add(identity)
        state[key]["seen_urls"] = sorted(seen)
        if IMPORT_ALL or item.get("published", "")[:10] == today():
            imported_by_source.setdefault(src["name"], []).append(item)
    for name, items in imported_by_source.items():
        src = next(s for s in sources if s["name"] == name)
        write_source_output(src, items)
        log("fetch-wechat-exporter", f"  {name}: {len(items)} NEW")
    state["wechat-exporter"] = {
        "last_fetch": today(),
        "status": "ok" if export_files else "empty",
        "export_dir": str(EXPORT_DIR),
        "files": len(export_files),
        "imported": sum(len(items) for items in imported_by_source.values()),
    }
    save_state(state)
    log("fetch-wechat-exporter", "DONE")


if __name__ == "__main__":
    main()
