#!/usr/bin/env python3
"""Fetch seeded WeChat public-account articles.

WeChat does not expose a stable unauthenticated RSS feed for a public account.
For now each `platform=wechat` row uses its URL as a seed article. New links can
be added as rows, and the same account identity is preserved in source health.
"""
import os
import re
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from html import unescape

from lib import PROFILE_LIBRARY_DIR, load_sources, load_state, profile_id_for_source, safe_filename, save_state, write_source_output, log, today

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
IMPORT_SEEDS = os.environ.get("PARKIO_WECHAT_IMPORT_SEEDS") == "1"


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
        return "\n".join(line for line in lines if line)[:8000]


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.S)
        if m:
            return unescape(m.group(1)).strip()
    return ""


def article_date(html: str) -> str:
    ct = first_match(
        html,
        [
            r'var ct = "(\d+)";',
            r"createTimestamp = '(\d+)'",
        ],
    )
    if not ct:
        return ""
    try:
        return datetime.fromtimestamp(int(ct)).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def clean_text(html_fragment: str) -> str:
    parser = TextExtractor()
    parser.feed(html_fragment or "")
    return parser.text()


def parse_article(url: str, html: str) -> dict:
    content = first_match(
        html,
        [
            r'<div[^>]+id=["\']js_content["\'][^>]*>(.*?)</div>\s*<script',
            r'<div[^>]+id=["\']js_content["\'][^>]*>(.*?)</div>',
        ],
    )
    title = first_match(
        html,
        [
            r'<meta property="og:title" content="(.*?)"',
            r'var msg_title = "(.*?)";',
        ],
    )
    account = first_match(
        html,
        [
            r'var nickname = htmlDecode\("(.*?)"\);',
            r"nick_name: '([^']+)'",
            r'<meta name="author" content="(.*?)"',
        ],
    )
    author = first_match(html, [r'<meta name="author" content="(.*?)"'])
    user_name = first_match(
        html,
        [
            r'var user_name = "(.*?)";',
            r"user_name: '([^']+)'",
        ],
    )
    desc = first_match(html, [r'<meta name="description" content="(.*?)"'])
    content = clean_text(content) if content else desc
    published = today() if IMPORT_SEEDS else article_date(html)
    return {
        "title": title or "微信公众号文章",
        "url": url,
        "published": published,
        "content": (content or "").strip(),
        # Provenance kept OUT of `content` so 公众号/作者/WeChat ID can never leak
        # into the consumer newsletter (gotcha #4). For status/metadata only;
        # the display author already comes from the source name downstream.
        "wechat_account": account,
        "wechat_author": author if author and author != account else "",
        "wechat_id": user_name,
    }


def seed_urls(src: dict) -> list[str]:
    urls = [src["url"]]
    notes = src.get("notes", "")
    for url in re.findall(r"https://mp\.weixin\.qq\.com/s/[^\s；;|]+", notes):
        if url not in urls:
            urls.append(url)
    return urls


def save_article_to_library(src: dict, item: dict, html: str) -> str:
    title = safe_filename(item.get("title", "wechat-article"))[:80]
    date = item.get("published", "") or today()
    slug = safe_filename(f"{date}-{title}")[:120]
    out_dir = PROFILE_LIBRARY_DIR / profile_id_for_source(src) / "items" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    article = out_dir / "article.md"
    raw = out_dir / "raw.html"
    article.write_text(
        "\n".join(
            [
                "---",
                f"source: {src['name']}",
                f"url: {item.get('url', '')}",
                f"published: {item.get('published', '')}",
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
    raw.write_text(html, encoding="utf-8")
    return str(article)


def main() -> None:
    state = load_state()
    sources = [s for s in load_sources() if s["platform"] == "wechat"]
    log("fetch-wechat", f"START — {len(sources)} sources")
    for src in sources:
        key = f"wechat:{src['name']}"
        imported: list[dict] = []
        seen = set(state.get(key, {}).get("seen_urls", []))
        library_paths: list[str] = []
        account = ""
        try:
            for url in seed_urls(src):
                html = fetch_url(url)
                item = parse_article(url, html)
                library_paths.append(save_article_to_library(src, item, html))
                should_import = IMPORT_SEEDS or url not in seen
                is_today = item.get("published", "")[:10] == today()
                if should_import and (IMPORT_SEEDS or is_today):
                    imported.append(item)
                seen.add(url)
                if not account:
                    account = first_match(
                        html,
                        [r'var nickname = htmlDecode\("(.*?)"\);', r"nick_name: '([^']+)'"],
                    )
            if imported:
                write_source_output(src, imported)
            log("fetch-wechat", f"  {src['name']}: {len(imported)} NEW")
            state[key] = {
                "last_fetch": today(),
                "seen_urls": sorted(seen),
                "library_path": library_paths[-1] if library_paths else state.get(key, {}).get("library_path", ""),
                "library_paths": library_paths or state.get(key, {}).get("library_paths", []),
                "account": account or state.get(key, {}).get("account", ""),
            }
        except Exception as ex:
            state[key] = {**state.get(key, {}), "last_fetch": today(), "status": "failed", "error": f"{type(ex).__name__}: {ex}"}
            log("fetch-wechat", f"  {src['name']}: ERROR {type(ex).__name__}: {ex}")
    save_state(state)
    log("fetch-wechat", "DONE")


if __name__ == "__main__":
    main()
