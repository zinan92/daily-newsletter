"""X 收藏当小时进 002_个人收藏；第二天早上的 archive 不重复写，raw 不被标记。"""
import json
from datetime import datetime
from pathlib import Path

import pytest

import ingestion.collection_index as collection_index
import stages.archive.run as archive
import stages.archive.x_saved_now as now
from stages.to_md.run import marker_path, render_item_markdown, normalize_record


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lib_dir = tmp_path / "002_个人收藏"
    monkeypatch.setattr(archive, "LIBRARY_DIR", lib_dir)
    monkeypatch.setattr(collection_index, "LIBRARY_DIR", lib_dir)
    monkeypatch.setattr(archive, "source_index", lambda: {})
    monkeypatch.setattr(now, "source_index", lambda: {})
    return lib_dir


def _raw(tmp_path: Path, day: str, tweet: str, kind: str = "bookmark") -> Path:
    folder = tmp_path / "raw" / day / "x-saved"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day}-x-{tweet}.json"
    path.write_text(json.dumps({
        "id": tweet, "url": f"https://x.com/someone/status/{tweet}",
        "text": f"文章标题：收藏的文章 {tweet}\n\n正文 {tweet}\n\n"
                + ("这是你点赞保存的内容。" if kind == "like" else "这是你主动收藏的内容。"),
        "author": "某人",
        "saved_kind": kind, "source": "我的 X 收藏", "source_name": "我的 X 收藏",
        "profile_id": "x-saved", "profile_name": "我的 X 收藏", "channel": "x", "platform": "twitter",
        "category": "personal-saved",
    }, ensure_ascii=False), encoding="utf-8")
    return path


def test_saved_today_lands_once_and_morning_run_does_not_duplicate(tmp_path: Path, library: Path) -> None:
    raw = [_raw(tmp_path, "2026-09-28", "111"), _raw(tmp_path, "2026-09-27", "222")]
    files = now.raw_saved_files(tmp_path / "raw", now=datetime(2026, 9, 28, 15))
    assert sorted(p.name for p in files) == sorted(p.name for p in raw)

    assert now.archive_saved(files, batch="26-09-28") == 2
    notes = sorted(p.name for p in library.glob("*.md"))
    assert len(notes) == 2 and all(n.startswith("260928_X_") for n in notes)
    assert "https://x.com/someone/status/111" in (library / notes[0]).read_text() + (library / notes[1]).read_text()

    # 再跑一小时：没有新的
    assert now.archive_saved(files, batch="26-09-28") == 0
    # 第二天早上日报那趟 archive 同一条：跳过，不写 260929_ 的第二份
    item = tmp_path / "item.md"
    item.write_text(render_item_markdown(normalize_record(raw[0])), encoding="utf-8")
    assert archive.archive_item(item, "26-09-29", {}) == 0
    assert sorted(p.name for p in library.glob("*.md")) == notes
    # raw 没有被标记，早上的 to_md 照常处理
    assert not any(marker_path(p).exists() for p in raw)


def test_morning_run_still_rewrites_its_own_file(tmp_path: Path, library: Path) -> None:
    raw = _raw(tmp_path, "2026-09-28", "333")
    item = tmp_path / "item.md"
    item.write_text(render_item_markdown(normalize_record(raw)), encoding="utf-8")
    assert archive.archive_item(item, "26-09-28", {}) == 1
    assert archive.archive_item(item, "26-09-28", {}) == 1  # 同一天重跑照旧覆盖同一个文件
    assert len(list(library.glob("*.md"))) == 1


def test_liked_tweets_never_land_in_002(tmp_path: Path, library: Path) -> None:
    liked = _raw(tmp_path, "2026-09-30", "444", kind="like")
    saved = _raw(tmp_path, "2026-09-30", "555")
    # 每小时那趟
    assert now.archive_saved([liked, saved], batch="26-09-30") == 1
    notes = list(library.glob("*.md"))
    assert len(notes) == 1 and "status/555" in notes[0].read_text()
    # 早上日报那趟
    item = tmp_path / "item.md"
    item.write_text(render_item_markdown(normalize_record(liked)), encoding="utf-8")
    assert archive.archive_item(item, "26-10-01", {}) == 0
    # 老 raw 没有 saved_kind 字段，只剩正文里的点赞标记，也要挡住
    data = json.loads(liked.read_text(encoding="utf-8"))
    data.pop("saved_kind")
    liked.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    item.write_text(render_item_markdown(normalize_record(liked)), encoding="utf-8")
    assert archive.archive_item(item, "26-10-01", {}) == 0
    assert len(list(library.glob("*.md"))) == 1


def test_like_then_bookmark_is_emitted_as_bookmark(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import ingestion.x.saved as saved

    tweet = {"id": "666", "text": "先赞后藏", "author": {"name": "某人", "screenName": "someone"}}
    feeds: dict[str, list[dict]] = {"bookmarks": [], "likes": [tweet]}
    written: list[list[dict]] = []
    monkeypatch.setattr(saved, "DB_PATH", tmp_path / "db.json")
    monkeypatch.setattr(saved, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(saved, "CANDIDATES_PATH", tmp_path / "cand.json")
    monkeypatch.setattr(saved, "BACKFILL_RECENT_BOOKMARKS", 0)
    monkeypatch.setattr(saved, "load_sources", lambda: [])
    monkeypatch.setattr(saved, "twitter_article", lambda _tid: {})
    monkeypatch.setattr(saved, "twitter_json", lambda args: list(feeds[args[0]]))
    monkeypatch.setattr(saved, "write_source_output", lambda _src, items: written.append(items))
    (tmp_path / "state.json").write_text(json.dumps({"bootstrapped_kinds": ["bookmark", "like"]}))

    saved.main()  # 先点赞
    assert [i["saved_kind"] for i in written[-1]] == ["like"]

    feeds["bookmarks"] = [tweet]
    saved.main()  # 后来又收藏了
    assert [i["saved_kind"] for i in written[-1]] == ["bookmark"]

    written.clear()
    saved.main()  # 仍在点赞列表里：不再重复发，也不把收藏降级回 like
    assert written == []
    db = json.loads((tmp_path / "db.json").read_text(encoding="utf-8"))
    assert db["666"]["saved_kind"] == "bookmark"
