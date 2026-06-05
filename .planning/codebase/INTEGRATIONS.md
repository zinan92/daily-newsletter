# External Integrations

**Analysis Date:** 2026-06-05

## APIs & External Services

**RSS / Atom / Web Feeds:**
- Generic RSS/Atom sources - `ingestion/rss/run.py` reads active `platform=rss` rows from `~/park-io/sources.md` through `lib.load_sources()`, fetches with `urllib.request`, and parses RSS/Atom XML with `xml.etree.ElementTree`.
  - SDK/Client: Python standard library `urllib.request` and `xml.etree.ElementTree`.
  - Auth: None detected for generic RSS.
- YouTube channel feeds and pages - `ingestion/rss/run.py` supports YouTube RSS plus HTML page fallback for official channels; it enriches titles/durations through `yt-dlp`.
  - SDK/Client: `yt-dlp`, `python -m yt_dlp`, or `/opt/homebrew/bin/yt-dlp`.
  - Auth: Optional cookies are handled in `enrichment/media/run.py` through `PARKIO_YTDLP_COOKIES_FILE` and `PARKIO_YTDLP_COOKIE_SOURCES`.

**Twitter / X:**
- Tracked X accounts - `ingestion/x/timeline.py` calls `/Users/wendy/.local/bin/twitter user-posts <handle> --max 20 --json` for active `platform=twitter` sources.
  - SDK/Client: local `twitter` CLI at `/Users/wendy/.local/bin/twitter`.
  - Auth: `twitter-auth.env` at `/Users/wendy/work/input-to-park/twitter-auth.env`; the file is loaded but must not be quoted or committed with values.
- X Articles - `ingestion/x/timeline.py` and `ingestion/x/saved.py` call `/Users/wendy/.local/bin/twitter article <tweet_id> --json` to attach long-form article content.
  - SDK/Client: local `twitter` CLI.
  - Auth: `TWITTER_AUTH_TOKEN`, `TWITTER_CT0`, `TWITTER_BROWSER`, and `TWITTER_CHROME_PROFILE` loaded from `twitter-auth.env`.
- User bookmarks/likes - `ingestion/x/saved.py` calls `twitter bookmarks -n <N> --json` and `twitter likes <self_handle> -n <N> --json`.
  - SDK/Client: local `twitter` CLI.
  - Auth: `twitter-auth.env`; `PARKIO_X_SELF_HANDLE`, `PARKIO_X_BOOKMARK_MAX`, `PARKIO_X_LIKE_MAX`, and `PARKIO_X_BACKFILL_RECENT_BOOKMARKS` configure scope.

**WeChat / WeWe RSS / Manual Links:**
- Seeded WeChat articles - `ingestion/manual_links/wechat_seed.py` fetches `mp.weixin.qq.com/s/...` seed URLs from active `platform=wechat` rows and extracts article text with `html.parser.HTMLParser`.
  - SDK/Client: Python standard library `urllib.request` and `html.parser`.
  - Auth: None detected for direct seed article fetching.
- WeChat RSS/JSON bridge - `ingestion/wechat_rss/run.py` reads active `platform=wechat-rss` rows or `platform=wechat` rows with `notes` containing `rss_url <url>`, then parses RSS XML or JSON feeds.
  - SDK/Client: Python standard library `urllib.request`, `xml.etree.ElementTree`, and `json`.
  - Auth: No repo-side credential; README documents `wewe-rss` on `localhost:4000` as the bridge, with WeChat/WeRead login expiry handled outside this repo.
- Manual WeChat links - `ingestion/manual_links/run.py` imports pending `https://mp.weixin.qq.com/s/...` URLs from `~/park-io/inbox/manual-links.md`, reuses `ingestion/manual_links/wechat_seed.py`, and writes imported/failed records back to that Markdown file.
  - SDK/Client: local file plus `ingestion/manual_links/wechat_seed.py`.
  - Auth: None detected.
- WeChat exporter directory - `ingestion/wechat_rss/exporter.py` imports JSON/Markdown/HTML exports from `PARKIO_WECHAT_EXPORT_DIR`, defaulting to `~/park-io/outbox/wechat-exporter`.
  - SDK/Client: local filesystem parser.
  - Auth: Not applicable in repo.

