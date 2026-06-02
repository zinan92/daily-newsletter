#!/usr/bin/env python3
"""Fetch transcript summaries for curated long-form media.

This stage is intentionally non-blocking for the reader-facing product:
videos with no transcript summary stay out of the daily panel. Operational
status is kept in media-summaries.json and logs only. Successful transcripts
are written back to the raw Markdown item; downloaded media files are temporary
and deleted after transcription.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from lib import PARKIO, ROOT, is_youtube_short, llm_call, log, parse_frontmatter, parse_md_items, today
from summarize import (
    one_line,
)

MEDIA_SUMMARIES_PATH = ROOT / "media-summaries.json"
MEDIA_QUEUE_PATH = ROOT / "media-queue.json"
DOWNLOAD_CAPABILITY = Path.home() / "content-toolkit/capabilities/download"
DOUYIN_COOKIE_FILE = Path.home() / "park-io/secrets/content-ops/douyin-cookies.json"
# Lowered from 1200: a YouTube Short / brief clip's full transcript can be
# 400-1000 chars and still summarize fine. 1200 silently dropped Shorts to
# title-only (e.g. the No Priors "Claude Code can destroy your database" Short
# at 996 chars). Env-configurable.
TRANSCRIPT_MIN_CHARS = int(os.environ.get("PARKIO_TRANSCRIPT_MIN_CHARS", "400"))
MAX_TRANSCRIPT_CHARS = 22000
DEFAULT_LIMIT = 4
MAX_ASR_SECONDS = int(os.environ.get("PARKIO_MEDIA_MAX_ASR_SECONDS", "5400"))
MLX_WHISPER_MODEL = os.environ.get("PARKIO_MLX_WHISPER_MODEL", "mlx-community/whisper-small-mlx")

if DOWNLOAD_CAPABILITY.exists():
    sys.path.insert(0, str(DOWNLOAD_CAPABILITY))

try:
    from content_downloader.adapters.douyin.adapter import DouyinAdapter
except Exception:  # pragma: no cover - runtime dependency
    DouyinAdapter = None


def load_cache() -> dict:
    if not MEDIA_SUMMARIES_PATH.exists():
        return {}
    try:
        return json.loads(MEDIA_SUMMARIES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict) -> None:
    MEDIA_SUMMARIES_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_queue() -> dict:
    if not MEDIA_QUEUE_PATH.exists():
        return {}
    try:
        return json.loads(MEDIA_QUEUE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_queue(queue: dict) -> None:
    MEDIA_QUEUE_PATH.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def media_record(item: dict, status: str, **extra) -> dict:
    return {
        "status": status,
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "source": item.get("source", ""),
        "path": item.get("_path", ""),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        **extra,
    }


def read_today_media_items() -> list[dict]:
    inbox = PARKIO / "inbox" / "unprocessed"
    if not inbox.exists():
        return []
    items = []
    for path in sorted(inbox.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        for item in parse_md_items(body):
            if item.get("published") and item["published"] != today():
                continue
            url = item.get("url", "")
            if not is_youtube_url(url) and not is_douyin_url(url):
                continue
            item["source"] = item.get("source") or fm.get("source_name", path.stem)
            item["_path"] = str(path)
            items.append(item)
    return dedupe_items(items)


def is_youtube_url(url: str) -> bool:
    return "youtube.com/" in url or "youtu.be/" in url


def is_douyin_url(url: str) -> bool:
    return "douyin.com/video/" in url or "v.douyin.com/" in url


def dedupe_items(items: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for item in items:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(item)
    return out


def parse_vtt(path: Path) -> str:
    lines = []
    seen_consecutive = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if "-->" in line or re.match(r"^\d+$", line):
            seen_consecutive.clear()
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"&amp;", "&", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line in seen_consecutive:
            continue
        seen_consecutive.add(line)
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_youtube_transcript(url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="parkio-subs.") as tmp:
        outtmpl = str(Path(tmp) / "%(id)s")
        cmd = ytdlp_base_cmd() + [
            "yt-dlp",
            "--no-warnings",
            "--ignore-no-formats-error",
            "--skip-download",
            "--write-auto-subs",
            "--write-subs",
            "--sub-langs",
            "en.*,en,zh-Hans.*,zh-Hans,zh-Hant.*,zh-Hant",
            "--sub-format",
            "vtt",
            "-o",
            outtmpl,
            url,
        ]
        result = run_with_optional_cookies(cmd, timeout=75)
        files = sorted(Path(tmp).glob("*.vtt"), key=lambda p: subtitle_rank(p.name))
        if not files:
            return fetch_youtube_audio_transcript(url)
        transcript = parse_vtt(files[0])
        if len(transcript) < TRANSCRIPT_MIN_CHARS:
            return fetch_youtube_audio_transcript(url)
        return transcript[:MAX_TRANSCRIPT_CHARS]


def fetch_douyin_transcript(url: str) -> str:
    ensure_mlx_whisper()
    if DouyinAdapter is None:
        raise RuntimeError("DouyinAdapter unavailable")
    if not DOUYIN_COOKIE_FILE.exists():
        raise RuntimeError(f"Douyin cookies not found: {DOUYIN_COOKIE_FILE}")
    cookies = json.loads(DOUYIN_COOKIE_FILE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="parkio-douyin.") as tmp:
        tmp_path = Path(tmp)
        adapter = DouyinAdapter(cookies=cookies)
        item = asyncio.run(adapter.download_single(url, tmp_path))
        video_files = [
            tmp_path / "douyin" / item.author_id / item.content_id / rel
            for rel in item.media_files
            if str(rel).lower().endswith((".mp4", ".mov", ".m4v", ".webm"))
        ]
        video = next((p for p in video_files if p.exists()), None)
        if not video:
            raise RuntimeError("Douyin download produced no video file")
        duration = local_media_duration_seconds(video)
        if duration and duration > MAX_ASR_SECONDS:
            raise RuntimeError(f"audio ASR skipped: duration {duration}s exceeds {MAX_ASR_SECONDS}s")
        transcript = mlx_transcribe_audio(video)
        transcript = re.sub(r"\s+", " ", transcript).strip()
        if len(transcript) < TRANSCRIPT_MIN_CHARS:
            raise RuntimeError(f"audio transcript too short: {len(transcript)} chars")
        return transcript[:MAX_TRANSCRIPT_CHARS]


def fetch_media_transcript(url: str) -> str:
    if is_douyin_url(url):
        return fetch_douyin_transcript(url)
    if is_youtube_url(url):
        return fetch_youtube_transcript(url)
    raise RuntimeError(f"unsupported media url: {url}")


def ytdlp_base_cmd() -> list[str]:
    return []


def ytdlp_executable() -> list[str]:
    """Use the newest installed yt-dlp path.

    Homebrew's executable can lag behind the Python package on this machine.
    Prefer `python -m yt_dlp` when available so extractor fixes land without
    waiting for a separate binary update.
    """
    probe = subprocess.run(
        [sys.executable, "-c", "import yt_dlp"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "yt_dlp"]
    if Path("/opt/homebrew/bin/yt-dlp").exists():
        return ["/opt/homebrew/bin/yt-dlp"]
    return ["yt-dlp"]


def ytdlp_cookie_sources() -> list[str]:
    raw = os.environ.get("PARKIO_YTDLP_COOKIE_SOURCES", "chrome,chrome:Default")
    return [part.strip() for part in raw.split(",") if part.strip()]


def ytdlp_cookies_file() -> str:
    return os.environ.get(
        "PARKIO_YTDLP_COOKIES_FILE",
        str(Path.home() / "park-io/secrets/youtube-cookies.txt"),
    ).strip()


def normalize_ytdlp_cmd(cmd: list[str]) -> list[str]:
    if cmd and cmd[0] == "yt-dlp":
        return ytdlp_executable() + cmd[1:]
    return cmd


def ytdlp_attempt_label(cmd: list[str]) -> str:
    if "--cookies" in cmd:
        idx = cmd.index("--cookies")
        if idx + 1 < len(cmd):
            return f"cookies-file:{Path(cmd[idx + 1]).name}"
    if "--cookies-from-browser" in cmd:
        idx = cmd.index("--cookies-from-browser")
        if idx + 1 < len(cmd):
            return f"cookies:{cmd[idx + 1]}"
    return "no-cookies"


def run_with_optional_cookies(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    if (
        shutil.which("yt-dlp") is None
        and not Path("/opt/homebrew/bin/yt-dlp").exists()
        and subprocess.run(
            [sys.executable, "-c", "import yt_dlp"],
            capture_output=True,
            text=True,
            timeout=10,
        ).returncode
        != 0
    ):
        raise RuntimeError("yt-dlp not found")
    cmd = normalize_ytdlp_cmd(cmd)
    attempts = []
    if "--cookies-from-browser" not in cmd:
        exe_len = 3 if cmd[:3] == [sys.executable, "-m", "yt_dlp"] else 1
        cookies_file = ytdlp_cookies_file()
        if cookies_file and Path(cookies_file).exists():
            attempts.append(cmd[:exe_len] + ["--cookies", cookies_file] + cmd[exe_len:])
        for source in ytdlp_cookie_sources():
            attempts.append(cmd[:exe_len] + ["--cookies-from-browser", source] + cmd[exe_len:])
    attempts.append(cmd)
    failures = []
    for attempt in attempts:
        result = subprocess.run(attempt, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result
        failures.append(
            f"[{ytdlp_attempt_label(attempt)}]\n"
            f"{(result.stderr or result.stdout or '').strip()}"
        )
    merged = "\n\n".join(failures)
    return subprocess.CompletedProcess(
        attempts[-1],
        1,
        stdout="",
        stderr=merged[:4000] or "yt-dlp failed",
    )


def video_duration_seconds(url: str) -> int:
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--dump-json",
        "--skip-download",
        url,
    ]
    result = run_with_optional_cookies(cmd, timeout=45)
    if result.returncode != 0:
        return 0
    try:
        data = json.loads(result.stdout.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return 0
    try:
        return int(float(data.get("duration") or 0))
    except (TypeError, ValueError):
        return 0


def local_media_duration_seconds(path: Path) -> int:
    if shutil.which("ffprobe") is None and not Path("/opt/homebrew/bin/ffprobe").exists():
        return 0
    ffprobe = "/opt/homebrew/bin/ffprobe" if Path("/opt/homebrew/bin/ffprobe").exists() else "ffprobe"
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return 0
    try:
        return int(float(result.stdout.strip() or 0))
    except (TypeError, ValueError):
        return 0


def fetch_youtube_audio_transcript(url: str) -> str:
    ensure_mlx_whisper()
    duration = video_duration_seconds(url)
    if duration and duration > MAX_ASR_SECONDS:
        raise RuntimeError(f"audio ASR skipped: duration {duration}s exceeds {MAX_ASR_SECONDS}s")
    with tempfile.TemporaryDirectory(prefix="parkio-audio.") as tmp:
        tmp_path = Path(tmp)
        outtmpl = str(tmp_path / "%(id)s.%(ext)s")
        download_cmd = [
            "yt-dlp",
            "--no-warnings",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "7",
            "-o",
            outtmpl,
            url,
        ]
        result = run_with_optional_cookies(download_cmd, timeout=300)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "audio download failed").strip()[:500])
        audio_files = sorted(tmp_path.glob("*.mp3")) or sorted(tmp_path.glob("*"))
        audio = next((p for p in audio_files if p.is_file()), None)
        if not audio:
            raise RuntimeError("audio download produced no file")
        transcript = mlx_transcribe_audio(audio)
        transcript = re.sub(r"\s+", " ", transcript).strip()
        if len(transcript) < TRANSCRIPT_MIN_CHARS:
            raise RuntimeError(f"audio transcript too short: {len(transcript)} chars")
        return transcript[:MAX_TRANSCRIPT_CHARS]


def ensure_mlx_whisper() -> None:
    code = "import mlx_whisper"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
    if result.returncode != 0:
        raise RuntimeError("no subtitle files and mlx_whisper is not available")


def mlx_transcribe_audio(audio: Path) -> str:
    code = """
