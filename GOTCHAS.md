# Park-IO Daily — Regression Gotchas

Hard-won invariants. Before editing `summarize.py`, `aggregation/digest/ai_process.py`,
`open-batch.py`, `processing_filter.py`, `fetch-twitter.py`, `push-telegram.py`,
or `fetch-wechat.py`, check the change against this list.

**Enforcement legend**
- 🟢 **gate** — structural failure blocks the push deterministically
- 🧪 **test** — locked by a `tests/` regression test
- 🔵 **code** — implemented in the pipeline (verified), no explicit lock yet
- 🟡 **partial** — partially handled; remaining work noted
- ⚪ **manual** — discipline / convention, not automated

Run all tests: `for t in tests/test_*.py; do python3 "$t"; done`

---

| # | Invariant | Status | Where |
|---|-----------|--------|-------|
| 1 | All content judgment is AI-first: merge, score, classify, brief_universe/deep_candidates selection, and final writing happen in `ai_process.py`, not script thresholds | 🧪🔵 | `aggregation/digest/ai_process.py` · `prompts/ai-process/` · `tests/test_ai_process.py` |
| 2 | No production fallback to `score.py`, `score_items.py`, `quality-check.py`, `quality.py`, or deterministic renderer | 🧪🔵 | `push-digest.sh` · `summarize.main()` · `tests/test_ai_process.py` |
| 3 | Podcast / YouTube / 抖音 must have usable transcript/summary before AI processing can make reader-facing decisions | 🧪🔵 | `stages/to_md/run.py` + media enrichment · `tests/test_ai_process.py` |
| 4 | No ops/meta in consumer body (公众号/作者/WeChat ID/internal source fields) | 🧪 | prompt contract + `digest_text.strip_source_meta()` · `test_cleaning.py` |
| 5 | Final body must be Chinese, never raw English | 🧪 | final writing prompt + structure checks · `test_chinese_fallback.py` |
| 6 | No stale-title pollution; titles from current content | 🧪 | `event_title()` (map removed) + `display_title()` · `test_titles.py` |
| 7 | Dedup only within today's batch | 🔵 | `read_today_items()` within-batch dedupe; `state.json` status-only |
| 8 | X quote/retweet: prefer the quoted long content | 🔵 | `fetch-twitter.nested_tweets()` / `tweet_text()` |
| 9 | X thread replies merge into one event, not split | 🧪 | `fetch-twitter` captures `conversation_id`; `build_events` merges same-thread · `test_thread_merge.py` (future fetches only) |
| 10 | Cross-source merge is an AI event-merge decision, not keyword cascades or deterministic grouping | 🧪🔵 | `prompts/ai-process/02-event-merge.md` · `tests/test_ai_process.py` |
| 11 | Product structure fixed: default `快讯` artifact with `底层工具/工作流/内容`; optional separate `深读` artifact; old `今日判断` and `可行动机会` must not reappear | 🧪🔵 | `prompts/ai-process/04-brief-writing.md` · `prompts/ai-process/05-deep-writing.md` · `validate_brief_markdown()` |
| 12 | Empty sections hidden on consumer page | 🔵 | `render_html_*_card()` return "" on empty |
| 13 | Markdown is the single content source for HTML / PNG | 🔵 | `ai_process.run_ai_process()` returns Markdown; `render_html_from_markdown()` derives HTML; PNG from HTML |
| 14 | PNG trims trailing whitespace | 🔵 | `html-to-long-image.trim_bottom_whitespace()` |
| 15 | `sent/` keeps the local final artifact family `YY-MM-DD.{md,html,png}` and optional `deep-YY-MM-DD.{md,html,png}` | 🧪🔵 | `finalize-local.py` · `tests/test_finalize_local.py` |
| 16 | Stable file naming `YY-MM-DD`, no 早/晚/hhmm | ⚪ | convention |
| 17 | Manual links: single `manual-links.md` (Pending/Imported/Failed) | ⚪ | convention · `fetch-manual-links.py` |
| 18 | References: `references/YYYY-MM-DD__platform__author__title__hash.md`; profile/source baselines live under `.system/source-profiles` | ⚪ | convention |
| 19 | Workflow diagram is a closed 5-stage system | 🔵 | `validate-workflow.py`. **Note:** v13 contract = fetch → to_md → coarse_filter → ai_process → archive, with dual product outputs |
| 20 | Structural AI output failure is the only production gate: invalid JSON or missing required final sections must stop the run and write `ai/error.json` | 🟢🧪 | `aggregation/digest/ai_process.py` · `tests/test_ai_process.py` |
| 21 | AI endpoint/JSON failure is not silent and never creates a fake successful newsletter | 🟢🔵 | `ai/error.json` + `ai/raw-response.md` |
| 22 | Source health stays in status/alerts, not inside final newsletter body | 🧪🔵 | `summarize.main()` · `generate-status.py` |
| 23 | WeChat auto-fetch is fragile; manual links reliable | 🟡 | manual path reliable; RSS bridge health must surface in digest/status |
| 24 | Empty-content X items don't enter consumer body | 🧪 | `x_item_has_content()` skips link-only single-X events · `test_empty_x.py` |
| 25 | Source health must not mention disabled sources | 🟡 | `digest_config.py` / `sources.md`; e.g. disabled `海外独角兽` must not leak into health |
| 26 | Dependency health should hide personal account names in consumer output | 🔵 | `run_report.py`; show "WeWe 读书账号失效", not the login account name |
| 27 | Automatic and manual WeChat items must pass the same AI selection path before inclusion | 🧪🔵 | `aggregation/digest/ai_process.py` · `tests/test_ai_process.py` |
| 28 | Reader surface has default 快讯 plus optional 深读; deep_candidates must be a traceable subset of brief_universe and preserve article-level substance | 🟢🧪 | `prompts/ai-process/03-selection.md` · `prompts/ai-process/05-deep-writing.md` · `validate_selection_references()` |
| 29 | Daily Newsletter umbrella ships three products: 快讯, 深读, 产品雷达; `daily-YY-MM-DD.*` links them without rewriting their bodies | 🧪🔵 | `build-daily-bundle.py` · `daily_bundle.py` · `tests/test_daily_bundle.py` |
| 30 | Recoverable source auth is non-blocking by default; WeChat / YouTube problems are health warnings, not reasons to skip daily artifact generation | 🧪🔵 | `push-digest.sh` · `tests/test_daily_routine_contract.py` |
| 31 | Unprocessed raw is not the library boundary: obvious low-value social noise is rejected before `processed/`; selected AI brief_universe/deep_candidates items archive, discard does not | 🧪🔵 | `processing_filter.py` · `open-batch.py` · `aggregation/digest/archive.py` |
| 32 | The five pipeline stages have physical folders; root scripts are compatibility wrappers only | 🧪🔵 | `stages/*/run.py` · `tests/test_ai_process.py` |

