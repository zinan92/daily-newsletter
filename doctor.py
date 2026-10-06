#!/usr/bin/env python3
"""Check what this machine can run: which AI provider, which sources.

Read-only. Makes no paid LLM call and fetches nothing. Exit 1 only when no AI
provider is usable, because without one no daily can be written.

    python3 doctor.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import lib  # noqa: E402  (loads .env)


def has_module(name: str, extra_path: Path | None = None) -> bool:
    code = "import sys\n"
    if extra_path:
        code += f"sys.path.insert(0, {str(extra_path)!r})\n"
    code += f"import {name}\n"
    return subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0


def cli_ok(binary: str) -> bool:
    path = shutil.which(binary) or (binary if Path(binary).exists() else None)
    if not path:
        return False
    try:
        return subprocess.run([path, "--version"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def provider_status(name: str) -> tuple[bool, str]:
    if name == "deepseek":
        key = lib._load_secret("PARKIO_DEEPSEEK_KEY", "deepseek-key")
        return bool(key), "PARKIO_DEEPSEEK_KEY 已填" if key else "缺 PARKIO_DEEPSEEK_KEY"
    if name == "anthropic":
        if os.environ.get("PARKIO_ANTHROPIC_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
            return True, "ANTHROPIC_API_KEY 已填"
        if lib._load_secret("PARKIO_CLIPROXY_KEY", "cliproxy-key"):
            return True, "CLIProxyAPI key 已填"
        return False, "缺 ANTHROPIC_API_KEY"
    if name == "claude":
        ok = cli_ok(lib.CLAUDE_BIN)
        return ok, "claude CLI 可用（需已登录）" if ok else f"找不到 claude CLI（{lib.CLAUDE_BIN}）"
    if name == "codex":
        ok = cli_ok(lib.CODEX_BIN)
        return ok, "codex CLI 可用（需已 codex login）" if ok else f"找不到 codex CLI（{lib.CODEX_BIN}）"
    return False, f"未知 provider：{name}"


def main() -> int:
    rows: list[tuple[str, bool, str]] = []

    py_ok = sys.version_info >= (3, 11)
    rows.append(("Python ≥ 3.11", py_ok, sys.version.split()[0]))

    primary = lib.LLM_PROVIDER or "deepseek"
    ai_ok, detail = provider_status(primary)
    rows.append((f"AI：{primary}（PARKIO_LLM_PROVIDER）", ai_ok, detail))
    fallback = (lib.LLM_FALLBACK_PROVIDER or "").strip().lower()
    if fallback and fallback not in {"none", "off", "false"} and fallback != primary:
        fb_ok, fb_detail = provider_status(fallback)
        rows.append((f"备用 AI：{fallback}", fb_ok, fb_detail + ("" if fb_ok else "；不用备用就设 PARKIO_LLM_FALLBACK_PROVIDER=none")))

    sources = lib.load_sources()
    counts = Counter((row.get("platform") or "").strip() for row in sources)
    rows.append(("来源清单", bool(sources), f"{lib.SOURCES_PATH}（{len(sources)} 个在用）"))

    secrets = lib.PARKIO / "_secrets"
    twitter_bin = os.environ.get("PARKIO_TWITTER_BIN", str(Path.home() / ".local/bin/twitter"))
    twitter_auth = Path(os.environ.get("PARKIO_TWITTER_AUTH_ENV", str(ROOT / "twitter-auth.env"))).expanduser()
    x_ok = Path(twitter_bin).expanduser().exists() and twitter_auth.exists()
    x_why = "twitter-cli + 登录态都在" if x_ok else (
        "缺 twitter-cli（uv tool install twitter-cli）" if not Path(twitter_bin).expanduser().exists()
        else f"缺登录态 {twitter_auth.name}（浏览器登录 x.com 后跑 python3 refresh-twitter-auth.py）"
    )

    dy_cookie = secrets / "douyin-cookies.json"
    dy_lib = has_module("content_downloader.adapters.douyin.api_client", lib.DOWNLOAD_CAPABILITY)
    dy_ok = dy_cookie.exists() and dy_lib
    dy_why = "cookie + 下载器都在" if dy_ok else (
        "下载器依赖没装（pip install -r requirements-full.txt）" if not dy_lib
        else f"缺 {dy_cookie}（格式见 vendor/content_downloader/cookies.json.example）"
    )

    platform_rows = [
        ("rss", True, "无需登录（YouTube 频道只拿标题和简介，转写见下面「视频转写」）"),
        ("scrape", True, "无需登录"),
        ("github", True, "无需登录"),
        ("twitter", x_ok, x_why),
        ("douyin", dy_ok, dy_why),
        ("wechat", True, "无需登录，但只抓清单里给的种子文章，不会自动发现新文章"),
    ]
    for platform, ok, why in platform_rows:
        n = counts.get(platform, 0)
        if n:
            rows.append((f"来源 {platform}（{n} 个）", ok, why if ok else why + " → 这些来源会被跳过"))
    other = sorted(p for p in counts if p not in {r[0] for r in platform_rows})
    for platform in other:
        rows.append((f"来源 {platform}（{counts[platform]} 个）", True, "见 README"))

    ytdlp = has_module("yt_dlp") or bool(shutil.which("yt-dlp"))
    ffmpeg = bool(shutil.which("ffmpeg"))
    yt_cookie = Path(os.environ.get("PARKIO_YTDLP_COOKIES_FILE", str(secrets / "youtube-cookies.txt"))).expanduser()
    whisper = has_module("mlx_whisper")
    missing = [name for name, ok in (("yt-dlp", ytdlp), ("ffmpeg", ffmpeg), (f"YouTube cookie {yt_cookie}", yt_cookie.exists()), ("mlx-whisper（仅 Apple Silicon）", whisper)) if not ok]
    rows.append(("视频转写（YouTube/播客/抖音）", not missing,
                 "全部就绪" if not missing else "缺 " + "、".join(missing) + " → 视频只用标题和简介"))

    feishu = bool(os.environ.get("FEISHU_WEBHOOK_URL") and os.environ.get("FEISHU_WEBHOOK_SECRET"))
    rows.append(("飞书推送（可选）", feishu, "已配置" if feishu else "没配置 → 日报只存本地文件"))

    print(f"数据目录 PARKIO_HOME = {lib.PARKIO}")
    print(f"日报会写到 {lib.SENT_DIR}/<YY-MM-DD>.md\n")
    for name, ok, detail in rows:
        print(f"  {'✓' if ok else '✗'} {name}：{detail}")
    print()
    if not ai_ok:
        print("✗ 没有可用的 AI，写不出日报。在 .env 里填一个 key，或装好并登录 claude / codex CLI。")
        return 1
    print("✓ 可以跑：./run-daily.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
