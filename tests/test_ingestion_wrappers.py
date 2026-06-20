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
    "fetch-douyin.py": ["main", "item_from_aweme", "awemes_to_deliver"],
    "fetch-wechat-rss.py": ["main", "parse_xml_feed", "parse_json_feed", "feed_url_for_source"],
    "fetch-wechat-exporter.py": ["main", "item_from_json", "match_source"],
    "fetch-manual-links.py": ["main", "load_fetch_wechat", "urls_from_pending"],
    "fetch-wechat.py": ["main", "fetch_url", "parse_article", "save_article_to_library"],
    "fetch-media-transcripts.py": ["main", "retryable_failed_items", "fetch_media_transcript"],
    "score.py": ["main"],
    "score-items.py": ["main", "score_batch", "write_scoring_health"],
    "build-digest.py": ["main"],
    "build-daily-bundle.py": ["main"],
    "build-product-radar.py": ["main"],
    "summarize.py": ["main", "load_scores", "source_health"],
    "check-quality.py": ["main"],
    "quality-check.py": ["main", "raw_english_body_lines", "heading_divergence"],
    "ai-quality-check.py": ["main", "valid_blocking_issue"],
    "archive-items.py": ["main", "archive_item"],
    "finalize-local.py": ["main", "batch_artifact_paths", "batch_label"],
    "html-to-long-image.py": ["main", "trim_bottom_whitespace"],
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
        "ingestion/douyin/run.py",
        "ingestion/wechat_rss/run.py",
        "ingestion/wechat_rss/exporter.py",
        "ingestion/manual_links/run.py",
        "ingestion/manual_links/wechat_seed.py",
        "enrichment/media/run.py",
        "aggregation/digest/score_stage.py",
        "aggregation/digest/score_items.py",
        "aggregation/digest/build.py",
        "aggregation/digest/summarize.py",
        "aggregation/digest/check_stage.py",
        "aggregation/digest/quality.py",
        "aggregation/digest/ai_quality.py",
        "aggregation/digest/archive.py",
        "aggregation/digest/finalize_local.py",
        "aggregation/digest/html_to_long_image.py",
    ]:
        assert (ROOT / rel).exists(), rel


def test_manual_links_uses_folderized_wechat_parser():
    module = load_module("fetch-manual-links.py")
    wechat = module.load_fetch_wechat()
    assert wechat.__name__ == "ingestion.manual_links.wechat_seed"
    assert hasattr(wechat, "parse_article")


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
