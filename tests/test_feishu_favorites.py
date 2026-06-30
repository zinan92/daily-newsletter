from pathlib import Path

from ingestion.feishu_favorites import run as feishu


def test_feishu_favorites_enriches_wechat_article(monkeypatch):
    def fake_fetch(url):
        return {
            "source": "WX",
            "source_platform": "wx",
            "title": "微信文章标题",
            "author": "公众号作者",
            "handle": "",
            "tweet_created_at": "",
            "body": "微信正文内容",
            "status": "archived",
            "extra_urls": [],
            "metrics": {},
        }

    monkeypatch.setattr(feishu, "fetch_wechat_article", fake_fetch)

    item = feishu.item_for_url("https://mp.weixin.qq.com/s/demo", {})

    assert item["status"] == "archived"
    assert item["title"] == "微信文章标题"
    assert item["body"] == "微信正文内容"


def test_feishu_favorites_updates_existing_needs_fetch_wechat_note(monkeypatch, tmp_path):
    note = tmp_path / "note.md"
    note.write_text(
        "---\nstatus: needs_fetch\n---\n\n# old\n\n## 待补\n\n- [ ] 抓取或补全正文。\n",
        encoding="utf-8",
    )

    def fake_fetch(url):
        return {
            "source": "WX",
            "source_platform": "wx",
            "title": "补全后的标题",
            "author": "数字生命卡兹克",
            "handle": "",
            "tweet_created_at": "",
            "body": "补全后的正文",
            "status": "archived",
            "extra_urls": [],
            "metrics": {},
        }

    monkeypatch.setattr(feishu, "fetch_wechat_article", fake_fetch)

    result = feishu.update_existing_if_needs_fetch(
        note,
        "https://mp.weixin.qq.com/s/demo",
        {"message_id": "m1", "create_time": "2026-06-29 16:49"},
        "chat-id",
        "好文收藏",
        {},
        dry_run=False,
    )

    text = note.read_text(encoding="utf-8")
    assert result == "updated:note.md"
    assert "status: archived" in text
    assert "# 补全后的标题" in text
    assert "## 正文缓存" in text
    assert "补全后的正文" in text
    assert "## 待补" not in text


def test_backfill_needs_fetch_updates_existing_file(tmp_path, monkeypatch):
    collection = tmp_path / "collection"
    collection.mkdir()
    target = collection / "260630_X_example__abc.md"
    target.write_text(
        "\n".join(
            [
                "---",
                "id: https://x.com/example/status/123",
                "source_url: https://x.com/example/status/123",
                "source_message_id: om_test",
                "source_message_link: https://example.com/message",
                "captured_at: 2026-06-30 10:17",
                "status: needs_fetch",
                "---",
                "",
                "# example",
                "",
                "## 待补",
                "- [ ] 抓取或补全正文。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(feishu, "LIBRARY_DIR", collection)
    monkeypatch.setattr(
        feishu,
        "item_for_url",
        lambda _url, _x_items: {
            "source": "X",
            "source_platform": "x",
            "title": "补全后的标题",
            "author": "Example Author",
            "handle": "example",
            "tweet_created_at": "2026-06-30T00:00:00+00:00",
            "body": "补全后的正文",
            "status": "archived",
            "extra_urls": [],
            "metrics": {"likes": 1},
        },
    )

    result = feishu.backfill_needs_fetch("oc_test", "好文收藏", {}, dry_run=False)

    text = target.read_text(encoding="utf-8")
    assert result == ["backfill_updated:260630_X_example__abc.md:https://x.com/example/status/123"]
    assert "status: archived" in text
    assert "补全后的正文" in text
    assert "## 待补" not in text


def test_fetch_x_tweet_selects_exact_status_from_thread(monkeypatch):
    class Completed:
        returncode = 0
        stdout = (
            '{"ok": true, "data": ['
            '{"id": "999", "text": "reply"},'
            '{"id": "123", "text": "target"}'
            "]}"
        )
        stderr = ""

    monkeypatch.setattr(feishu.x_saved, "load_twitter_env", lambda: None)
    monkeypatch.setattr(feishu.x_saved, "TWITTER_BIN", "twitter")
    monkeypatch.setattr(feishu.subprocess, "run", lambda *args, **kwargs: Completed())

    tweet = feishu.fetch_x_tweet("123")

    assert tweet["text"] == "target"
