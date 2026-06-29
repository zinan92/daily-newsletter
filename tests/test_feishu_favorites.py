import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_favorites():
    spec = importlib.util.spec_from_file_location("feishu_favorites", ROOT / "ingestion" / "feishu_favorites" / "run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_feishu_favorites_enriches_wechat_article(monkeypatch):
    favorites = load_favorites()

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

    monkeypatch.setattr(favorites, "fetch_wechat_article", fake_fetch)

    item = favorites.item_for_url("https://mp.weixin.qq.com/s/demo", {})

    assert item["status"] == "archived"
    assert item["title"] == "微信文章标题"
    assert item["body"] == "微信正文内容"


def test_feishu_favorites_updates_existing_needs_fetch_wechat_note(monkeypatch, tmp_path):
    favorites = load_favorites()
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

    monkeypatch.setattr(favorites, "fetch_wechat_article", fake_fetch)

    result = favorites.update_existing_if_needs_fetch(
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
