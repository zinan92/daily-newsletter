# Technology Stack

**Analysis Date:** 2026-06-04

## Languages

**Primary:**
- Python 3.11+ - Pipeline scripts, source fetchers, scoring, summarization, quality gates, health/status generation, and artifact rendering. Runtime selection is enforced by `fetch-all.sh`, which checks `sys.version_info >= (3, 11)`.
- Bash - launchd-friendly orchestration wrappers in `fetch-all.sh` and `push-digest.sh`.
- Markdown - Source configuration and durable content queues use Markdown tables, YAML-like frontmatter, and item sections through `~/park-io/sources.md`, `~/park-io/inbox/manual-links.md`, `~/park-io/inbox/unprocessed/*.md`, and `~/park-io/inbox/processed/<batch>/*.md`.
- HTML/CSS - Reader and maintainer artifacts are generated as HTML by `summarize.py`, `generate-status.py`, and rendered to PNG by `html-to-long-image.py`.

**Secondary:**
- JSON - Runtime state, media queues, Telegram dedupe, scoring health, and source health use JSON files such as `state.json`, `media-summaries.json`, `media-queue.json`, `tg-push-state.json`, `x-saved-items.json`, and `x-saved-state.json`.
- XML/RSS/Atom - RSS, Atom, YouTube feed, and WeChat bridge parsing is implemented in `fetch-rss.py` and `fetch-wechat-rss.py` with `xml.etree.ElementTree`.
- YAML - Workflow topology is documented as `inbox-workflow.yaml` per `AGENTS.md`, although the renderer/validator live outside the files inspected here.

## Runtime

**Environment:**
- Local macOS CLI/launchd pipeline, not an HTTP service. README describes it as a CLI/cron-style workflow with no exposed HTTP API.
- Python interpreter resolution is owned by `fetch-all.sh`: prefer `PARKIO_PYTHON`, then `/usr/local/bin/python3`, `/opt/homebrew/bin/python3`, `~/content-toolkit/capabilities/download/.venv/bin/python`, then `python3`.
- launchd runs use working directory `/Users/wendy/work/input-to-park` and PATH `/Users/wendy/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin` from `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-fetch.plist`, `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-push.plist`, and `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-health.plist`.

**Package Manager:**
- Not detected in repo: no `requirements.txt`, `pyproject.toml`, `Pipfile`, `poetry.lock`, or `uv.lock` was present under `/Users/wendy/work/input-to-park`.
- Dependencies are imported opportunistically from the active Python environment and external local tool directories. Do not add a new package manager without first stabilizing the runtime contract.
- Lockfile: missing.

## Frameworks

**Core:**
- Standard-library-first Python scripts - `urllib.request`, `xml.etree.ElementTree`, `subprocess`, `json`, `pathlib`, `html.parser`, and `re` are the dominant implementation surface.
- File-first pipeline - `lib.py` centralizes root paths, state loading, source parsing, LLM calls, item rendering, and Markdown queue writing.
- Deterministic routing - `digest_config.py` maps source names to roles, authority, groups, and digest sections; AI is used inside scoring/summarization/QC nodes, not for routing.

**Testing:**
- Plain Python test files - `tests/test_*.py` files use direct `assert` statements and can be run with `for t in tests/test_*.py; do python3 "$t"; done`.
- `unittest.mock` is used in `tests/test_llm_fallback.py`; there is no detected pytest/vitest/jest config.

**Build/Dev:**
- No compiled build step. `build-digest.py` invokes `summarize.py`, then renders the generated HTML to PNG via `html-to-long-image.py`.
- Google Chrome headless is the PNG rendering runtime in `html-to-long-image.py`, with DevTools websocket rendering when `websockets` exists and Chrome CLI screenshot fallback otherwise.
- `fetch-all.sh` and `push-digest.sh` are the operational entrypoints consumed by launchd.

## Key Dependencies

