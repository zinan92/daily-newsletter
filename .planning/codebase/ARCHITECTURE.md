<!-- refreshed: 2026-06-04 -->
# Architecture

**Analysis Date:** 2026-06-04

## System Overview

`input-to-park` is a local CLI/cron pipeline, not a web service. The repo contains executable Python scripts and shell orchestrators; runtime data lives primarily under `~/park-io/`.

```text
┌─────────────────────────────────────────────────────────────┐
│                  Cron / Manual Entrypoints                  │
│ `fetch-all.sh`                       `push-digest.sh`       │
└───────────────┬───────────────────────────────┬─────────────┘
                │                               │
                ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│                       Fetch Raw Layer                       │
│ `fetch.py` → `fetch-*.py` → `lib.write_source_output()`     │
│ output: `~/park-io/inbox/unprocessed/*.md`                  │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                       Batch + Scoring                       │
│ `open-batch.py` → `score.py` → `score-items.py`             │
│ output: `~/park-io/inbox/processed/<batch>/`, `scores.json` │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                Event Merge + Summarize + Render             │
│ `build-digest.py` → `summarize.py` → `digest_events.py`     │
│ output: `000-<batch>.md`, `.html`, optional `.png`          │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                 Quality, Archive, Finalize, Send            │
│ `quality-check.py` + `ai-quality-check.py`                  │
│ `archive-items.py` → `finalize-local.py` → `send-artifacts.py` │
│ local sent: `~/park-io/inbox/sent/`; optional Telegram      │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Status + Long-Term Memory                │
│ `generate-status.py`, `source-health.py`, `channel-health.py` │
│ `~/park-io/status.html`, `~/park-io/library/profiles/`      │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Determinism | Responsibility | File |
|-----------|-------------|----------------|------|
| Fetch orchestrator | Deterministic | Runs all fetchers, records source health, regenerates status. | `fetch.py`, `fetch-all.sh` |
| Source fetchers | Mostly deterministic, network-dependent | Fetch RSS, scrape pages, X, saved X, WeChat, WeChat RSS/exporter, Douyin, and media transcripts. | `fetch-rss.py`, `fetch-scrape.py`, `fetch-twitter.py`, `fetch-twitter-saved.py`, `fetch-wechat.py`, `fetch-wechat-rss.py`, `fetch-wechat-exporter.py`, `fetch-douyin.py`, `fetch-media-transcripts.py` |
| Manual link importer | Deterministic + network-dependent | Reads `~/park-io/inbox/manual-links.md`, imports supported WeChat links, moves them from Pending to Imported/Failed, and writes source output. | `fetch-manual-links.py` |
| Shared runtime library | Deterministic infrastructure + stochastic LLM client | Defines repo/data paths, source parsing, item markdown parsing/rendering, state IO, logging, Telegram alerts, and `llm_call()`. | `lib.py` |
| Batch opener | Deterministic | Moves raw pending markdown from `~/park-io/inbox/unprocessed/` into `~/park-io/inbox/processed/<batch>/`, merging duplicate profile-day files. | `open-batch.py` |
| Scoring | AI/stochastic for ordinary items, deterministic bypass for curated classes | Scores ordinary items with an LLM and writes `scores.json`; media, WeChat, Douyin, saved X, and configured always-include classes bypass scoring. | `score.py`, `score-items.py`, `digest_config.py` |
| Event merging | Mixed | Merges X threads deterministically by `conversation_id`; may use LLM semantic clustering for official/code/people same-event grouping; fails open to no semantic merge. | `digest_events.py` |
| Digest builder | Mixed | Reads batch items, applies score/routing policy, creates Chinese markdown, renders HTML from the final markdown, and records push/processed markers. | `build-digest.py`, `summarize.py`, `digest_text.py` |
| Long image renderer | Deterministic rendering, browser/tool dependent | Converts the HTML artifact into a long PNG when HTML exists. | `html-to-long-image.py` |
| Deterministic quality gate | Deterministic | Blocks push/final pipeline failures for missing artifacts, bad AI phrases, metadata leakage, raw English prose, MD/HTML divergence, duplicate headings, duplicate push URLs, and local file URL leaks. | `check-quality.py`, `quality-check.py` |
| AI quality check | AI/stochastic, non-blocking by default | Performs read-only product QC on final Markdown/HTML and returns structured pass/fail JSON; blocks only when `PARKIO_STRICT_AI_QUALITY=1`. | `ai-quality-check.py` |
| Local finalizer | Deterministic | Copies processed Markdown/HTML into `~/park-io/inbox/sent/<label>.md|html` independent of Telegram. | `finalize-local.py` |
| Telegram sender | Deterministic IO + network-dependent | Optionally sends compact digest text, HTML, and PNG; dedupes by hidden URL markers and `tg-push-state.json`. | `send-artifacts.py`, `push-telegram.py` |
| Archive/profile library | Deterministic | Archives processed source items into `~/park-io/library/profiles/<profile_id>/items/` or `~/park-io/library/独立链接/`, and maintains `profile.md` baselines. | `archive-items.py` |
| Status/dashboard | Deterministic probes + network-dependent checks | Builds owner dashboard and source health views from logs, current batch, state, manual links, media queue, sent digests, and library stats. | `generate-status.py`, `source-health.py`, `channel-health.py` |

## Pattern Overview

**Overall:** File-first ETL pipeline with deterministic routing and localized AI nodes.

**Key Characteristics:**
- Use file artifacts as contracts: raw source files, batch directories, markdown/html/png output, JSON state, and profile library files.
- Keep routing deterministic: source name/platform/category/profile maps decide section placement; AI does not choose the route.
- Use AI inside bounded nodes: item scoring, semantic same-event clustering, headline/paragraph rewrites, release-note value bullets, and AI QC.
- Fail visible: fetch failures are logged and surfaced through `source-health.json`, `source-health.md`, `channel-health.py`, digest channel banners, and `status.html`.
- Preserve local ownership: secrets are loaded from env or `~/park-io/secrets/` by `lib._load_secret()` and `push-telegram.py`; do not put secret values in repo files.

## Layers

**Entrypoint Layer:**
- Purpose: Cron/manual control surfaces.
- Location: `fetch-all.sh`, `push-digest.sh`
- Contains: shell orchestration, lock handling, stage sequencing, environment setup.
- Depends on: Python 3.11+, repo scripts, `logs/fetch.lock`.
- Used by: launchd/cron/manual operator.

**Fetch Raw Layer:**
- Purpose: Gather raw content into normalized markdown queue files.
- Location: `fetch.py`, `fetch-*.py`, `lib.write_source_output()`
- Contains: platform-specific fetch logic, source state updates, raw markdown rendering.
- Depends on: `~/park-io/sources.md`, `state.json`, platform credentials/cookies, network sources, `~/content-toolkit/capabilities/download` for some media/Douyin paths.
- Used by: `fetch-all.sh`, `open-batch.py`, `source-health.py`, `channel-health.py`.

**Manual Links Layer:**
- Purpose: Human-supplied one-off links enter the same source-output path as fetched sources.
- Location: `fetch-manual-links.py`
- Contains: `~/park-io/inbox/manual-links.md` section management, WeChat URL extraction, import records, failure records, independent-link archive writes.
- Depends on: `fetch-wechat.py`, `lib.load_sources()`, `lib.write_source_output()`.
- Used by: `fetch.py`.

**Batch Layer:**
- Purpose: Freeze currently pending source files into the day's processed batch.
- Location: `open-batch.py`
- Contains: move/merge logic from `~/park-io/inbox/unprocessed/` to `~/park-io/inbox/processed/<batch>/`.
- Depends on: `lib.batch_id()`, `lib.processed_batch_dir()`, frontmatter parsing/rendering.
- Used by: `push-digest.sh`.

**Scoring Layer:**
- Purpose: Attach relevance scores, line-fit, tags, and reasons.
- Location: `score.py`, `score-items.py`
- Contains: `SCORING_PROMPT`, owner context loading from `~/park-io/sources.md`, profile context loading from `~/park-io/library/profiles/*/profile.md`, outage recording to `scoring-health.json`.
- Depends on: `lib.llm_call()`, `digest_config.media_source_names()`, batch/raw markdown parser.
- Used by: `push-digest.sh`, `summarize.py`.

**Routing + Event Layer:**
- Purpose: Convert source items into section-ready events.
- Location: `digest_config.py`, `digest_events.py`, `summarize.py`
- Contains: source-role maps, source groups, bypass rules, path breakdown, deterministic thread merge, optional semantic event clustering.
- Depends on: `scores.json`, source metadata, `conversation_id`, `SOURCE_ROLES`, `SOURCE_AUTHORITY`.
- Used by: `summarize.render_panel()`, `generate-status.py`.

**Summarize/Render Layer:**
- Purpose: Produce the reader-facing Chinese daily digest.
- Location: `build-digest.py`, `summarize.py`, `digest_text.py`, `html-to-long-image.py`
- Contains: markdown rendering, HTML rendering from final markdown, optional PNG generation, hidden push/processed URL markers.
- Depends on: `lib.llm_call()` for value paragraphs/headlines/release-note rewrites, deterministic text sanitizers from `digest_text.py`, health rows from `source_health()`.
- Used by: `quality-check.py`, `finalize-local.py`, `push-telegram.py`.

**Quality Layer:**
- Purpose: Stop bad final artifacts before finalization/send.
- Location: `check-quality.py`, `quality-check.py`, `ai-quality-check.py`
- Contains: deterministic hard gate plus optional AI QC.
- Depends on: `lib.batch_artifact_paths()`, final Markdown/HTML, hidden markers, `lib.llm_call()` for AI QC.
- Used by: `push-digest.sh`, `push-telegram.py`.

**Delivery Layer:**
- Purpose: Persist local sent artifacts and optionally push to Telegram.
- Location: `finalize-local.py`, `send-artifacts.py`, `push-telegram.py`
- Contains: local copy-to-sent, Telegram multipart send, chunking, compact push body extraction, URL dedupe state.
- Depends on: `~/park-io/inbox/sent/`, env/secrets for Telegram, hidden URL markers.
- Used by: `push-digest.sh` when `PARKIO_SKIP_SEND=0`; local finalize always runs.

**Archive + Observability Layer:**
- Purpose: Preserve historical items and show operator status.
- Location: `archive-items.py`, `generate-status.py`, `source-health.py`, `channel-health.py`
- Contains: profile item archive, profile baseline updates, processed cleanup, status HTML generation, source health history, truthful channel health classification from logs.
- Depends on: `~/park-io/library/`, `~/park-io/inbox/sent/`, `logs/*.log`, `state.json`, `source-health.json`, `scoring-health.json`.
- Used by: owner dashboard, digest health sections, future scoring context.

## Data Flow

### Primary Daily Pipeline

1. Fetch scheduler invokes `fetch-all.sh`.
2. `fetch-all.sh` picks Python 3.11+ and runs `fetch.py`; it uses `logs/fetch.lock` to avoid overlapping fetch and appends to `logs/fetch-all.log`.
3. `fetch.py` runs `fetch-manual-links.py`, `fetch-rss.py`, `fetch-twitter.py`, `fetch-twitter-saved.py`, `fetch-scrape.py`, `fetch-wechat.py`, `fetch-wechat-rss.py`, `fetch-wechat-exporter.py`, `fetch-douyin.py`, and `fetch-media-transcripts.py`.
4. Each fetcher reads active rows from `~/park-io/sources.md` through `lib.load_sources()` and writes new items through `lib.write_source_output()` to `~/park-io/inbox/unprocessed/<YY-MM-DD-profile_id>.md`.
5. Each fetcher updates `state.json` through `lib.save_state()` with `last_fetch`, seen IDs/URLs, status, and errors where implemented.
6. `fetch.py` runs `source-health.py --record`, which writes `source-health.json` in the repo and `~/park-io/source-health.md`.
7. `fetch.py` runs `generate-status.py`, which writes the owner dashboard using current health, state, library, sent digest, and dependency signals.
8. Digest scheduler invokes `push-digest.sh`.
9. `push-digest.sh` waits for `logs/fetch.lock` to clear, then runs `open-batch.py`.
10. `open-batch.py` moves all pending raw markdown to `~/park-io/inbox/processed/<batch>/`, preserving dated subdirectories and merging destination collisions.
11. `push-digest.sh` exports `PARKIO_BATCH_ID` and runs `score.py`.
12. `score.py` delegates to `score-items.py`; ordinary items are scored by `lib.llm_call()` and persisted to `scores.json`, while configured curated classes are skipped for deterministic bypass.
13. `score-items.py` writes `scoring-health.json` so outages are visible in status and digest context.
14. `push-digest.sh` runs `build-digest.py`.
15. `build-digest.py` runs `summarize.py`; `summarize.read_today_items()` parses batch markdown, attaches scores, applies bypass/threshold rules, and dedupes within each source file.
16. `summarize.render_panel()` builds section output for health overview, today conclusion, official/code sources, WeChat articles, saved items, X application events, media updates, contact blocks, and hidden processed/push markers.
17. `summarize.py` writes `~/park-io/inbox/processed/<batch>/000-<batch>.md` and renders `000-<batch>.html` from the same final markdown.
18. `build-digest.py` invokes `html-to-long-image.py` to create `000-<batch>.png` when HTML exists; render failure is a warning, not a digest failure.
19. `push-digest.sh` runs `check-quality.py`, which delegates to `quality-check.py`.
20. `quality-check.py` performs deterministic blocking checks and then runs `ai-quality-check.py` unless `PARKIO_SKIP_AI_QUALITY=1`; AI QC is non-blocking unless `PARKIO_STRICT_AI_QUALITY=1`.
21. `push-digest.sh` runs `archive-items.py`, which archives source-item markdown into `~/park-io/library/profiles/<profile_id>/items/` or `~/park-io/library/独立链接/`.
22. `push-digest.sh` runs `finalize-local.py`, which copies the final Markdown/HTML into `~/park-io/inbox/sent/<label>.md|html`.
23. If `PARKIO_SKIP_SEND=0`, `push-digest.sh` runs `send-artifacts.py`, which delegates to `push-telegram.py` with quality skipped because the stage already passed.
24. `push-telegram.py` extracts hidden push/processed URL markers, dedupes against `tg-push-state.json`, sends compact text plus HTML/PNG to Telegram, updates URL state, and moves/removes processed artifacts.
25. `push-digest.sh` runs `generate-status.py` at the end even when Telegram is skipped.

### Manual Links Flow

1. User edits `~/park-io/inbox/manual-links.md` under the `## Pending` section.
2. `fetch.py` runs `fetch-manual-links.py`.
3. `fetch-manual-links.py` extracts supported WeChat article URLs with `WECHAT_URL_RE`; unsupported URLs are preserved in Pending.
4. For each new supported URL, `fetch-manual-links.py` dynamically loads `fetch-wechat.py`, calls `fetch_url()` and `parse_article()`, and determines a source/profile with `source_for_article()`.
5. Known configured accounts are saved through `fetch-wechat.save_article_to_library()`; unknown manual links are saved under `~/park-io/library/独立链接/` by `save_independent_article()`.
6. Imported items are grouped by source and sent into `lib.write_source_output()` so they enter the same raw queue as automated sources.
7. The manual links file is rewritten with remaining Pending lines, recent Imported records, and recent Failed records.
8. `state.json` key `manual-links` stores seen URLs, imported records, failed records, and library paths.

### Scoring And Routing Flow

1. `score-items.py` parses each source markdown file via `lib.parse_frontmatter()` and `lib.parse_md_items()`.
2. Items from platforms/categories/sources in `ALWAYS_INCLUDE_PLATFORMS`, `ALWAYS_INCLUDE_CATEGORIES`, `ALWAYS_INCLUDE_SOURCES`, media source names, and video/WeChat categories bypass scoring.
3. Non-bypassed queued items are batched by `BATCH_SIZE=10` and sent to the LLM with `SCORING_PROMPT`.
4. Valid LLM JSON rows update `scores.json` by URL with `score`, `tags`, `line_fit`, `reason`, and `scored_at`.
5. `summarize.attach_scores()` attaches score metadata; missing scores become `score=0` with a filtering reason.
6. `summarize.bypasses_score()` deterministically keeps official/code/people/media/saved/WeChat/Douyin sources regardless of score.
7. Non-bypassed items require `score >= digest_config.SCORE_THRESHOLD` to enter the kept set.
8. Section routing is deterministic from `digest_config.source_names_for_group()`, `digest_config.SOURCE_ROLES`, platform/category, and helper filters in `summarize.py`.

### Event Merging Flow

1. `summarize.py` builds per-section raw item pools: official/code/people, Twitter application layer, saved X, WeChat, and media.
2. `digest_events.build_events()` groups same-thread X items deterministically when multiple items share a `conversation_id`.
3. `digest_events.event_key()` gives stable unique-by-default keys for manual items, code releases, official blogs, and application-practice sources.
4. `digest_events._semantic_cluster()` may call the LLM for official/code/people candidate items and returns shared event keys only for same-event groups.
5. If semantic clustering is disabled with `PARKIO_SEMANTIC_CLUSTER=0` or fails, it returns `{}` and items remain separate.
6. Events are sorted deterministically by score, source authority, and title.
7. Official events are grouped by company/category through `group_official_events()` and `group_official_events_by_category()`.
8. Application events use high-value Twitter items; saved and WeChat events bypass score and are rendered in their own sections.

### Summarize And Render Flow

1. `summarize.render_panel()` collects source health, path breakdown, kept/filtered items, media summaries, saved events, WeChat events, official events, and application events.
2. Titles and paragraphs use deterministic cleanups first (`digest_text.py`, `clean_reader_text()`, `deterministic_headline()`, `source_headline()`).
3. AI/stochastic calls are used for `event_summary()`, `value_paragraph()`, `saved_value_paragraph()`, `item_headline()`, and `release_value_notes()` when deterministic output is insufficient.
4. LLM failures are recorded through `note_llm_failure()`; fallback deterministic/source text is used where possible.
5. Markdown is the single content source. `render_html_from_markdown()` renders HTML from final markdown and strips hidden markers.
6. Hidden markers `<!-- parkio-processed-items:... -->` and `<!-- parkio-push-items:... -->` are appended by `summarize.render_panel()` for downstream dedupe and delivery.
7. `html-to-long-image.py` creates the PNG from HTML after markdown/html are written.

### Quality Gate Flow

1. `quality-check.py` resolves artifact paths through `lib.batch_artifact_paths()` in batch mode or from `~/park-io/inbox/sent/` otherwise.
2. Missing Markdown/HTML is a deterministic failure.
3. Visible Markdown/HTML are checked against `BAD_PATTERNS` and `METADATA_PATTERNS`.
4. Raw English body prose is detected by `raw_english_body_lines()` and blocks the pipeline.
5. Markdown headings must appear in HTML via `heading_divergence()`.
6. Required sections, event headings, duplicate headings, duplicate push URLs, local file URLs, and size warnings are checked deterministically.
7. `ai-quality-check.py` inspects trimmed visible Markdown/HTML with an LLM and expects strict JSON.
8. AI QC failure is a warning by default; set `PARKIO_STRICT_AI_QUALITY=1` to make it a hard gate.

### Delivery And Archive Flow

1. `archive-items.py` reads processed batch source markdown files, parses items, writes each item to a profile library path, ensures `profile.md`, and removes old processed batches.
2. `finalize-local.py` copies final processed Markdown/HTML to `~/park-io/inbox/sent/` with a temp-file replace.
3. `send-artifacts.py` invokes `push-telegram.py` with `PARKIO_SKIP_QUALITY=1`.
4. `push-telegram.py` optionally re-runs quality when not skipped, extracts push/processed markers, compacts the visible body, and chunks messages under Telegram limits.
5. Telegram credentials are loaded from `PARKIO_TELEGRAM_BOT_TOKEN`, `PARKIO_TELEGRAM_CHAT_ID`, or `~/park-io/secrets/telegram-*`.
6. `push-telegram.py` stores processed and pushed URL state in `tg-push-state.json`.

### Status And Dashboard Flow

1. `source-health.py --record` writes historical fetch success to `source-health.json` and `~/park-io/source-health.md`.
2. `channel-health.py` reads fetch logs and probes WeChat RSS freshness to distinguish `DOWN`, `STALE`, `QUIET`, `NEW`, and `UNKNOWN`.
3. `summarize.source_health()` folds channel health into digest-visible source rows.
4. `generate-status.py` imports `summarize.py`, reads today items, scoring health, manual link state, media queue, sent digests, library profiles, dependency probes, and channel health.
5. `generate-status.py` renders an owner-facing HTML status/dashboard page under `~/park-io/status.html` using deterministic HTML string rendering.

**State Management:**
- Repo state files: `state.json`, `scores.json`, `scoring-health.json`, `source-health.json`, `media-summaries.json`, `media-queue.json`, `x-saved-state.json`, `tg-push-state.json`.
- Runtime content roots: `~/park-io/inbox/unprocessed/`, `~/park-io/inbox/processed/`, `~/park-io/inbox/sent/`, `~/park-io/library/profiles/`, `~/park-io/library/独立链接/`.
- Source configuration: `~/park-io/sources.md` is parsed by `lib.load_sources()` and treated as the active source list.
- Logs: `logs/<component>.log` are the operational truth for channel health and dashboard status.

## Deterministic vs AI/Stochastic Map

**Deterministic Components:**
- Source/profile/path routing: `digest_config.py`, `summarize.bypasses_score()`, `summarize.compute_path_breakdown()`.
- Raw queue rendering and parsing: `lib.write_source_output()`, `lib.parse_md_items()`, `lib.render_frontmatter()`.
- Batch opening and file movement: `open-batch.py`.
- X thread merging by `conversation_id`: `digest_events.build_events()`.
- Score bypass classes: `score-items.py`, `summarize.bypasses_score()`.
- Markdown-to-HTML rendering from final markdown: `summarize.render_html_from_markdown()`.
- Deterministic quality gate: `quality-check.py`.
- Local sent copy: `finalize-local.py`.
- Archive/profile writes: `archive-items.py`.
- Status dashboard rendering and most health classification: `generate-status.py`, `source-health.py`, `channel-health.py`.

**AI/Stochastic Components:**
- Item scoring and tag/line-fit extraction: `score-items.py` via `lib.llm_call()`.
- Official/code/people same-event semantic clustering: `digest_events._semantic_cluster()`.
- Event summaries and item value paragraphs: `summarize.event_summary()`, `summarize.value_paragraph()`, `summarize.saved_value_paragraph()`.
- Headline regeneration for prose/X titles: `summarize.item_headline()`.
- Release-note value bullets: `summarize.release_value_notes()`.
- AI product quality review: `ai-quality-check.py`.
- ASR fixing/media summarization paths are visible in the fetch layer through `fetch-media-transcripts.py`, `polish-douyin.py`, and `fix-asr-errors.py`.

**Network/External Non-Determinism:**
- RSS/scrape/X/WeChat/Douyin/media fetchers: `fetch-rss.py`, `fetch-scrape.py`, `fetch-twitter.py`, `fetch-wechat*.py`, `fetch-douyin.py`, `fetch-media-transcripts.py`.
- Telegram delivery: `push-telegram.py`.
- WeChat RSS freshness probes: `channel-health.py`.
- Dependency probes: `generate-status.py`.

## Key Abstractions

**Source Row:**
- Purpose: One configured input channel from `~/park-io/sources.md`.
- Examples: consumed by `fetch-rss.py`, `fetch-twitter.py`, `summarize.py`, `source-health.py`.
- Pattern: dict rows from `lib.load_sources()` with normalized `profile_id`.

**Profile:**
- Purpose: Stable person/company/channel grouping used for queue files and library archive.
- Examples: `lib.profile_id_for_source()`, `lib.PROFILE_ID_BY_SOURCE_NAME`, `~/park-io/library/profiles/<profile_id>/profile.md`.
- Pattern: deterministic mapping from explicit `profile_id`, known source name, or safe filename.

**Raw Source Markdown File:**
- Purpose: Append-only per-profile-day queue of fetched items.
- Examples: written by `lib.write_source_output()`, moved by `open-batch.py`, parsed by `score-items.py` and `summarize.py`.
- Pattern: frontmatter + repeated `## <title>` item blocks with metadata and `[link](...)`.

**Batch Directory:**
- Purpose: Frozen daily processing unit.
- Examples: `lib.processed_batch_dir()`, `open-batch.py`, `build-digest.py`, `quality-check.py`.
- Pattern: `~/park-io/inbox/processed/<YY-MM-DD-label>/` with raw source files plus `000-<label>.md|html|png`.

**Score Record:**
- Purpose: Persistent per-URL score metadata.
- Examples: `scores.json`, `score-items.py`, `summarize.attach_scores()`.
- Pattern: URL-keyed JSON with `score`, `tags`, `line_fit`, `reason`, `scored_at`.

**Event:**
- Purpose: Group of one or more items rendered as one digest unit.
- Examples: `digest_events.build_events()`, `summarize.render_summary_event()`.
- Pattern: dict with `event_key`, `items`, `primary`, `score`, `line_fit`, `tags`.

**Hidden Markers:**
- Purpose: Machine-readable URL lists embedded in final markdown without visible rendering.
- Examples: `summarize.PROCESSED_MARKER`, `summarize.PUSH_MARKER`, `push-telegram.py`.
- Pattern: HTML comments containing JSON arrays.

**Channel Health Row:**
- Purpose: Distinguish healthy quiet channels from broken or stale channels.
- Examples: `channel-health.py`, `summarize.source_health()`, `generate-status.py`.
- Pattern: `state`/`status` values derived from fetch logs plus feed freshness.

## Entry Points

**Fetch Raw:**
- Location: `fetch-all.sh`
- Triggers: cron/launchd/manual every few hours.
- Responsibilities: choose Python, prevent overlapping fetches, run `fetch.py`, log results.

**Fetch Orchestrator:**
- Location: `fetch.py`
- Triggers: `fetch-all.sh`.
- Responsibilities: run all fetchers, record source health, regenerate dashboard.

**Digest Orchestrator:**
- Location: `push-digest.sh`
- Triggers: cron/launchd/manual daily run.
- Responsibilities: wait for fetch lock, open batch, score, build digest, quality-check, archive, finalize local sent, optional Telegram, regenerate status.

**Manual Batch Open:**
- Location: `open-batch.py`
- Triggers: `push-digest.sh` or manual.
- Responsibilities: move pending raw files into a processed batch and print the batch id.

**Build Digest:**
- Location: `build-digest.py`
- Triggers: `push-digest.sh`.
- Responsibilities: run `summarize.py` and optional HTML-to-PNG rendering.

**Quality Check:**
- Location: `check-quality.py`
- Triggers: `push-digest.sh`.
- Responsibilities: delegate to `quality-check.py`.

**Telegram Push:**
- Location: `send-artifacts.py`
- Triggers: `push-digest.sh` only when `PARKIO_SKIP_SEND=0`, or manual.
- Responsibilities: delegate to `push-telegram.py` with quality skip.

**Status Page:**
- Location: `generate-status.py`
- Triggers: `fetch.py`, `push-digest.sh`, manual.
- Responsibilities: render owner dashboard from pipeline state and health.

## Architectural Constraints

- **Runtime model:** Single-machine Python CLI pipeline. There is no HTTP API server in this repo.
- **Concurrency:** `fetch-all.sh` uses `logs/fetch.lock`; `push-digest.sh` waits up to 60 minutes for that lock before skipping the digest.
- **Global state:** `lib.py` defines module-level paths and LLM provider settings; `digest_config.py` caches active Douyin source names; `digest_events.py` caches semantic cluster results in `_SEM_CACHE`; `summarize.py` tracks per-run LLM headline budget and failures.
- **File state:** Many scripts read/write shared JSON and markdown files directly (`state.json`, `scores.json`, `tg-push-state.json`, `~/park-io/inbox/*`), so avoid concurrent writes outside the orchestrators.
- **Routing rule:** AI must not decide source routing; use deterministic source/profile/group helpers in `digest_config.py` and `summarize.py`.
- **Quality boundary:** Reader-facing output must pass `quality-check.py` before delivery; AI QC is advisory unless strict mode is enabled.
- **Secrets:** Do not read or commit secret contents. Code loads secret values via env or files under `~/park-io/secrets/`.
- **Output authority:** Markdown is the single digest content source; HTML is rendered from that markdown by `summarize.render_html_from_markdown()`.
- **External runtime assumptions:** X auth, WeWe RSS, Douyin downloader/cookies, YouTube cookies, DeepSeek/Anthropic-compatible LLM access, and Telegram credentials can affect runs but are outside repo source code.

## Anti-Patterns

### Letting AI Decide Routing

**What happens:** Adding an LLM classification step to choose whether an item belongs in official, X, media, saved, WeChat, or manual sections.

**Why it's wrong:** The repo contract keeps routing deterministic so sections remain stable and debuggable.

**Do this instead:** Add or adjust source groups and roles in `digest_config.py`, then use existing helpers in `summarize.py`.

### Rendering HTML From Raw Sources

**What happens:** Generating HTML with separate summarization/rendering logic instead of from final markdown.

**Why it's wrong:** Markdown/HTML divergence is a hard quality failure in `quality-check.py`.

**Do this instead:** Keep markdown as the source and render with `summarize.render_html_from_markdown()`.

### Hiding Fetch Or Scoring Failures As Empty Content

**What happens:** Treating failed fetches or scoring outages as "no updates".

**Why it's wrong:** The operator needs to know whether a source is quiet, stale, or broken.

**Do this instead:** Record source errors in `state.json`, `source-health.json`, `scoring-health.json`, and logs; consume them through `channel-health.py`, `summarize.source_health()`, and `generate-status.py`.

### Bypassing The Quality Gate

**What happens:** Sending Telegram or finalizing reader-facing output before `quality-check.py`.

**Why it's wrong:** The deterministic gate catches producer voice, metadata leakage, raw English, hidden marker problems, duplicate push URLs, and MD/HTML divergence.

**Do this instead:** Keep `push-digest.sh` stage order: `build-digest.py` → `check-quality.py` → archive/finalize/send.

### Using Historical Push State To Decide Today's Digest

**What happens:** Filtering today’s visible digest based on prior sent/pushed URLs.

**Why it's wrong:** `summarize.read_today_items()` scopes dedupe to the current batch; historical push state is only for Telegram delivery dedupe.

**Do this instead:** Use `tg-push-state.json` only in `push-telegram.py` and keep digest rendering batch-scoped.

## Error Handling

**Strategy:** Continue where possible in fetch/status stages; fail hard before final delivery when product quality or required artifacts are invalid.

**Patterns:**
- Fetch orchestrator logs each failing fetcher but continues to the next fetcher in `fetch.py`.
- Platform fetchers write per-source failure status/error into `state.json` where implemented.
- `lib.llm_call()` retries transient LLM failures and can fail over from DeepSeek to Anthropic-compatible CLIProxy; non-retryable provider/config errors fail fast.
- `score-items.py` records scoring outages in `scoring-health.json` and keeps official/manual/media classes independent from scoring.
- `summarize.py` falls back to deterministic/source-derived text when LLM calls fail and writes a local health alert for true LLM degradation.
- `quality-check.py` returns non-zero for deterministic red lines; AI QC is non-blocking unless strict mode is enabled.
- `finalize-local.py` uses temp-file copy and replace for local sent artifacts.
- `push-telegram.py` can dry-run with `PARKIO_PUSH_DRY_RUN=1` and force URL pushes with `PARKIO_FORCE_PUSH=1`.

## Cross-Cutting Concerns

**Logging:** Use `lib.log(component, msg)` for component-specific logs under `logs/<component>.log`; shell orchestrators write `logs/fetch-all.log` and `logs/push-digest.log`.

**Validation:** Deterministic product validation lives in `quality-check.py`; workflow/source invariants are documented in `AGENTS.md` and `GOTCHAS.md`; tests live in `tests/`.

**Authentication:** Local env and secret-file loading only. LLM keys use `PARKIO_DEEPSEEK_KEY` / `~/park-io/secrets/deepseek-key` and `PARKIO_CLIPROXY_KEY` / `~/park-io/secrets/cliproxy-key`; Telegram uses `PARKIO_TELEGRAM_BOT_TOKEN`, `PARKIO_TELEGRAM_CHAT_ID`, or `~/park-io/secrets/telegram-*`; other fetcher auth/cookies stay in local files referenced by fetch/status code.

**Configuration:** Source list and owner context come from `~/park-io/sources.md`; LLM and runtime toggles are environment variables read by `lib.py`, `score-items.py`, `summarize.py`, `quality-check.py`, `push-telegram.py`, and shell scripts.

**Observability:** `generate-status.py` is the owner-facing status surface; `source-health.py` provides historical fetch success; `channel-health.py` provides truthful current channel state from logs plus freshness probes; digest markdown includes a compact channel overview.

**Archival:** `archive-items.py` keeps long-term profile assets under `~/park-io/library/profiles/` and independent/manual content under `~/park-io/library/独立链接/`; profile baselines feed future scoring context in `score-items.py`.

---

*Architecture analysis: 2026-06-04*