---

## Open items (tracked)

- **#23** — Surface WeChat auto-feed success/failure in the status dashboard
  (manual-links path is already reliable). The only remaining 🟡.
- **#10 (cross-source semantic merge)** — the keyword cascade is kept because it
  currently produces net-positive merges; a semantic-similarity replacement is a
  future improvement, not a present bug.
- **#1 / #2 AI-first boundary** — older notes said "every URL enters scoring".
  That is now legacy. Current production rule: scripts do only coarse garbage
  removal; AI decides all merge/scoring/classification/selection.
- **#25 disabled-source health leak** — channel-health and digest health must be
  derived from active sources only, not stale state/log rows.
- **#27 WeChat selection mismatch** — if 公众号 says "获取 N → 收录 0" while
  items exist, verify the raw/to-md/coarse-filter boundary first, then inspect
  `processed/<YY-MM-DD>/ai/03-selection.json`.
- **#28 Daily Inbox dual-product contract** — every useful signal belongs in
  `brief_universe` and the default 快讯 artifact. `deep_candidates` is only a
  subset of that universe, reserved for official explainers, long-form cases,
  platform-mechanism analysis, media summaries with real transcripts, and
  curated long articles that can justify 10-30 minutes of reader attention.
- **#29 Daily Newsletter umbrella contract** — the daily reader routine now
  ships three products: 快讯, 深读, 产品雷达. Product Radar stays outside the
  快讯/深读 AI selection universe and is linked by `daily-YY-MM-DD.*`. Product
  Radar should render one Top 5 build-choices list, not separate Product Hunt /
  HN / TrustMRR sections; do not merge those rows into the main signal selection.
- **#30 Recoverable source auth is non-blocking** — WeChat / YouTube cookie or
  QR/login problems must be surfaced in status/run-report/daily bundle, but the
  scheduled daily artifact still generates from available sources by default.
  Use `PARKIO_PREFLIGHT_BLOCK=1` only for an explicit debugging run.

---