**Critical:**
- DeepSeek OpenAI-compatible Chat Completions API - Primary LLM provider in `lib.py` via `PARKIO_LLM_PROVIDER=deepseek`, endpoint `PARKIO_DEEPSEEK_ENDPOINT`, model `PARKIO_DEEPSEEK_MODEL`, and key `PARKIO_DEEPSEEK_KEY` or `~/park-io/secrets/deepseek-key`.
- CLIProxyAPI / Sonnet - Fallback Anthropic-compatible provider in `lib.py`, using `PARKIO_CLIPROXY_ENDPOINT`, `PARKIO_CLIPROXY_KEY` or `~/park-io/secrets/cliproxy-key`, and `PARKIO_CLIPROXY_MODEL`.
- `twitter` CLI - X source fetching uses `/Users/wendy/.local/bin/twitter` in `fetch-twitter.py` and `fetch-twitter-saved.py`.
- `content-toolkit` download capability - Douyin fetching/transcription imports `content_downloader` from `~/content-toolkit/capabilities/download` in `fetch-douyin.py` and `fetch-media-transcripts.py`.
- `yt-dlp` / `yt_dlp` - YouTube feed fallback and transcript/audio download use Homebrew `yt-dlp`, `python -m yt_dlp`, or PATH `yt-dlp` in `fetch-rss.py` and `fetch-media-transcripts.py`.
- MLX Whisper - Audio ASR uses `mlx_whisper` with default model `mlx-community/whisper-small-mlx` in `fetch-media-transcripts.py`.

**Infrastructure:**
- Google Chrome - Full-page PNG rendering depends on `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` in `html-to-long-image.py`.
- `websockets` Python package - Optional DevTools protocol renderer in `html-to-long-image.py`.
- Pillow (`PIL`) - Optional whitespace trimming for PNG outputs in `html-to-long-image.py`.
- `ffprobe` - Optional duration probe for downloaded media in `fetch-media-transcripts.py`, preferring `/opt/homebrew/bin/ffprobe`.
- Telegram Bot API - Delivery and health alerts use `urllib.request` in `push-telegram.py` and `lib.py`.

## Command/Script Entry Points

**Fetch:**
- `./fetch-all.sh` - launchd-safe fetch wrapper, every 4 hours; calls `fetch.py`.
- `fetch.py` - Runs source stages: `fetch-rss.py`, `fetch-twitter.py`, `fetch-twitter-saved.py`, `fetch-scrape.py`, `fetch-wechat.py`, `fetch-wechat-rss.py`, `fetch-wechat-exporter.py`, `fetch-douyin.py`, `fetch-manual-links.py`, `fetch-media-transcripts.py`, then records `source-health.py --record` and regenerates `generate-status.py`.

**Daily Digest:**
- `./push-digest.sh` - Daily build wrapper; waits for fetch lock, opens a batch, runs `score.py`, `build-digest.py`, `check-quality.py`, `archive-items.py`, `finalize-local.py`, and optionally `send-artifacts.py`.
- `open-batch.py` - Moves pending raw Markdown into `~/park-io/inbox/processed/<batch>/`.
- `score.py` / `score-items.py` - Scores processed batch items and writes health state.
- `build-digest.py` / `summarize.py` - Generates Markdown/HTML digest and PNG.
- `check-quality.py` / `quality-check.py` / `ai-quality-check.py` - Enforces deterministic quality gates and optional AI review.
- `archive-items.py` - Archives processed items to `~/park-io/library/profiles/<id>/items/`.
- `finalize-local.py` - Saves final Markdown and HTML to `~/park-io/inbox/sent/`.
- `send-artifacts.py` / `push-telegram.py` - Sends Telegram text/HTML/PNG when sending is enabled.

**Maintenance:**
- `generate-status.py` - Writes maintainer-facing `~/park-io/status.html`.
- `channel-health.py` and `source-health.py` - Compute source/channel health from fetch logs, state, and feed freshness.
- `check-pipeline-health.py` - launchd health check and local/Telegram alert surface.
- `refresh-twitter-auth.py` - Twitter auth refresh helper.
- `onboard-source.py`, `onboard-baseline.py`, and `backfill-claude-blog-library.py` - Source/profile maintenance tools.

## Data/File Formats

**Source Configuration:**
- `~/park-io/sources.md` - Single source of truth for active source rows; parsed by `lib.load_sources()` from the first Markdown table.
- `digest_config.py` - In-repo policy constants for source roles, authority, groups, section membership, and bad LLM markers.

**Raw Queue:**
- `~/park-io/inbox/unprocessed/<YY-MM-DD-profile_id>.md` - Profile-day Markdown queue written by `lib.write_source_output()`.
- Queue files use frontmatter rendered by `lib.render_frontmatter()` and item sections parsed by `lib.parse_md_items()`.
- `state.json` - Repo-local fetch and dedupe state used by source fetchers.

