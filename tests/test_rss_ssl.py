"""Regression tests for source-specific RSS SSL recovery."""
import importlib.util
import ssl
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHY_NOT_TV_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=UC5xLV_gJAP9psKcyrJ3ZIcw"


def load_fetch_rss():
    spec = importlib.util.spec_from_file_location("fetch_rss", ROOT / "fetch-rss.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.text.encode("utf-8")


def test_whynot_tv_ssl_eof_uses_youtube_page_fallback(monkeypatch):
    module = load_fetch_rss()
    written = []
    saved_states = []
    urls = []

    def fake_urlopen(req, timeout):
        url = req.full_url
        urls.append(url)
        if url == WHY_NOT_TV_FEED:
            raise urllib.error.URLError(ssl.SSLEOFError("UNEXPECTED_EOF_WHILE_READING"))
        if url == "https://www.youtube.com/@whynottv1999/videos":
            return FakeResponse("<html>fallback page</html>")
        raise AssertionError(url)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        module._rss,
        "load_sources",
        lambda: [{"name": "Why Not TV", "platform": "rss", "url": WHY_NOT_TV_FEED}],
    )
    monkeypatch.setattr(module._rss, "load_state", lambda: {})
    monkeypatch.setattr(module._rss, "save_state", lambda state: saved_states.append(state))
    monkeypatch.setattr(module._rss, "write_source_output", lambda src, items: written.append((src, items)))
    monkeypatch.setattr(module._rss, "log", lambda *args: None)
    monkeypatch.setattr(module._rss, "today", lambda: "2026-07-21")
    monkeypatch.setattr(
        module._rss,
        "parse_youtube_videos_page",
        lambda html: [
            {
                "title": "Interview",
                "url": "https://www.youtube.com/watch?v=video12345",
                "published": "2026-07-21",
                "summary": "Published 1 hour ago.",
            }
        ],
    )
    monkeypatch.setattr(module._rss, "youtube_titles_with_ytdlp", lambda handle, limit=8: {})

    module.main()

    assert urls == [WHY_NOT_TV_FEED, "https://www.youtube.com/@whynottv1999/videos"]
    assert written[0][0]["name"] == "Why Not TV"
    assert written[0][1][0]["title"] == "Interview"
    assert saved_states[0]["rss:Why Not TV"]["last_fetch"] == "2026-07-21"
    assert "error" not in saved_states[0]["rss:Why Not TV"]


def test_non_whynot_ssl_eof_is_not_converted(monkeypatch):
    module = load_fetch_rss()

    def fake_urlopen(req, timeout):
        raise urllib.error.URLError(ssl.SSLEOFError("UNEXPECTED_EOF_WHILE_READING"))

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    try:
        module.fetch_url("https://example.com/feed.xml")
    except urllib.error.URLError:
        pass
    else:
        raise AssertionError("non-Why Not TV SSL EOF was converted")


def test_whynot_certificate_errors_are_not_downgraded(monkeypatch):
    module = load_fetch_rss()

    def fake_urlopen(req, timeout):
        raise urllib.error.URLError(ssl.SSLError("CERTIFICATE_VERIFY_FAILED"))

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    try:
        module.fetch_url(WHY_NOT_TV_FEED)
    except urllib.error.URLError as exc:
        assert "CERTIFICATE_VERIFY_FAILED" in str(exc)
    else:
        raise AssertionError("certificate verification error was downgraded")