**YouTube / Podcast / Media Transcription:**
- YouTube subtitles and audio - `enrichment/media/run.py` uses `yt-dlp` to fetch subtitles first, then downloads audio when subtitles are missing or too short.
  - SDK/Client: `yt-dlp` CLI/Python module and optional browser/cookie-file auth.
  - Auth: `PARKIO_YTDLP_COOKIES_FILE` defaulting to `~/park-io/secrets/youtube-cookies.txt`; `PARKIO_YTDLP_COOKIE_SOURCES` defaulting to `chrome,chrome:Default`.
- Local ASR - `enrichment/media/run.py` calls `mlx_whisper.transcribe()` through a subprocess using `PARKIO_MLX_WHISPER_MODEL`, default `mlx-community/whisper-small-mlx`.
  - SDK/Client: `mlx_whisper`.
  - Auth: None.
- Media duration checks - `enrichment/media/run.py` uses `ffprobe` to skip overlong media based on `PARKIO_MEDIA_MAX_ASR_SECONDS`.
  - SDK/Client: `/opt/homebrew/bin/ffprobe` or PATH `ffprobe`.
  - Auth: None.

**Douyin:**
- Douyin profile monitor - `ingestion/douyin/run.py` imports `content_downloader.adapters.douyin.api_client.DouyinAPIClient` from `~/content-toolkit/capabilities/download` and fetches user posts by `sec_uid`.
  - SDK/Client: local `content-toolkit` Python package, `DouyinAPIClient`.
  - Auth: cookie JSON at `~/park-io/secrets/content-ops/douyin-cookies.json`; existence only, do not read contents.
- Douyin video transcription - `enrichment/media/run.py` imports `content_downloader.adapters.douyin.adapter.DouyinAdapter` from the same `content-toolkit` directory, downloads a video temporarily, then transcribes through MLX Whisper.
  - SDK/Client: `DouyinAdapter`, `mlx_whisper`, `ffprobe`.
  - Auth: `~/park-io/secrets/content-ops/douyin-cookies.json`.

**Official / Scraped Web Sources:**
- Claude blog backfill and scrape candidates - `backfill-claude-blog-library.py` uses helpers from `ingestion/web_scrape/run.py` to fetch `https://claude.com/blog` candidates and persist library articles.
  - SDK/Client: local scraper module plus Python standard library.
  - Auth: None detected.
- General scrape stage - `fetch.py` runs `ingestion/web_scrape/run.py` as one fetch stage; scrape outputs feed the same Markdown queue through `lib.write_source_output()`.
  - SDK/Client: local script.
  - Auth: None detected from inspected references.

**LLM Providers:**
- DeepSeek - Primary LLM provider in `lib.py`, using OpenAI-compatible `/v1/chat/completions`.
  - SDK/Client: Python `urllib.request`; no OpenAI SDK dependency detected.
  - Auth: `PARKIO_DEEPSEEK_KEY` or `~/park-io/secrets/deepseek-key`.
  - Models/config: `PARKIO_DEEPSEEK_MODEL`, `PARKIO_DEEPSEEK_ENDPOINT`, `PARKIO_DEEPSEEK_THINKING`, and `PARKIO_DEEPSEEK_MAX_OUTPUT`.
- CLIProxyAPI / Sonnet - Anthropic-compatible fallback provider in `lib.py`.
  - SDK/Client: Python `urllib.request` to `PARKIO_CLIPROXY_ENDPOINT`, default `http://localhost:8317/v1/messages`.
  - Auth: `PARKIO_CLIPROXY_KEY` or `~/park-io/secrets/cliproxy-key`.
  - Model/config: `PARKIO_CLIPROXY_MODEL`, default `claude-sonnet-4-5-20250929`.
- Failover policy - `lib.llm_call()` retries transient DeepSeek failures and fails over to the fallback provider only for retryable/unavailable conditions; non-retryable config/request errors fail fast.