**Processed Output:**
- `~/park-io/inbox/processed/<batch>/000-<label>.md` - Digest Markdown generated by `summarize.py`.
- `~/park-io/inbox/processed/<batch>/000-<label>.html` - Reader HTML panel generated by `summarize.py`.
- `~/park-io/inbox/processed/<batch>/000-<label>.png` - Long image rendered from HTML by `html-to-long-image.py`.
- `~/park-io/inbox/sent/<YY-MM-DD>.md` and `.html` - Local final daily digest copied by `finalize-local.py`.

**State/Health:**
- `media-summaries.json` and `media-queue.json` - Media transcript/summarization status for `fetch-media-transcripts.py`.
- `x-saved-items.json`, `x-saved-state.json`, and `x-saved-source-candidates.json` - X saved/bookmark tracking in `fetch-twitter-saved.py`.
- `tg-push-state.json` - Telegram URL/content delivery dedupe in `push-telegram.py`.
- `~/park-io/inbox/health-alerts.md` - Local health alert log written by `lib.write_health_alert()`.
- `logs/*.log` - Fetch, push, health, launchd stdout/stderr, and stage logs.

## Configuration

**Environment:**
- LLM: `PARKIO_LLM_PROVIDER`, `PARKIO_LLM_FALLBACK_PROVIDER`, `PARKIO_DEEPSEEK_KEY`, `PARKIO_DEEPSEEK_MODEL`, `PARKIO_DEEPSEEK_ENDPOINT`, `PARKIO_DEEPSEEK_THINKING`, `PARKIO_DEEPSEEK_MAX_OUTPUT`, `PARKIO_CLIPROXY_KEY`, `PARKIO_CLIPROXY_ENDPOINT`, `PARKIO_CLIPROXY_MODEL`.
- Runtime/batch: `PARKIO_PYTHON`, `PARKIO_BATCH_ID`, `PARKIO_BATCH_DIR`, `PARKIO_SKIP_SEND`, `PARKIO_FORCE_PUSH`, `PARKIO_SKIP_QUALITY`, `PARKIO_STRICT_AI_QUALITY`.
- Fetch/media: `PARKIO_REFETCH_TODAY`, `PARKIO_WECHAT_IMPORT_SEEDS`, `PARKIO_WECHAT_EXPORT_DIR`, `PARKIO_X_BOOKMARK_MAX`, `PARKIO_X_LIKE_MAX`, `PARKIO_X_SELF_HANDLE`, `PARKIO_X_BACKFILL_RECENT_BOOKMARKS`, `PARKIO_YOUTUBE_MIN_SECONDS`, `PARKIO_YTDLP_COOKIES_FILE`, `PARKIO_YTDLP_COOKIE_SOURCES`, `PARKIO_TRANSCRIPT_MIN_CHARS`, `PARKIO_MEDIA_MAX_ASR_SECONDS`, `PARKIO_MLX_WHISPER_MODEL`, `PARKIO_MEDIA_RETRY_DAYS`, `PARKIO_SCREENSHOT_WIDTH`.
- Secrets are loaded by `lib._load_secret()` from env first, then `~/park-io/secrets/<file>`. Do not store credential values in tracked files.

**Build:**
- No package build config detected.
- Operational config lives in scripts, `AGENTS.md`, `GOTCHAS.md`, `digest_config.py`, `~/park-io/sources.md`, and launchd plists under `/Users/wendy/Library/LaunchAgents/`.

## Platform Requirements

**Development:**
- macOS with Python 3.11+, Bash, Google Chrome, Homebrew-style tools under `/opt/homebrew/bin`, and access to `~/park-io`.
- Optional but operationally important: `yt-dlp` or Python `yt_dlp`, `ffprobe`, `mlx_whisper`, `websockets`, Pillow, and `content-toolkit`.
- Run regression tests with `for t in tests/test_*.py; do python3 "$t"; done` before changing core pipeline files named in `AGENTS.md`.

**Production:**
- Local launchd on Wendy's Mac. Fetch runs every 14,400 seconds via `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-fetch.plist`; digest runs daily at 08:30 via `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-push.plist`; health check runs daily at 09:30 via `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-health.plist`.
- Data storage and product output are local filesystem paths under `~/park-io`, not a hosted backend.

---

*Stack analysis: 2026-06-04*
