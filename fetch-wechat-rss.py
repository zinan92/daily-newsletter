#!/usr/bin/env python3
"""Fetch WeChat public-account articles from RSS/JSON bridge feeds.

This stage is intentionally thin. It does not scrape WeChat directly. It reads
configured `platform=wechat-rss` sources, or `platform=wechat` sources whose
notes contain `rss_url <url>`, and imports newly published feed entries into the
same daily raw queue and profile library used by manual WeChat seed articles.
"""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser

from lib import (
    PROFILE_LIBRARY_DIR,
    load_sources,
    load_state,
    log,
    profile_id_for_source,
    safe_filename,
    save_state,
    today,
    write_source_output,
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
NS = {"atom": "http://www.w3.org/2005/Atom"}


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
    parser.feed(text or "")
    return parser.text()


def fetch_url(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content_type = resp.headers.get("Content-Type", "")
        return resp.read().decode("utf-8", errors="replace"), content_type


def parse_date(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if re.fullmatch(r"\d{10}", raw):
        return datetime.fromtimestamp(int(raw)).strftime("%Y-%m-%d")
    if re.fullmatch(r"\d{13}", raw):
        return datetime.fromtimestamp(int(raw) / 1000).strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        return parsedate_to_datetime(raw).astimezone().strftime("%Y-%m-%d")
    except Exception:
        pass
    m = re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", raw)
    if not m:
        return ""
    parts = re.split(r"[-/]", m.group(0))
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def first_text(parent: ET.Element, names: list[str]) -> str:
    for name in names:
        value = parent.findtext(name)
        if value:
            return value
        value = parent.findtext(f"atom:{name}", "", NS)
        if value:
            return value
    return ""


def parse_xml_feed(text: str) -> list[dict]:
    root = ET.fromstring(text)
    tag = root.tag.lower()
    items: list[dict] = []
    if tag == "rss":
        nodes = root.findall(".//item")
    elif tag.endswith("}feed") or tag == "feed":
        nodes = root.findall("atom:entry", NS) or root.findall("entry")
    else:
        return items
    for node in nodes:
        link_el = node.find("atom:link", NS) or node.find("link")
        link = ""
        if link_el is not None:
            link = link_el.get("href") or link_el.text or ""
        content = first_text(node, ["content", "encoded", "summary", "description"])
        items.append(
            {
                "title": first_text(node, ["title"]).strip() or "微信公众号文章",
                "url": link.strip(),
                "published": parse_date(first_text(node, ["pubDate", "published", "updated"])),
                "content": clean_html(content) if "<" in content else content.strip(),
            }
        )
    return items


def flatten_json(value: object) -> list[dict]:
    out: list[dict] = []
    if isinstance(value, list):
        for item in value:
            out.extend(flatten_json(item))
    elif isinstance(value, dict):
        if any(k in value for k in ("title", "url", "link", "content", "description")):
            out.append(value)
        for key in ("items", "articles", "data", "list", "entries"):
            child = value.get(key)
            if isinstance(child, (list, dict)):
                out.extend(flatten_json(child))
    return out


def parse_json_feed(text: str) -> list[dict]:
    payload = json.loads(text)
    items = []
    for row in flatten_json(payload):
        content = str(
            row.get("content_html")
            or row.get("content")
            or row.get("summary")
            or row.get("description")
            or ""
        ).strip()
        items.append(
            {
                "title": str(row.get("title") or row.get("name") or "微信公众号文章").strip(),
                "url": str(row.get("url") or row.get("link") or row.get("article_url") or "").strip(),
                "published": parse_date(
                    row.get("date_published")
                    or row.get("date_modified")
                    or row.get("published")
                    or row.get("date")
                    or row.get("pubDate")
                    or row.get("create_time")
                ),
                "content": clean_html(content) if "<" in content else content,
            }
        )
    return items


def feed_url_for_source(src: dict) -> str:
    if src.get("platform") == "wechat-rss":
        return src.get("url", "").strip()
    notes = src.get("notes", "")
    match = re.search(r"rss_url\s+(https?://\S+)", notes)
    return match.group(1).strip() if match else ""


def configured_sources() -> list[dict]:
    out = []
    for src in load_sources():
        if src.get("platform") == "wechat-rss" or feed_url_for_source(src):
            out.append(src)
    return out


def save_to_library(src: dict, item: dict) -> str:
    date = item.get("published") or today()
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
    return str(article)


def main() -> None:
    sources = configured_sources()
    state = load_state()
    log("fetch-wechat-rss", f"START — {len(sources)} sources")
    for src in sources:
        feed_url = feed_url_for_source(src)
        key = f"wechat-rss:{src['name']}"
        try:
            text, content_type = fetch_url(feed_url)
            if "json" in content_type or feed_url.endswith(".json"):
                entries = parse_json_feed(text)
            else:
                entries = parse_xml_feed(text)
            seen = set(state.get(key, {}).get("seen_urls", []))
            new_items = []
            library_paths = []
            for item in entries:
                if not item.get("url") and not item.get("title"):
                    continue
                identity = item.get("url") or f"{item.get('published')}:{item.get('title')}"
                if item.get("published"):
                    library_paths.append(save_to_library(src, item))
                if identity in seen:
                    continue
                seen.add(identity)
                if item.get("published", "")[:10] == today():
                    new_items.append(item)
            if new_items:
                write_source_output({**src, "platform": "wechat-rss"}, new_items)
            state[key] = {
                "last_fetch": today(),
                "feed_url": feed_url,
                "seen_urls": sorted(seen),
                "library_paths": library_paths[-20:],
                "status": "ok",
                "entries": len(entries),
                "imported": len(new_items),
            }
            log("fetch-wechat-rss", f"  {src['name']}: {len(new_items)} NEW / {len(entries)} entries")
        except Exception as ex:
            state[key] = {
                **state.get(key, {}),
                "last_fetch": today(),
                "feed_url": feed_url,
                "status": "failed",
                "error": f"{type(ex).__name__}: {ex}",
            }
            log("fetch-wechat-rss", f"  {src['name']}: ERROR {type(ex).__name__}: {ex}")
    save_state(state)
    log("fetch-wechat-rss", "DONE")


if __name__ == "__main__":
    main()