**Telegram:**
- Digest delivery - `push-telegram.py` uses Telegram Bot API endpoints `sendMessage` and `sendDocument` to send text chunks, HTML, and PNG artifacts.
  - SDK/Client: Python standard library `urllib.request`, multipart body constructed manually in `push-telegram.py`.
  - Auth: `PARKIO_TELEGRAM_BOT_TOKEN`, `PARKIO_TELEGRAM_CHAT_ID`, or local secret files `~/park-io/secrets/telegram-bot-token` and `~/park-io/secrets/telegram-chat-id`.
- Health alerts - `lib.send_telegram()` can send owner alert text through Telegram Bot API; `lib.write_health_alert()` also writes local alerts to `~/park-io/inbox/health-alerts.md`.
  - SDK/Client: Python standard library `urllib.request`.
  - Auth: same Telegram env/local secret names.

**Browser / HTML / PNG Artifacts:**
- HTML digest artifacts - `aggregation/digest/summarize.py` writes processed Markdown and HTML through paths from `lib.batch_artifact_paths()`.
  - SDK/Client: local renderer code.
  - Auth: None.
- Long PNG rendering - `aggregation/digest/html_to_long_image.py` opens generated HTML through `file://`, launches Google Chrome headless, captures a full-page PNG through Chrome DevTools or CLI screenshot fallback, and trims bottom whitespace with Pillow when available.
  - SDK/Client: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, optional `websockets`, optional `PIL.Image`.
  - Auth: None.
- Status page - `generate-status.py` writes maintainer status HTML under `~/park-io/status.html` and reads sent digests, source health, manual links state, and channel health.
  - SDK/Client: local filesystem HTML generation.
  - Auth: None.

## Data Storage

**Databases:**
- No server database detected. Durable state is local files.
- Source truth: `~/park-io/sources.md`, parsed by `lib.load_sources()`.
- Fetch/dedupe state: `state.json`, `x-saved-items.json`, `x-saved-state.json`, `x-saved-source-candidates.json`, `media-summaries.json`, `media-queue.json`, and `tg-push-state.json`.
- Long-term library: `~/park-io/library/profiles/<profile_id>/items/` and `~/park-io/library/独立链接/`.

**File Storage:**
- Local filesystem only.
- Raw queue: `~/park-io/inbox/unprocessed/`.
- Batch processing: `~/park-io/inbox/processed/<batch>/`.
- Final local digest: `~/park-io/inbox/sent/`.
- Logs: `/Users/wendy/work/input-to-park/logs/`.
- Manual collection inbox: `~/park-io/inbox/manual-links.md`.

**Caching:**
- Local JSON caches only: `media-summaries.json`, `media-queue.json`, `x-saved-items.json`, `x-saved-state.json`, `x-saved-source-candidates.json`, `tg-push-state.json`, and selected state blocks inside `state.json`.
- No Redis/Memcached/external cache detected.

## Authentication & Identity

**Auth Provider:**
- Custom/local secret loading. `lib._load_secret()` reads env first, then `~/park-io/secrets/<filename>`.
- X identity is cookie/session based through `twitter-auth.env`; scripts load only the allowed variable names and pass them to the local twitter CLI environment.
- YouTube auth is cookie based through `PARKIO_YTDLP_COOKIES_FILE` or browser cookie extraction configured by `PARKIO_YTDLP_COOKIE_SOURCES`.
- Douyin auth is cookie JSON based through `~/park-io/secrets/content-ops/douyin-cookies.json`.
- Telegram auth is bot token/chat id through env or `~/park-io/secrets/telegram-*`.
- LLM auth is API-key based for DeepSeek and CLIProxy.

## Monitoring & Observability

**Error Tracking:**
- No SaaS error tracker detected.
- Stage errors are written to `logs/*.log`, source-specific `state.json` entries, source health records, and status/health artifacts.
- `check-pipeline-health.py` detects stale sent digest, scoring failures, empty media section, and WeChat bridge failures; it writes local health alerts and can alert the owner.

