"""Compatibility tests for root fetch wrappers after folderization.

Run: python3 tests/test_ingestion_wrappers.py
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WRAPPERS = {
    "fetch-rss.py": ["main", "parse_feed", "fetch_youtube_fallback"],
    "fetch-scrape.py": ["main", "claude_blog_sitemap_urls", "extract_claude_blog_article"],
    "fetch-twitter.py": ["main", "extract_handle", "fetch_tweets", "tweet_text"],
    "fetch-twitter-saved.py": ["main", "item_from_tweet", "content_for"],
}


def load_module(filename: str):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"), ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_root_fetch_wrappers_reexport_expected_symbols():
    for filename, attrs in WRAPPERS.items():
        module = load_module(filename)
        for attr in attrs:
            assert hasattr(module, attr), f"{filename} missing {attr}"


def test_folderized_modules_exist():
    for rel in [
        "ingestion/rss/run.py",
        "ingestion/web_scrape/run.py",
        "ingestion/x/timeline.py",
        "ingestion/x/saved.py",
    ]:
        assert (ROOT / rel).exists(), rel


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)
