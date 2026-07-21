#!/usr/bin/env python3
"""Compatibility wrapper for ingestion/rss/run.py."""
import ssl
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.rss import run as _rss
from ingestion.rss.run import *  # noqa: F401,F403

WHY_NOT_TV_FEED_TOKEN = "youtube.com/feeds/videos.xml?channel_id=UC5xLV_gJAP9psKcyrJ3ZIcw"
if not hasattr(_rss, "_ROOT_WRAPPER_ORIGINAL_FETCH_URL"):
    _rss._ROOT_WRAPPER_ORIGINAL_FETCH_URL = _rss.fetch_url
_ORIGINAL_FETCH_URL = _rss._ROOT_WRAPPER_ORIGINAL_FETCH_URL


def _is_whynot_tv_feed(url: str) -> bool:
    return WHY_NOT_TV_FEED_TOKEN in str(url)


def _is_ssl_eof_error(exc: Exception) -> bool:
    candidates = [exc]
    if isinstance(exc, urllib.error.URLError):
        candidates.append(exc.reason)
    return any(
        isinstance(candidate, ssl.SSLEOFError)
        or ("UNEXPECTED_EOF" in str(candidate).upper())
        for candidate in candidates
    )


def fetch_url(url, timeout=30):
    try:
        return _ORIGINAL_FETCH_URL(url, timeout=timeout)
    except Exception as exc:
        if _is_whynot_tv_feed(url) and _is_ssl_eof_error(exc):
            raise urllib.error.HTTPError(url, 599, f"recoverable SSL EOF: {exc}", {}, None) from exc
        raise


_rss.fetch_url = fetch_url
_rss.YOUTUBE_FALLBACK_HANDLES.setdefault("Why Not TV", "whynottv1999")
main = _rss.main


if __name__ == "__main__":
    main()