**Logs:**
- `fetch-all.sh` writes to `/Users/wendy/work/input-to-park/logs/fetch-all.log` and uses `/Users/wendy/work/input-to-park/logs/fetch.lock`.
- `push-digest.sh` writes to `/Users/wendy/work/input-to-park/logs/push-digest.log`.
- launchd stdout/stderr paths are configured in `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-fetch.plist`, `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-push.plist`, and `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-health.plist`.
- `channel-health.py`, `source-health.py`, and `generate-status.py` provide maintainer-facing health views rather than external telemetry.

## CI/CD & Deployment

**Hosting:**
- Local Mac launchd. No cloud hosting or server deployment detected for this repo.
- Runtime plists:
  - `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-fetch.plist` runs `/Users/wendy/work/input-to-park/fetch-all.sh` every 14,400 seconds.
  - `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-push.plist` runs `/Users/wendy/work/input-to-park/push-digest.sh` daily at 08:30.
  - `/Users/wendy/Library/LaunchAgents/com.wendy.parkio-health.plist` runs `python3 check-pipeline-health.py` daily at 09:30.

**CI Pipeline:**
- Not detected.
- Regression tests are local script tests under `tests/test_*.py` and are documented in `AGENTS.md` and `README.md`.

## Environment Configuration

**Required env vars / local secret files:**
- DeepSeek: `PARKIO_DEEPSEEK_KEY` or `~/park-io/secrets/deepseek-key`.
- CLIProxy fallback: `PARKIO_CLIPROXY_KEY` or `~/park-io/secrets/cliproxy-key`; endpoint defaults to `http://localhost:8317/v1/messages`.
- Telegram: `PARKIO_TELEGRAM_BOT_TOKEN`, `PARKIO_TELEGRAM_CHAT_ID`, or `~/park-io/secrets/telegram-bot-token` and `~/park-io/secrets/telegram-chat-id`.
- X: `twitter-auth.env` at `/Users/wendy/work/input-to-park/twitter-auth.env`; existence only, do not read contents.
- YouTube: `PARKIO_YTDLP_COOKIES_FILE` or default `~/park-io/secrets/youtube-cookies.txt`.
- Douyin: `~/park-io/secrets/content-ops/douyin-cookies.json`.
- Runtime overrides: `PARKIO_PYTHON`, `PARKIO_BATCH_ID`, `PARKIO_BATCH_DIR`, `PARKIO_SKIP_SEND`, `PARKIO_FORCE_PUSH`, `PARKIO_SKIP_QUALITY`, and `PARKIO_STRICT_AI_QUALITY`.

**Secrets location:**
- Repo-local secret-like file detected by path reference: `/Users/wendy/work/input-to-park/twitter-auth.env`; do not read or quote its contents.
- Main local secret directory: `~/park-io/secrets/`, referenced by `lib._load_secret()`, `ingestion/douyin/run.py`, and `enrichment/media/run.py`.
- YouTube cookies default: `~/park-io/secrets/youtube-cookies.txt`.
- Douyin cookies default: `~/park-io/secrets/content-ops/douyin-cookies.json`.

## Webhooks & Callbacks

**Incoming:**
- None detected. This repo exposes no HTTP API and receives no webhook callbacks.
- Input surfaces are file and CLI based: `~/park-io/sources.md`, `~/park-io/inbox/manual-links.md`, source feeds/APIs, and launchd invocations.

**Outgoing:**
- DeepSeek chat completions from `lib.py` to `PARKIO_DEEPSEEK_ENDPOINT`.
- CLIProxy/Sonnet messages from `lib.py` to `PARKIO_CLIPROXY_ENDPOINT`.
- Telegram Bot API calls from `push-telegram.py` and `lib.py`.
- RSS/Atom/Web fetches from `ingestion/rss/run.py`, `ingestion/manual_links/wechat_seed.py`, `ingestion/wechat_rss/run.py`, `ingestion/web_scrape/run.py`, and related maintenance scripts.
- X CLI subprocess calls from `ingestion/x/timeline.py` and `ingestion/x/saved.py`.
- YouTube/Douyin media downloads from `enrichment/media/run.py`.

---

*Integration audit: 2026-06-05*
