#!/usr/bin/env python3
"""Backfill Claude Blog articles and linked PDFs into Park-IO library."""
import importlib.util
from pathlib import Path

from lib import PROFILE_LIBRARY_DIR, load_state, save_state, now_utc

ROOT = Path(__file__).parent
FETCH_SCRAPE = ROOT / "fetch-scrape.py"
CLAUDE_BLOG_URL = "https://claude.com/blog"
SOURCE_NAME = "Claude Blog"


def load_fetch_scrape():
    spec = importlib.util.spec_from_file_location("fetch_scrape", FETCH_SCRAPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_index(library_dir: Path, rows: list[dict]) -> None:
    lines = [
        "# Claude Blog Library",
        "",
        "Official Claude blog archive captured by input-to-park.",
        "",
        "| Date | Title | Assets |",
        "|---|---|---|",
    ]
    for row in rows:
        slug = row["url"].rstrip("/").rsplit("/", 1)[-1]
        article = f"{slug}/article.md"
        assets = []
        item_dir = library_dir / slug
        for pdf in sorted((item_dir / "assets").glob("*.pdf")) if (item_dir / "assets").exists() else []:
            assets.append(f"[PDF]({slug}/assets/{pdf.name})")
        lines.append(
            f"| {row.get('published') or ''} | [{row.get('title') or slug}]({article}) | {' · '.join(assets)} |"
        )
    index_path = Path.home() / "park-io" / "outbox" / "library-maintenance" / "anthropic" / "claude-blog-index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    fetch_scrape = load_fetch_scrape()
    candidates = fetch_scrape.fetch_all_claude_blog_candidates(CLAUDE_BLOG_URL)
    state = load_state()
    key = f"scrape:{SOURCE_NAME}"
    seen_urls = state.get(key, {}).get("seen_urls", {})
    source = {"name": SOURCE_NAME, "profile_id": "anthropic"}
    library_dir = PROFILE_LIBRARY_DIR / "anthropic" / "items"
    saved = 0
    failed = 0
    rows = []

    for idx, candidate in enumerate(candidates, 1):
        url = candidate["url"]
        rows.append(candidate)
        try:
            html = fetch_scrape.fetch_url(url)
            extracted = fetch_scrape.extract_claude_blog_article(html)
            item = {
                "title": extracted.get("title") or candidate.get("title") or "Untitled",
                "url": url,
                "published": extracted.get("published") or candidate.get("published") or "",
                "author": extracted.get("author", ""),
                "summary": extracted.get("summary") or candidate.get("summary") or "",
                "content": extracted.get("content", ""),
                "pdfs": extracted.get("pdfs", []),
            }
            fetch_scrape.save_library_article(source, item, html)
            seen_urls[url] = seen_urls.get(url) or now_utc()
            saved += 1
            if idx % 10 == 0:
                print(f"[backfill] saved {idx}/{len(candidates)}")
        except Exception as ex:
            failed += 1
            print(f"[backfill] failed {url}: {type(ex).__name__}: {ex}")

    state[key] = {"seen_urls": seen_urls, "last_fetch": now_utc()}
    save_state(state)
    write_index(library_dir, rows)
    print(f"[backfill] done: {saved} saved, {failed} failed, {len(candidates)} candidates")
    print(f"[backfill] library: {library_dir}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
