"""GitHub Trending source: parsing, 7-day repeat window, product radar collector.

Run: python3 -m pytest tests/test_github_trending.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import product_radar  # noqa: E402
from ingestion.github_trending import run as gh  # noqa: E402

FIXTURE = (ROOT / "tests" / "fixtures" / "github-trending-daily.html").read_text(encoding="utf-8")


def test_parse_trending_reads_rank_repo_description_and_stars():
    repos = gh.parse_trending(FIXTURE)
    assert [r["rank"] for r in repos] == [1, 2, 3]
    first = repos[0]
    assert first["full_name"] == "alibaba/open-code-review"
    assert first["url"] == "https://github.com/alibaba/open-code-review"
    assert first["language"] == "Go"
    assert first["stars_today"] > 1000
    assert first["stars_total"] > first["stars_today"]
    assert first["description"].startswith("Secure, fast")


def test_parse_trending_on_unrelated_html_yields_nothing():
    assert gh.parse_trending("<html><body><p>nope</p></body></html>") == []


def test_repeat_within_seven_days_is_not_a_new_item():
    repos = gh.parse_trending(FIXTURE)
    seen = {"alibaba/open-code-review": "2026-09-15", "cloudflare/security-audit-skill": "2026-09-01"}
    fresh = gh.new_repos(repos, seen, "2026-09-18")
    names = [r["full_name"] for r in fresh]
    assert "alibaba/open-code-review" not in names  # 3 days ago → still inside the window
    assert "cloudflare/security-audit-skill" in names  # 17 days ago → comeback counts
    assert "addyosmani/agent-skills" in names  # never seen


def test_item_carries_board_metadata_for_the_ai_stage():
    repo = gh.parse_trending(FIXTURE)[0]
    item = gh.to_item(repo, "2026-09-18")
    assert item["url"] == repo["url"]
    assert "GitHub Trending 日榜第 1 名" in item["text"]
    assert "今日 +" in item["text"]
    assert item["published"] == "2026-09-18"
    assert item["likes"] == repo["stars_today"]


def test_prune_seen_drops_entries_older_than_keep_window():
    seen = {"a/b": "2026-05-01", "c/d": "2026-09-10"}
    assert gh.prune_seen(seen, "2026-09-18", keep_days=60) == {"c/d": "2026-09-10"}


def test_product_radar_collector_scores_trending_repos(monkeypatch):
    monkeypatch.setattr(product_radar, "fetch_text", lambda url, timeout=30: FIXTURE)
    signals, meta = product_radar.fetch_github_trending()
    assert meta["source"] == "GitHub Trending"
    assert meta["fetched"] == 3
    assert meta["errors"] == []
    top = signals[0]
    assert top.source == "GitHub Trending"
    assert top.title == "alibaba/open-code-review"
    assert "stars today" in top.metric
    assert top.score > 20
    assert "开发者今日在 star" in top.reasons


def test_product_radar_collector_reports_empty_parse_as_error(monkeypatch):
    monkeypatch.setattr(product_radar, "fetch_text", lambda url, timeout=30: "<html></html>")
    signals, meta = product_radar.fetch_github_trending()
    assert signals == []
    assert meta["errors"]
