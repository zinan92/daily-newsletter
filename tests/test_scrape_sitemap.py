"""Regression test: Claude Blog discovery must use the sitemap, not the Webflow
index (which silently drops recent posts — that's how the May-27/28 articles were
missed), and must age-gate so the one-time backlog isn't ingested as today's news.

Run: python3 tests/test_scrape_sitemap.py
"""
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_spec = importlib.util.spec_from_file_location("fetch_scrape", os.path.join(_ROOT, "fetch-scrape.py"))
fs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fs)

SITEMAP = """<?xml version="1.0"?><urlset>
  <url><loc>https://claude.com/blog</loc></url>
  <url><loc>https://claude.com/blog/category</loc></url>
  <url><loc>https://claude.com/blog/introducing-dynamic-workflows-in-claude-code</loc></url>
  <url><loc>https://claude.com/blog/using-llms-to-secure-source-code</loc></url>
  <url><loc>https://claude.com/blog/an-old-post-from-last-year</loc></url>
</urlset>"""


def test_sitemap_extracts_articles_excludes_index_and_category():
    urls = fs.claude_blog_sitemap_urls(SITEMAP)
    assert "https://claude.com/blog/introducing-dynamic-workflows-in-claude-code" in urls
    assert "https://claude.com/blog/using-llms-to-secure-source-code" in urls
    assert "https://claude.com/blog" not in urls
    assert "https://claude.com/blog/category" not in urls
    assert len(urls) == 3


def test_parse_iso_and_display_dates():
    assert fs.parse_iso_date("2026-05-28T10:00:00Z") == "2026-05-28"
    assert fs.parse_iso_date("May 28, 2026") == "2026-05-28"
    assert fs.parse_iso_date("") == ""


def test_age_gate_recent_vs_old():
    # recent post passes the gate; very old one is filtered; junk → None (filtered)
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
    old = (datetime.now(timezone.utc) - timedelta(days=400)).strftime("%Y-%m-%d")
    assert fs.article_age_days(recent) <= fs.CLAUDE_BLOG_MAX_AGE_DAYS
    assert fs.article_age_days(old) > fs.CLAUDE_BLOG_MAX_AGE_DAYS
    assert fs.article_age_days("not a date") is None


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
            n += 1
    print(f"OK — {n} tests passed")