import json
import sys
import mlx_whisper

audio_path, model = sys.argv[1:3]
result = mlx_whisper.transcribe(
    audio_path,
    path_or_hf_repo=model,
    verbose=False,
    word_timestamps=False,
)
segments = result.get("segments") or []
parts = []
for segment in segments:
    text = " ".join(str(segment.get("text") or "").split())
    if text:
        parts.append(text)
if not parts:
    parts.append(" ".join(str(result.get("text") or "").split()))
print("\\n".join(parts))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(audio), MLX_WHISPER_MODEL],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "mlx_whisper failed").strip()[:500])
    return result.stdout.strip()


def subtitle_rank(filename: str) -> tuple[int, str]:
    name = filename.lower()
    if ".zh-hans" in name or ".zh-hant" in name:
        return (0, name)
    if ".en." in name:
        return (1, name)
    if ".en-en." in name:
        return (2, name)
    return (9, name)


def parse_summary(text: str) -> dict:
    one_liner = ""
    bullets = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("- "):
            bullets.append(line.removeprefix("- ").strip())
        elif not one_liner:
            one_liner = re.sub(r"^(一句话|摘要)[：:]\s*", "", line).strip()
    return {
        "summary": one_liner or one_line(text, limit=180),
        "bullets": bullets[:4],
    }


