"""X home timeline lane: tracked-account skip, engagement floor, retweet collapse, 48h seen window.

Run: python3 -m pytest tests/test_x_home.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ingestion.x import home  # noqa: E402

NOW = datetime(2026, 9, 18, 20, 0, 0)


def tweet(tid: str, handle: str, text: str, likes: int = 50, **extra) -> dict:
    return {
        "id": tid,
        "text": text,
        "author": {"name": handle.title(), "screenName": handle},
        "metrics": {"likes": likes, "retweets": 3},
        "createdAtLocal": "2026-09-18 19:30",
        "isRetweet": False,
        **extra,
    }


def test_tracked_handles_come_from_twitter_sources_only():
    sources = [
        {"platform": "twitter", "url": "https://x.com/vista8"},
        {"platform": "twitter", "url": "https://x.com/Oran_ge/"},
        {"platform": "rss", "url": "https://x.com/notatwitterrow"},
        {"platform": "twitter", "url": "https://x.com/home"},
    ]
    assert home.tracked_handles(sources) == {"vista8", "oran_ge"}


def test_select_skips_tracked_low_engagement_and_seen():
    tweets = [
        tweet("1", "vista8", "Jev waitlist 开放了"),                 # tracked → skip
        tweet("2", "someone", "小号发的", likes=3),                   # below floor → skip
        tweet("3", "builder", "Hypit 两天 8000 星"),                  # keep
        tweet("4", "other", "已经见过的", likes=99),                  # seen → skip
        tweet("5", "quiet", "", likes=200),                           # empty → skip
    ]
    seen = {"4": (NOW - timedelta(hours=3)).isoformat(timespec="seconds")}
    items, reasons = home.select_tweets(tweets, tracked={"vista8"}, seen=seen, min_likes=20, now=NOW)
    assert [i["id"] for i in items] == ["2", "3"]  # low-engagement post is kept for the radar…
    assert items[0]["category"] == "ai-timeline-low"  # …but tagged so the coarse filter drops it
    assert items[1]["category"] == "ai-timeline"
    items = items[1:]
    assert items[0]["url"] == "https://x.com/builder/status/3"
    assert items[0]["published"] == "2026-09-18"
    assert reasons == {"tracked_account": 1, "low_engagement": 1, "seen": 1, "empty": 1, "kept": 2}
    assert "3" in seen  # newly kept ids are stamped so the next run skips them


def test_retweet_collapses_to_original_and_dedupes_within_run():
    original = tweet("10", "origin", "Jev: System One model", likes=900)
    rt = {
        "id": "11",
        "text": "RT @origin: Jev: System One model",
        "author": {"screenName": "fan"},
        "metrics": {"likes": 0},
        "isRetweet": True,
        "retweetedStatus": original,
    }
    items, reasons = home.select_tweets([rt, original], tracked=set(), seen={}, min_likes=20, now=NOW)
    assert [i["id"] for i in items] == ["10"]
    assert items[0]["handle"] == "origin"
    assert reasons["seen"] == 1


def test_prune_seen_rolls_off_after_48_hours():
    seen = {
        "old": (NOW - timedelta(hours=49)).isoformat(timespec="seconds"),
        "fresh": (NOW - timedelta(hours=47)).isoformat(timespec="seconds"),
    }
    assert home.prune_seen(seen, NOW) == {"fresh": seen["fresh"]}


def test_same_tweet_in_both_feeds_is_written_once():
    t = tweet("7", "dev", "OpenRouter Union Alpha 免费 262K", likes=120)
    a = {**t, "_feed": "following"}
    b = {**t, "_feed": "for-you"}
    items, _ = home.select_tweets([a, b], tracked=set(), seen={}, min_likes=20, now=NOW)
    assert len(items) == 1
    assert items[0]["feed"] == "following"


def test_timeline_items_need_a_strong_ai_signal_to_enter_the_batch():
    from stages.coarse_filter.filter import should_keep_item

    fm = {"category": "ai-timeline", "platform": "twitter", "source_name": "X 首页时间线"}

    def item(text: str) -> dict:
        return {"title": text[:40], "content": text, "source": "X 首页时间线", "url": "https://x.com/a/status/1"}

    keep, reason = should_keep_item(fm, item("Jev is a System One model: typed decisions, 40x faster than an LLM. Waitlist open."))
    assert keep, reason
    keep, reason = should_keep_item(fm, item("Hypit 两天 8000 星，开源的爆款视频克隆系统，agent 原生"))
    assert keep, reason
    keep, reason = should_keep_item(fm, item("As a Catholic I wish there was a more persuasive argument for why contraception is immoral, again and again."))
    assert not keep
    assert reason == "timeline_no_domain_signal"
    keep, reason = should_keep_item(fm, item("$420M USDC transactions in a month. Solana is where USDC gets spent."))
    assert not keep

    # Other lanes keep the old, looser behaviour.
    keep, _ = should_keep_item({"category": "ai", "platform": "twitter"}, item("As a Catholic I wish there was a more persuasive argument, again and again, for a long long time, longer than ninety characters."))
    assert keep


def test_low_engagement_timeline_items_never_enter_the_batch():
    from stages.coarse_filter.filter import should_keep_item

    fm = {"category": "ai-timeline-low", "platform": "twitter", "source_name": "X 首页时间线"}
    keep, reason = should_keep_item(fm, {"title": "Hypit", "content": "使用 Hypit 复刻小Lin说的视频教程，agent 一键出片", "source": "X 首页时间线", "url": "https://x.com/a/status/2"})
    assert not keep
    assert reason == "timeline_low_engagement_radar_only"
