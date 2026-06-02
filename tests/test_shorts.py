"""Regression test: YouTube Shorts are excluded (owner wants long videos only)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lib


def test_shorts_url_is_short():
    assert lib.is_youtube_short("https://www.youtube.com/shorts/abc123")


def test_short_duration_is_short():
    assert lib.is_youtube_short("https://www.youtube.com/watch?v=x", 30)


def test_long_video_is_not_short():
    assert not lib.is_youtube_short("https://www.youtube.com/watch?v=x", 600)


def test_unknown_duration_watch_is_not_short():
    # No /shorts/ and no duration → treat as a normal (long) video, don't drop.
    assert not lib.is_youtube_short("https://www.youtube.com/watch?v=x", None)


def test_non_youtube_unaffected():
    assert not lib.is_youtube_short("https://example.com/article", None)


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1; print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)