def summarize_transcript(item: dict, transcript: str) -> dict:
    prompt = f"""你是 Park-IO 的长内容编辑。下面是一个 YouTube / Podcast 的字幕文本。

请输出给最终内容消费者看的中文摘要，不要输出处理状态、字幕质量、metadata。

要求：
- 第一行是一句话摘要，80-130 个中文字符
- 后面输出 3-4 条 bullet，每条以 `- ` 开头
- 只写内容本身：这个视频讲了什么、关键观点是什么、和 AI/创业/产品/投资判断有什么关系
- 不要写“值得看”“我注意到”“这期主要围绕标题”
- 不要提 transcript、字幕、抓取、处理状态

标题：{item.get('title', '')}
来源：{item.get('source', '')}
字幕：
{transcript}
"""
    text = llm_call(prompt, max_tokens=1300)
    parsed = parse_summary(text)
    if bad_summary(parsed):
        raise RuntimeError("summary is not publishable")
    parsed.update(
        {
            "status": "summarized",
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    return parsed


def write_transcript_to_markdown(path: Path, url: str, transcript: str) -> None:
    """Persist a successful transcript in the raw Markdown item.

    Media files stay temporary; the durable raw evidence is the transcript text.
    """
    text = path.read_text(encoding="utf-8")
    marker = f"[link]({url})"
    start = text.find(marker)
    if start < 0:
        return
    heading = text.rfind("\n## ", 0, start)
    if heading < 0:
        heading = text.rfind("\n# ", 0, start)
    next_heading = text.find("\n## ", start + len(marker))
    if next_heading < 0:
        next_heading = len(text)
    section = text[heading:next_heading]
    transcript_block = "\n\n### Transcript\n\n" + transcript.strip() + "\n"
    if "### Transcript" in section:
        section = re.sub(r"\n\n### Transcript\n\n.*?\n(?=\n## |\Z)", transcript_block, section, flags=re.S)
    else:
        section = section.rstrip() + transcript_block
    path.write_text(text[:heading] + section + text[next_heading:], encoding="utf-8")


def bad_summary(parsed: dict) -> bool:
    text = " ".join([parsed.get("summary", "")] + parsed.get("bullets", []))
    bad = (
        "字幕",
        "transcript",
        "无法准确",
        "无法理解",
        "重新处理",
        "质量较差",
        "处理状态",
        "metadata",
        "这期主要围绕",
    )
    return any(marker.lower() in text.lower() for marker in bad)


def media_failure_status(exc: Exception) -> str:
    text = str(exc).lower()
    if "exceeds" in text:
        return "skipped_too_long"
    if (
        "no subtitle files" in text
        or "transcript too short" in text
        or "audio transcript too short" in text
        or "download produced no video" in text
    ):
        return "no_transcript"
    return "failed"


def should_retry(record: dict) -> bool:
    if not record:
        return True
    if record.get("status") == "summarized":
        return False
    updated = record.get("updated_at", "")
    try:
        dt = datetime.fromisoformat(updated)
    except ValueError:
        return True
    return datetime.now() - dt > timedelta(hours=18)


def main() -> None:
    cache = load_cache()
    queue = load_queue()
    items = read_today_media_items()
    limit = DEFAULT_LIMIT
    processed = 0
    log("fetch-media-transcripts", f"START — {len(items)} media items")
    for item in items:
        url = item.get("url", "")
        # Owner wants long videos only — never spend a download/transcription on
        # a YouTube Short.
        if is_youtube_short(url, item.get("duration")):
            queue[url] = media_record(item, "skipped_short")
            cache[url] = {
                "status": "skipped_short", "title": item.get("title", ""), "url": url,
                "source": item.get("source", ""),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            continue
        queue.setdefault(url, media_record(item, "pending"))
        if not should_retry(cache.get(url, {})):
            queue[url] = {
                **queue.get(url, {}),
                **media_record(item, cache.get(url, {}).get("status", "summarized")),
            }
            continue
        if processed >= limit:
            log("fetch-media-transcripts", f"  limit reached: {limit}")
            break
        try:
            queue[url] = media_record(item, "processing")
            save_queue(queue)
            log("fetch-media-transcripts", f"  fetching transcript: {item.get('source')} — {item.get('title')}")
            transcript = fetch_media_transcript(url)
            cache[url] = summarize_transcript(item, transcript)
            queue[url] = media_record(
                item,
                "summarized",
                chars=len(transcript),
                summary_chars=len(cache[url].get("summary", "")),
            )
            if item.get("_path"):
                write_transcript_to_markdown(Path(item["_path"]), url, transcript)
            log("fetch-media-transcripts", f"  summarized: {url}")
        except Exception as ex:
            status = media_failure_status(ex)
            cache[url] = {
                "status": status,
                "title": item.get("title", ""),
                "url": url,
                "source": item.get("source", ""),
                "error": f"{type(ex).__name__}: {str(ex)[:300]}",
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            queue[url] = media_record(
                item,
                status,
                error=f"{type(ex).__name__}: {str(ex)[:300]}",
            )
            log("fetch-media-transcripts", f"  skipped: {url}: {type(ex).__name__}: {ex}")
        processed += 1
        save_cache(cache)
        save_queue(queue)
    save_cache(cache)
    save_queue(queue)
    log("fetch-media-transcripts", "DONE")


if __name__ == "__main__":
    main()
