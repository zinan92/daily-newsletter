"""Regression tests for WeChat scoring.

Automatic and manual WeChat items both enter the same scoring channel before
they can enter the newsletter.
"""
import importlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _wechat_item_file(path: Path, *, source_name: str, category: str) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                f"source_name: {source_name}",
                "platform: wechat",
                f"category: {category}",
                "---",
                "",
                "## 自动公众号文章",
                f"**source: {source_name} · *2026-06-09* · [link](https://mp.weixin.qq.com/s/test-auto)**",
                "",
                "这是一篇自动公众号 RSS 抓到的文章，应该进入评分队列，而不是直接绕过评分。",
            ]
        ),
        encoding="utf-8",
    )


def _item_file(path: Path, *, source_name: str, platform: str, category: str, url: str) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                f"source_name: {source_name}",
                f"platform: {platform}",
                f"category: {category}",
                "---",
                "",
                f"## {source_name} 测试内容",
                f"source: {source_name} · *2026-06-09* · [link]({url})",
                "",
                "这是一条需要统一进入评分队列的测试内容。",
            ]
        ),
        encoding="utf-8",
    )


def test_auto_wechat_rss_enters_score_queue(tmp_path, monkeypatch):
    score_items = importlib.import_module("aggregation.digest.score_items")
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    _wechat_item_file(batch_dir / "26-06-09-shuzi.md", source_name="数字生命卡兹克", category="wechat-ai")
    scores_path = tmp_path / "scores.json"
    scores_path.write_text("{}", encoding="utf-8")

    seen_batches = []

    def fake_score_batch(batch):
        seen_batches.append(batch)
        return [
            {
                "url": item["url"],
                "score": 4,
                "line_fit": ["development"],
                "tags": ["wechat-auto"],
                "reason": "自动公众号 RSS 进入评分队列。",
            }
            for item in batch
        ]

    monkeypatch.setenv("PARKIO_BATCH_DIR", str(batch_dir))
    monkeypatch.setattr(score_items, "SCORES_PATH", scores_path)
    monkeypatch.setattr(score_items, "SCORING_HEALTH_PATH", tmp_path / "scoring-health.json")
    monkeypatch.setattr(score_items, "score_batch", fake_score_batch)

    score_items.main()

    assert seen_batches, "automatic WeChat RSS item should be queued for scoring"
    assert seen_batches[0][0]["url"] == "https://mp.weixin.qq.com/s/test-auto"
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    assert scores["https://mp.weixin.qq.com/s/test-auto"]["score"] == 4


def test_manual_wechat_link_enters_score_queue(tmp_path, monkeypatch):
    score_items = importlib.import_module("aggregation.digest.score_items")
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    _wechat_item_file(batch_dir / "26-06-09-manual.md", source_name="手动公众号文章", category="wechat-manual")
    scores_path = tmp_path / "scores.json"
    scores_path.write_text("{}", encoding="utf-8")

    seen_batches = []

    monkeypatch.setenv("PARKIO_BATCH_DIR", str(batch_dir))
    monkeypatch.setattr(score_items, "SCORES_PATH", scores_path)
    monkeypatch.setattr(score_items, "SCORING_HEALTH_PATH", tmp_path / "scoring-health.json")
    def fake_score_batch(batch):
        seen_batches.append(batch)
        return [
            {
                "url": item["url"],
                "score": 4,
                "line_fit": ["content"],
                "tags": ["wechat-manual"],
                "reason": "手动公众号文章同样进入评分队列。",
            }
            for item in batch
        ]

    monkeypatch.setattr(score_items, "score_batch", fake_score_batch)

    score_items.main()

    assert seen_batches, "manual WeChat links should be queued for scoring"
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    assert scores["https://mp.weixin.qq.com/s/test-auto"]["score"] == 4


def test_official_media_and_saved_enter_score_queue(tmp_path, monkeypatch):
    score_items = importlib.import_module("aggregation.digest.score_items")
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    _item_file(
        batch_dir / "official.md",
        source_name="Claude Blog",
        platform="rss",
        category="ai-official",
        url="https://claude.com/blog/test",
    )
    _item_file(
        batch_dir / "media.md",
        source_name="Claude YouTube",
        platform="rss",
        category="video-official",
        url="https://www.youtube.com/watch?v=test",
    )
    _item_file(
        batch_dir / "saved.md",
        source_name="我的 X 收藏",
        platform="twitter",
        category="saved",
        url="https://x.com/user/status/1",
    )
    scores_path = tmp_path / "scores.json"
    scores_path.write_text("{}", encoding="utf-8")
    seen_urls = []

    def fake_score_batch(batch):
        seen_urls.extend(item["url"] for item in batch)
        return [
            {
                "url": item["url"],
                "score": 4,
                "line_fit": ["development"],
                "tags": ["unified-scoring"],
                "reason": "所有来源统一评分。",
            }
            for item in batch
        ]

    monkeypatch.setenv("PARKIO_BATCH_DIR", str(batch_dir))
    monkeypatch.setattr(score_items, "SCORES_PATH", scores_path)
    monkeypatch.setattr(score_items, "SCORING_HEALTH_PATH", tmp_path / "scoring-health.json")
    monkeypatch.setattr(score_items, "score_batch", fake_score_batch)

    score_items.main()

    assert "https://claude.com/blog/test" in seen_urls
    assert "https://www.youtube.com/watch?v=test" in seen_urls
    assert "https://x.com/user/status/1" in seen_urls


def test_discussion_boost_raises_repeated_topic_scores():
    score_items = importlib.import_module("aggregation.digest.score_items")
    scores = {
        "u1": {"score": 3, "tags": ["fable-5-subagents"], "reason": "有用。"},
        "u2": {"score": 3, "tags": ["fable-5-subagents"], "reason": "有用。"},
        "u3": {"score": 3, "tags": ["fable-5-subagents"], "reason": "有用。"},
    }
    items = [
        {"url": "u1", "source": "Claude Blog"},
        {"url": "u2", "source": "ai_xiaomu"},
        {"url": "u3", "source": "wadezone"},
    ]

    changed = score_items.apply_discussion_boost(scores, items)

    assert changed == 3
    assert scores["u1"]["score"] == 4
    assert scores["u1"]["base_score"] == 3
    assert scores["u1"]["discussion_boost"]["sources"] == 3
    assert "多源讨论加权" in scores["u1"]["reason"]
