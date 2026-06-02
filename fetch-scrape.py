#!/usr/bin/env python3
"""
fetch-scrape.py — Scrapes HTML index pages for sources without RSS.
Currently handles Anthropic Engineering and Claude Blog.
Logic ported from follow-builders generate-feed.js (regex + Next.js __NEXT_DATA__).
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape

from lib import (
    PROFILE_LIBRARY_DIR,
    load_sources,
    load_state,
    save_state,
    write_source_output,
    log,
    today,
    now_utc,
    profile_id_for_source,
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MAX_ARTICLES_PER_SOURCE = 5
ARTICLE_DELAY_SEC = 0.5
CLAUDE_SITEMAP = "https://claude.com/sitemap.xml"
CLAUDE_BLOG_MAX_AGE_DAYS = 21   # only ingest blog posts published within this window
CLAUDE_FETCH_BUDGET = 80        # max article fetches/run — bounds the one-time sitemap catch-up


def fetch_url(url, timeout=30, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as ex:
            last_error = ex
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def extract_next_data(html):
    """Pull JSON from <script id='__NEXT_DATA__'> block. Returns dict or None."""
    m = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>([\s\S]*?)</script>',
        html,
        re.IGNORECASE,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def parse_anthropic_section(html, index_url):
    """Generic Anthropic Next.js parser — works for /news, /engineering, /research.
    Strategy 1: __NEXT_DATA__ JSON. Strategy 2: regex on hrefs matching the section path.
    """
    import urllib.parse as _up
    section_path = _up.urlparse(index_url).path.rstrip("/")  # e.g. '/news' or '/engineering'
    base = f"{_up.urlparse(index_url).scheme}://{_up.urlparse(index_url).netloc}"

    articles = []
    data = extract_next_data(html)
    if data:
        page_props = (data.get("props") or {}).get("pageProps") or {}
        posts = (
            page_props.get("posts")
            or page_props.get("articles")
            or page_props.get("entries")
            or []
        )
        for p in posts:
            slug_field = p.get("slug")
            slug = slug_field.get("current") if isinstance(slug_field, dict) else (slug_field or "")
            if not slug:
                continue
            articles.append(
                {
                    "title": p.get("title", "Untitled"),
                    "url": f"{base}{section_path}/{slug}",
                    "published": p.get("publishedOn") or p.get("publishedAt") or p.get("date"),
                    "summary": p.get("summary") or p.get("description") or "",
                }
            )
        if articles:
            return articles

    # Fallback: regex for <section>/<slug> hrefs
    pattern = r'href="' + re.escape(section_path) + r'/([a-z0-9-]+)"'
    seen = set()
    for m in re.finditer(pattern, html, re.IGNORECASE):
        slug = m.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        articles.append(
            {
                "title": "",
                "url": f"{base}{section_path}/{slug}",
                "published": None,
                "summary": "",
            }
        )
    return articles


def parse_claude_blog(html):
    """claude.com/blog — Webflow site, parse cards with title/date/url."""
    articles = []
    seen = set()
    for idx, block in enumerate(re.split(r'<div role="listitem" class="blog_cms_item w-dyn-item">', html)):
        if idx == 0:
            continue
        url_match = re.search(r'href="/blog/([a-z0-9-]+)"', block, re.IGNORECASE)
        if not url_match:
            continue
        slug = url_match.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        title = ""
        title_match = re.search(r'fs-list-field="heading"[^>]*>(.*?)</', block, re.IGNORECASE | re.S)
        if title_match:
            title = _strip_to_text(title_match.group(1), limit=300)
        if not title:
            cta_match = re.search(r'data-cta-copy="([^"]+)"', block, re.IGNORECASE)
            if cta_match:
                title = unescape(cta_match.group(1))
        date = ""
        date_match = re.search(
            r'fs-list-fieldtype="date"\s+fs-list-field="date"[^>]*>([^<]+)</',
            block,
            re.IGNORECASE,
        )
        if date_match:
            date = parse_display_date(date_match.group(1).strip())
        category = ""
        category_match = re.search(r'fs-list-field="category"[^>]*>([^<]+)</', block, re.IGNORECASE)
        if category_match:
            category = unescape(category_match.group(1).strip())
        articles.append(
            {
                "title": unescape(title),
                "url": f"https://claude.com/blog/{slug}",
                "published": date,
                "summary": category,
            }
        )
    return articles


def parse_display_date(text: str) -> str:
    if not text:
        return ""
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def claude_blog_page_count(html: str) -> int:
    match = re.search(r'aria-label="Page\s+\d+\s+of\s+(\d+)"', html)
    if match:
        return int(match.group(1))
    return 1


def fetch_all_claude_blog_candidates(index_url: str) -> list:
    first = fetch_url(index_url)
    pages = claude_blog_page_count(first)
    all_articles = []
    seen = set()
    for page in range(1, pages + 1):
        html = first if page == 1 else fetch_url(f"{index_url}?b7eea976_page={page}")
        for article in parse_claude_blog(html):
            if article["url"] in seen:
                continue
            seen.add(article["url"])
            all_articles.append(article)
    return all_articles


def claude_blog_sitemap_urls(xml: str | None = None) -> list[str]:
    """All /blog/<slug> article URLs from claude.com sitemap.

    The Webflow index pagination silently drops recent posts (that's how the
    May-27/28 articles were missed); the sitemap lists every article, so we use
    it as the authoritative candidate set. Pass `xml` to unit-test the parser.
    """
    if xml is None:
        try:
            xml = fetch_url(CLAUDE_SITEMAP)
        except Exception:
            return []
    out, seen = [], set()
    for u in re.findall(r"<loc>\s*(https://claude\.com/blog/[a-z0-9-]+)\s*</loc>", xml, re.IGNORECASE):
        slug = u.rstrip("/").rsplit("/", 1)[-1]
        if slug in ("blog", "category") or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def parse_iso_date(raw: str) -> str:
    """Best-effort → 'YYYY-MM-DD' (handles ISO 8601 and 'May 28, 2026')."""
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.strip().replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return parse_display_date(raw.strip())


def article_age_days(published: str) -> int | None:
    """Days since `published` (any supported format); None if unparseable."""
    d = parse_iso_date(published)
    if not d:
        return None
    try:
        return (datetime.now(timezone.utc).date() - datetime.strptime(d, "%Y-%m-%d").date()).days
    except ValueError:
        return None


def _strip_to_text(html, limit=5000):
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(re.sub(r"\s+", " ", text).strip())
    return text[:limit]


def clean_claude_blog_text(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    copy_link = re.search(r"Share Copy link https://claude\.com/blog/[a-z0-9-]+", text)
    if copy_link:
        text = text[copy_link.end():].strip()
    # Drop related-post and footer material that follows the actual article body.
    for marker in (
        "Related posts Explore more",
        "Prev Prev",
        "Get started with Claude today",
        "No items found. Related posts",
    ):
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx].strip()
    return text


def extract_anthropic_article(html):
    """Try Next.js JSON first; fallback to title regex + text strip."""
    data = extract_next_data(html)
    if data:
        page_props = (data.get("props") or {}).get("pageProps") or {}
        post = (
            page_props.get("post")
            or page_props.get("article")
            or page_props.get("entry")
            or page_props
        )
        if isinstance(post, dict):
            title = post.get("title", "")
            published = post.get("publishedOn") or post.get("publishedAt") or post.get("date")
            author = ""
            a = post.get("author")
            if isinstance(a, dict):
                author = a.get("name", "")
            elif isinstance(post.get("authors"), list) and post["authors"]:
                first = post["authors"][0]
                if isinstance(first, dict):
                    author = first.get("name", "")
            # Sanity portable text body
            body = post.get("body") or post.get("content") or []
            content = ""
            if isinstance(body, list):
                parts = []
                for block in body:
                    if isinstance(block, dict) and block.get("_type") == "block":
                        children = block.get("children", [])
                        text = "".join(c.get("text", "") for c in children if isinstance(c, dict))
                        if text.strip():
                            parts.append(text.strip())
                content = "\n\n".join(parts)
            if title or content:
                return {
                    "title": title,
                    "author": author,
                    "published": published,
                    "content": content[:5000] if content else _strip_to_text(html),
                }

    # Fallback: <title> tag + stripped body
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    title = unescape(m.group(1).strip()) if m else ""
    return {
        "title": title,
        "author": "",
        "published": None,
        "content": _strip_to_text(html),
    }


def extract_claude_blog_article(html):
    """claude.com/blog/<slug> — OG meta + text strip."""
    title = ""
    m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
    if m:
        title = unescape(m.group(1))
    if not title:
        m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if m:
            title = unescape(m.group(1).strip())
    title = re.sub(r"\s*\|\s*Claude\s*$", "", title).strip()

    summary = ""
    m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html)
    if m:
        summary = unescape(m.group(1))

    published = ""
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
    if m:
        published = parse_iso_date(m.group(1))

    return {
        "title": title,
        "author": "",
        "published": published or None,
        "content": clean_claude_blog_text(_strip_to_text(html, limit=12000))[:7000],
        "summary": summary,
        "pdfs": extract_pdf_links(html, "https://claude.com"),
    }


def extract_pdf_links(html: str, base_url: str) -> list[str]:
    links = []
    for match in re.finditer(r'href="([^"]+\.pdf[^"]*)"', html, re.IGNORECASE):
        url = urllib.parse.urljoin(base_url, unescape(match.group(1)))
        if url not in links:
            links.append(url)
    return links


def safe_name(text: str, fallback: str = "untitled") -> str:
    text = unescape(text or "").strip().lower()
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = text.strip("-")
    return text[:90] or fallback


def save_library_article(source: dict, item: dict, article_html: str = "") -> None:
    source_name = source["name"]
    source_dir = PROFILE_LIBRARY_DIR / profile_id_for_source(source) / "items"
    slug = safe_name(item.get("url", "").rstrip("/").rsplit("/", 1)[-1], safe_name(item.get("title", "")))
    item_dir = source_dir / slug
    assets_dir = item_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    pdf_paths = []
    for pdf_url in item.get("pdfs", []) or extract_pdf_links(article_html, item.get("url", "")):
        try:
            raw_pdf_name = urllib.parse.unquote(pdf_url.rsplit("/", 1)[-1].split("?", 1)[0])
            raw_pdf_name = re.sub(r"\.pdf$", "", raw_pdf_name, flags=re.IGNORECASE)
            pdf_name = safe_name(raw_pdf_name, "document") + ".pdf"
            pdf_path = assets_dir / pdf_name
            if not pdf_path.exists():
                data = urllib.request.urlopen(
                    urllib.request.Request(pdf_url, headers={"User-Agent": USER_AGENT}),
                    timeout=60,
                ).read()
                pdf_path.write_bytes(data)
            pdf_paths.append(pdf_path.relative_to(item_dir))
        except Exception as ex:
            log("fetch-scrape", f"    pdf download failed for {pdf_url}: {ex}")

    md_lines = [
        "---",
        f"title: {item.get('title', '')}",
        f"url: {item.get('url', '')}",
        f"source: {source_name}",
        f"published: {item.get('published') or ''}",
        f"saved_at: {now_utc()}",
        "---",
        "",
        f"# {item.get('title') or slug}",
        "",
        f"- Source: {item.get('url', '')}",
    ]
    if item.get("published"):
        md_lines.append(f"- Published: {item.get('published')}")
    if item.get("summary"):
        md_lines.append(f"- Summary: {item.get('summary')}")
    for rel in pdf_paths:
        md_lines.append(f"- PDF: [{rel.name}]({rel.as_posix()})")
    md_lines.extend(["", "## Content", "", item.get("content", "").strip()])
    (item_dir / "article.md").write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")
    if article_html:
        (item_dir / "raw.html").write_text(article_html, encoding="utf-8")


def main():
    state = load_state()
    sources = [s for s in load_sources() if s["platform"] == "scrape"]
    log("fetch-scrape", f"START — {len(sources)} sources")

    for src in sources:
        key = f"scrape:{src['name']}"
        try:
            log("fetch-scrape", f"  {src['name']}: fetching index {src['url']}")
            html = fetch_url(src["url"])

            if "anthropic.com" in src["url"]:
                candidates = parse_anthropic_section(html, src["url"])
                article_extractor = extract_anthropic_article
            elif "claude.com" in src["url"]:
                candidates = fetch_all_claude_blog_candidates(src["url"])
                known = {c["url"] for c in candidates}
                # sitemap = authoritative complete set; index alone drops recent posts
                candidates += [{"url": u} for u in claude_blog_sitemap_urls() if u not in known]
                article_extractor = extract_claude_blog_article
            else:
                log("fetch-scrape", f"  {src['name']}: NO PARSER CONFIGURED")
                continue

            log("fetch-scrape", f"  {src['name']}: {len(candidates)} candidate articles")

            seen_urls = state.get(key, {}).get("seen_urls", {})
            new_articles = []
            is_claude = "claude.com" in src["url"]
            max_new = len(candidates) if os.environ.get("PARKIO_SCRAPE_BACKFILL") == "1" else MAX_ARTICLES_PER_SOURCE
            fetches = 0
            for c in candidates:
                if len(new_articles) >= max_new:
                    break
                if is_claude and fetches >= CLAUDE_FETCH_BUDGET:
                    break
                if c["url"] in seen_urls:
                    continue
                try:
                    article_html = fetch_url(c["url"])
                    fetches += 1
                    time.sleep(ARTICLE_DELAY_SEC)
                    extracted = article_extractor(article_html)
                    # Age gate: ingest only recent posts; mark older backlog seen so the
                    # one-time sitemap catch-up is absorbed once (not re-fetched or flooded).
                    if is_claude:
                        age = article_age_days(extracted.get("published") or c.get("published") or "")
                        if age is None or age > CLAUDE_BLOG_MAX_AGE_DAYS:
                            seen_urls[c["url"]] = now_utc()
                            continue
                    if not extracted.get("content"):
                        log("fetch-scrape", f"    no content for {c['url']}")
                        continue
                    new_articles.append(
                        {
                            "title": extracted.get("title") or c.get("title") or "Untitled",
                            "url": c["url"],
                            "published": extracted.get("published") or c.get("published"),
                            "author": extracted.get("author", ""),
                            "summary": extracted.get("summary", "") or c.get("summary", ""),
                            "content": extracted.get("content", ""),
                            "pdfs": extracted.get("pdfs", []),
                        }
                        | ({"library": "true"} if "claude.com" in src["url"] else {})
                    )
                    if "claude.com" in src["url"]:
                        save_library_article(src, new_articles[-1], article_html)
                    seen_urls[c["url"]] = now_utc()
                except Exception as ex:
                    log("fetch-scrape", f"    article fetch failed for {c['url']}: {ex}")

            log("fetch-scrape", f"  {src['name']}: {len(new_articles)} NEW articles")
            if new_articles:
                write_source_output(src, new_articles)
            state[key] = {"seen_urls": seen_urls, "last_fetch": today()}
        except Exception as ex:
            state[key] = {**state.get(key, {}), "last_fetch": today(), "status": "failed", "error": f"{type(ex).__name__}: {ex}"}
            log("fetch-scrape", f"  {src['name']}: ERROR {type(ex).__name__}: {ex}")

    save_state(state)
    log("fetch-scrape", "DONE")


if __name__ == "__main__":
    main()
