"""Regression tests for YouTube long-video transcription behavior.

Run: python3 tests/test_youtube_long_transcription.py
"""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_media():
    spec = importlib.util.spec_from_file_location("media_run", ROOT / "enrichment/media/run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fake_download(cmd, timeout, retries):
    outtmpl = Path(cmd[cmd.index("-o") + 1])
    out = outtmpl.parent / "audio.mp3"
    out.write_text("fake audio", encoding="utf-8")
    return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()


def test_long_youtube_audio_uses_segmented_transcription():
    media = load_media()
    calls = {"segmented": 0, "single": 0}
    media.ensure_mlx_whisper = lambda: None
    media.run_ytdlp_with_retries = fake_download
    media.local_media_duration_seconds = lambda _path: media.MAX_ASR_SECONDS + 60
    media.video_duration_seconds = lambda _url: media.MAX_ASR_SECONDS + 60

    def segmented(_audio, duration):
        calls["segmented"] += 1
        assert duration == media.MAX_ASR_SECONDS + 60
        return "这是一段长视频分段转录结果。" * 40

    def single(_audio):
        calls["single"] += 1
        return "不应该走这里"

    media.transcribe_long_youtube_audio = segmented
    media.mlx_transcribe_audio_with_retry = single
    text = media.fetch_youtube_audio_transcript("https://www.youtube.com/watch?v=long")
    assert calls == {"segmented": 1, "single": 0}
    assert "长视频分段转录结果" in text


def test_normal_youtube_audio_uses_single_file_transcription():
    media = load_media()
    calls = {"segmented": 0, "single": 0}
    media.ensure_mlx_whisper = lambda: None
    media.run_ytdlp_with_retries = fake_download
    media.local_media_duration_seconds = lambda _path: 600
    media.video_duration_seconds = lambda _url: 600
    media.transcribe_long_youtube_audio = lambda _audio, _duration: calls.__setitem__("segmented", calls["segmented"] + 1) or ""

    def single(_audio):
        calls["single"] += 1
        return "这是一段普通长度视频转录结果。" * 40

    media.mlx_transcribe_audio_with_retry = single
    text = media.fetch_youtube_audio_transcript("https://www.youtube.com/watch?v=normal")
    assert calls == {"segmented": 0, "single": 1}
    assert "普通长度视频转录结果" in text


def test_duration_exceeds_still_maps_to_skipped_too_long_for_douyin_or_hard_cap():
    media = load_media()
    status = media.media_failure_status(RuntimeError("audio ASR skipped: duration 9999s exceeds 5400s"))
    assert status == "skipped_too_long"


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