## External Solution Evaluation Gotchas

These are evaluated libraries / approaches. Do not re-introduce them blindly as
"fixes" without checking the specific blocker they solve.

| Candidate | Problem considered | Verdict | Why |
|---|---|---|---|
| [`yizhiyanhua-ai/youtube-ai-digest`](https://github.com/yizhiyanhua-ai/youtube-ai-digest) | YouTube digest / subtitles | 🟡 reference only | Good shape for channel list -> transcript -> Chinese digest, but still based on `yt-dlp`; it does not bypass YouTube login/bot failures beyond normal subtitle fetching. |
| [`ComposioHQ/awesome-claude-skills/video-downloader`](https://github.com/ComposioHQ/awesome-claude-skills/blob/master/video-downloader/SKILL.md) | YouTube download | ⚪ not a fix | Thin downloader wrapper around `yt-dlp`. Useful as UX reference, not a root-cause fix for `Sign in to confirm you're not a bot`. |
| [`op7418/Youtube-clipper-skill`](https://github.com/op7418/Youtube-clipper-skill) | YouTube download/subtitle/clip workflow | 🟡 reference only | Good for environment checks, ffmpeg, subtitle parsing, and chaptering. Still depends on successful YouTube download/subtitle acquisition. |
| [`D4Vinci/Scrapling`](https://github.com/D4Vinci/Scrapling) | Generic anti-bot scraping | ⚪ not for current YouTube/WeChat root cause | Useful for ordinary web pages and selector drift. Does not solve YouTube media acquisition or WeChat subscription/RSS state by itself. |
| [`NanmiCoder/MediaCrawler`](https://github.com/NanmiCoder/MediaCrawler) | Douyin / XHS / self-media crawling | 🟡 possible Douyin/XHS reference | Strong for Chinese social platforms with Playwright/CDP login-state patterns. It does not cover YouTube transcription or WeChat public-account RSS as the main product path. |
| [`jackwener/opencli`](https://github.com/jackwener/opencli) | Logged-in browser automation | 🟡 useful support layer | Can help operate real Chrome, inspect pages, click QR/login flows, and build site commands. It is not the ingestion backend; use for health recovery / QR / manual auth workflows. |
| [`Panniantong/Agent-Reach`](https://github.com/Panniantong/Agent-Reach) | Agent internet toolkit | 🟡 tool-selection reference | Useful map of upstream tools: YouTube still uses `yt-dlp`; WeChat uses search/read style tools rather than a durable subscription feed. Good diagnostic scaffold, not a drop-in replacement. |
| [`rachelos/we-mp-rss`](https://github.com/rachelos/we-mp-rss) | WeChat public-account RSS | 🟢 best replacement candidate | Purpose-built for WeChat public account RSS, supports scheduled updates, auth expiry reminders, notifications, RSS output, and full-content options. Still requires auth/session maintenance; not "set and forget". |

### YouTube root-cause rule

If YouTube fails with `Sign in to confirm you're not a bot`, do not spend time
on Whisper tuning. The transcript model is not reached. The failure is in media
acquisition/cookies. Fix order:

1. Update `yt-dlp`.
2. Verify `youtube-cookies.txt` and `--cookies-from-browser chrome` with one
   failing URL.
3. If both fail, treat it as authentication / bot challenge and surface it in
   health; do not hide it as `no_transcript`.
4. Once audio is downloaded, use the existing MLX Whisper path. For long videos,
   split with ffmpeg and concatenate transcripts; do not skip solely because a
   video is long unless it exceeds the configured hard cap.

### WeChat root-cause rule

There is no truly stable public official WeChat RSS. Any automated feed depends
on a bridge/session that can expire. Correct strategy:

1. Keep manual links as the reliable fallback.
2. Track `seen_urls` / identities so bridge recovery backfills every unseen
   article since last success, not only "today".
3. Surface auth expiry in the daily digest and status page.
4. Prefer a purpose-built WeChat RSS bridge (`we-mp-rss` or current WeWe bridge)
   over generic scraping frameworks.
5. If migrating bridge, test delta recovery and auth expiry alerts before
   replacing the production feed.

## How this maps to the workflow contract

`inbox-workflow.yaml` should converge on the 5-stage contract:
`fetch -> to_md -> coarse_filter -> ai_process -> archive`. Nodes are typed
`script | ai | local_model | human | sink`. Routing and persistence are script
work; editorial judgment is AI work. This file lists the invariants those
stages must preserve.
