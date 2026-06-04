# Codebase Structure

**Analysis Date:** 2026-06-04

## Directory Layout

```text
input-to-park/
├── *.py                         # Flat Python CLI/cron pipeline scripts
├── fetch-all.sh                 # Scheduled fetch entrypoint
├── push-digest.sh               # Scheduled digest/finalize entrypoint
├── prompts/                     # Markdown prompts for legacy/source summarization
├── tests/                       # Plain Python regression tests
├── logs/                        # Runtime logs written by shell and Python stages
├── .runtime/wewe-rss/           # Local WeWe RSS runtime data
├── .planning/codebase/          # Codebase map documents
├── README.md                    # Product and operator overview
├── AGENTS.md                    # Agent editing rules and workflow constraints
├── GOTCHAS.md                   # Behavioral invariants and regression map
├── HANDOVER.md                  # Current operational handover notes
└── *.json                       # Local state, health, scoring, and media queues
```

## Directory Purposes

**Repository Root:**
- Purpose: Keep every executable pipeline stage at top level for cron/launchd and manual operation.
- Contains: Fetchers (`fetch-*.py`), scoring (`score.py`, `score-items.py`), digest build (`build-digest.py`, `summarize.py`), quality gates (`check-quality.py`, `quality-check.py`, `ai-quality-check.py`), archival/finalization (`archive-items.py`, `finalize-local.py`), delivery (`send-artifacts.py`, `push-telegram.py`), status (`generate-status.py`, `channel-health.py`, `check-pipeline-health.py`).
- Key files: `lib.py`, `digest_config.py`, `digest_events.py`, `digest_text.py`, `fetch.py`, `fetch-all.sh`, `push-digest.sh`, `summarize.py`, `quality-check.py`.

**`prompts/`:**
- Purpose: Store markdown prompts used by summarization/assembly paths.
- Contains: `prompts/summarize-blogs.md`, `prompts/summarize-tweets.md`, `prompts/digest-intro.md`.
- Use prompt files for source-level prompt text when a script needs stable, editable instructions; keep product invariants in code/tests, not only prompt wording.

**`tests/`:**
- Purpose: Store regression tests for product invariants.
- Contains: Standalone `tests/test_*.py` modules that can be run directly with `python3 tests/test_name.py`.
- Key files: `tests/test_bypass.py`, `tests/test_cleaning.py`, `tests/test_titles.py`, `tests/test_thread_merge.py`, `tests/test_llm_fallback.py`, `tests/test_alerts.py`.

**`logs/`:**
- Purpose: Runtime log output for scheduled fetch and digest jobs.
- Contains: `logs/fetch-all.log`, `logs/push-digest.log`, lock files such as `logs/fetch.lock`.
- Generated: Yes.
- Committed: Runtime files should be treated as local operational state.

**`.runtime/wewe-rss/`:**
- Purpose: Local WeWe RSS runtime data for WeChat feed support.
- Contains: Runtime data under `.runtime/wewe-rss/data`.
- Generated: Yes.
- Committed: Treat as local runtime state, not source code.

**External Park-IO Data Root `~/park-io/`:**
- Purpose: Hold source configuration, inbox queues, processed artifacts, sent artifacts, long-term library, status files, and secrets outside the code repo.
- Key paths: `/Users/wendy/park-io/sources.md`, `/Users/wendy/park-io/inbox/manual-links.md`, `/Users/wendy/park-io/inbox/unprocessed/`, `/Users/wendy/park-io/inbox/processed/`, `/Users/wendy/park-io/inbox/sent/`, `/Users/wendy/park-io/library/profiles/`, `/Users/wendy/park-io/library/独立链接`.
- Do not read or document secret values under `/Users/wendy/park-io/secrets/` or `/Users/wendy/park-io/outbox/.system/secrets/`.

## Key File Locations

**Entry Points:**
- `fetch-all.sh`: Cron/launchd fetch wrapper; selects Python 3.11+, sets `PYTHONPATH` for `~/content-toolkit/capabilities/download`, locks with `logs/fetch.lock`, then runs `fetch.py`.
- `push-digest.sh`: Daily digest wrapper; waits for `logs/fetch.lock`, opens a batch with `open-batch.py`, then runs `score.py`, `build-digest.py`, `check-quality.py`, `archive-items.py`, `finalize-local.py`, and optionally `send-artifacts.py`.
- `fetch.py`: Fetch orchestrator for source fetch stages.
- `open-batch.py`: Moves pending inbox files into a processed batch and emits `PARKIO_BATCH_ID`.
- `build-digest.py`: Runs `summarize.py`, then renders PNG from HTML via `html-to-long-image.py` when HTML exists.

**Configuration:**
- `lib.py`: Defines repo root and Park-IO paths: `ROOT`, `PARKIO`, `SOURCES_PATH`, `INBOX`, `UNPROCESSED_DIR`, `PROCESSED_DIR`, `SENT_DIR`, `LIBRARY_DIR`, `PROFILE_LIBRARY_DIR`, `INDEPENDENT_LINKS_DIR`.
- `digest_config.py`: Product policy constants: score thresholds, source groups, source roles, source authority, bad LLM markers, active Douyin source lookup.
- `/Users/wendy/park-io/sources.md`: Single source of truth for active sources; `lib.load_sources()` parses the first markdown table and ignores inactive rows.
- `/Users/wendy/park-io/inbox/manual-links.md`: Single manual link queue with `Pending`, `Imported`, and `Failed` sections.
- `state.json`, `scores.json`, `source-health.json`, `scoring-health.json`, `media-queue.json`, `media-summaries.json`, `tg-push-state.json`: Local JSON state and health files read/written by pipeline stages.

**Core Logic:**
- `lib.py`: Shared path helpers, source parser, state helpers, markdown item rendering, source output writer, LLM client, health alert writer, Telegram helper.
- `summarize.py`: Main daily intelligence panel builder; reads processed items, scores, media summaries, source health, and writes final markdown/html artifacts.
- `digest_events.py`: Event grouping, thread merging, official grouping, source ranking, semantic clustering.
- `digest_text.py`: Reader-facing text cleanup; strips source metadata and bad LLM wording.
- `quality-check.py`: Deterministic reader-facing gate; blocks metadata leaks, raw English, bad patterns, push marker issues, and markdown/html heading divergence.
- `ai-quality-check.py`: AI second-pass quality review.
- `archive-items.py`: Moves processed items into profile library files and keeps profile baselines current.
- `finalize-local.py`: Writes final local sent artifacts under `/Users/wendy/park-io/inbox/sent/`.

**Fetchers:**
- `fetch-rss.py`: RSS, GitHub release feeds, and YouTube RSS/fallback handling.
- `fetch-scrape.py`: HTML scrape sources such as official blogs/news pages.
- `fetch-twitter.py`: X account fetch path.
- `fetch-twitter-saved.py`: User saved X items path.
- `fetch-wechat.py`: Direct WeChat article fetch/parser/library writer.
- `fetch-wechat-rss.py`: WeWe RSS-based WeChat feed fetcher.
- `fetch-wechat-exporter.py`: WeChat exporter import path.
- `fetch-manual-links.py`: Manual WeChat article import path from `/Users/wendy/park-io/inbox/manual-links.md`.
- `fetch-douyin.py`: Douyin source fetcher using `content_downloader` from `~/content-toolkit/capabilities/download`.
- `fetch-media-transcripts.py`, `fix-asr-errors.py`, `polish-douyin.py`: Media transcription and cleanup path.

**Status and Operations:**
- `channel-health.py`: Source health truth from fetch logs and feed freshness.
- `source-health.py`: Source health data collection.
- `generate-status.py`: Maintainer status page writer.
- `check-pipeline-health.py`: Writes local health alerts for transcription failures, scoring outages, stale feeds, and related operational problems.
- `send-artifacts.py`, `push-telegram.py`: Delivery path; Telegram is optional and normally skipped by `PARKIO_SKIP_SEND=1`.

**Testing:**
- `tests/test_bypass.py`: Official/manual/media score bypass invariants.
- `tests/test_cleaning.py`: Reader-facing metadata cleanup invariants.
- `tests/test_chinese_fallback.py`: Chinese fallback behavior.
- `tests/test_titles.py`: Title generation and stale-title prevention.
- `tests/test_thread_merge.py`: X thread merge behavior.
- `tests/test_douyin_delivery.py`: Douyin delivery/archive behavior.
- `tests/test_llm_fallback.py`: DeepSeek to Anthropic/Sonnet fallback behavior.
- `tests/test_alerts.py`: Local health alert behavior.

## Park-IO Output Folders

**Unprocessed Queue:**
- Location: `/Users/wendy/park-io/inbox/unprocessed/`.
- Naming: `YY-MM-DD-profile_id.md`, created by `lib.write_source_output()` through `lib.profile_day_filename()`.
- Current examples: `/Users/wendy/park-io/inbox/unprocessed/26-06-04-openai.md`, `/Users/wendy/park-io/inbox/unprocessed/26-06-04-x-saved.md`, `/Users/wendy/park-io/inbox/unprocessed/26-06-04-thariq.md`.

**Processed Batch:**
- Location: `/Users/wendy/park-io/inbox/processed/<YY-MM-DD>/`.
- Final reader artifacts: `000-YY-MM-DD.md`, `000-YY-MM-DD.html`, `000-YY-MM-DD.png`, generated via `lib.batch_artifact_paths()` and `build-digest.py`.
- Per-profile processed files remain alongside final artifacts, for example `/Users/wendy/park-io/inbox/processed/26-06-04/26-06-04-openai.md`.

**Sent / Local Final:**
- Location: `/Users/wendy/park-io/inbox/sent/`.
- Purpose: Owner-facing local final digest output written by `finalize-local.py`.
- Naming: `YY-MM-DD.md` and HTML when available; do not make timestamped variants.

**Profile Library:**
- Location: `/Users/wendy/park-io/library/profiles/<profile_id>/items/`.
- Purpose: Long-term archived content by source/profile.
- Profile metadata: `archive-items.py` creates or updates `/Users/wendy/park-io/library/profiles/<profile_id>/profile.md`.
- Current profiles include `/Users/wendy/park-io/library/profiles/anthropic`, `/Users/wendy/park-io/library/profiles/openai`, `/Users/wendy/park-io/library/profiles/claude-hunter`, `/Users/wendy/park-io/library/profiles/zhuzi-tzfilm`.

**Independent Links:**
- Location: `/Users/wendy/park-io/library/独立链接/`.
- Purpose: Manual or unknown-profile WeChat articles that cannot map to a tracked source.
- Writer: `fetch-manual-links.py` via `save_independent_article()` and `archive-items.py` for `unknown-profile`, `x-saved`, or `manual-link`.

## Naming Conventions

**Files:**
- Top-level executable scripts use kebab-case verbs: `fetch-manual-links.py`, `score-items.py`, `quality-check.py`, `push-telegram.py`.
- Shared import modules use snake_case: `digest_config.py`, `digest_events.py`, `digest_text.py`.
- Tests use `test_<topic>.py`: `tests/test_source_health.py`, `tests/test_health_dashboard.py`.
- Prompts use kebab-case markdown names: `prompts/summarize-blogs.md`, `prompts/summarize-tweets.md`.
- Local state files use lowercase kebab names when operational: `source-health.json`, `scoring-health.json`, `media-queue.json`.

**Directories:**
- Repo-local directories are lowercase purpose names: `prompts/`, `tests/`, `logs/`.
- Park-IO batch directories use `YY-MM-DD`: `/Users/wendy/park-io/inbox/processed/26-06-04`.
- Profile library directories use sanitized `profile_id` from `/Users/wendy/park-io/sources.md` or `lib.PROFILE_ID_BY_SOURCE_NAME`: `/Users/wendy/park-io/library/profiles/claude-hunter`.

**Source/Profile/Library:**
- Add or disable sources in `/Users/wendy/park-io/sources.md`; the first markdown table is parsed by `lib.load_sources()`.
- Prefer explicit `profile_id` in `/Users/wendy/park-io/sources.md`; otherwise `lib.profile_id_for_source()` maps known names through `lib.PROFILE_ID_BY_SOURCE_NAME` or sanitizes `name`.
- Store long-term profile items in `/Users/wendy/park-io/library/profiles/<profile_id>/items/`; do not add legacy per-channel subfolders under a profile.
- Keep channel/source metadata in frontmatter and filenames, not extra library layers.

## Manual Links Behavior

- Manual links live in `/Users/wendy/park-io/inbox/manual-links.md`, not in the repo.
- The file must keep exactly these sections for automation: `## Pending`, `## Imported`, `## Failed`.
- `fetch-manual-links.py` automatically creates the file with default text if it is missing.
- Only WeChat article URLs matching `https://mp.weixin.qq.com/s/...` are imported automatically.
- Unsupported URLs in `Pending` are preserved and logged; they are not silently deleted.
- Successfully imported URLs move from `Pending` to `Imported` with date, profile, title, and URL.
- Failed URLs move to `Failed` with date, URL, and error.
- Duplicate seen URLs are deduped through `state.json` under key `manual-links`.
- Tracked WeChat accounts map to source/profile via `fetch-manual-links.py source_for_article()` and `/Users/wendy/park-io/sources.md`.
- Unknown manual WeChat articles use profile `manual-link` and are saved under `/Users/wendy/park-io/library/独立链接/`.

## Where to Add New Code

**New Fetch Source Type:**
- Primary code: add a new `fetch-<platform>.py` at repo root, then call it from `fetch.py`.
- Shared source parsing/path behavior: use `lib.load_sources()`, `lib.write_source_output()`, `lib.profile_id_for_source()`, and `lib.safe_filename()`.
- Tests: add focused regression coverage under `tests/test_<topic>.py`.

**New Digest Behavior:**
- Primary code: `summarize.py` for orchestration/rendering, `digest_events.py` for event grouping, `digest_text.py` for cleanup, `digest_config.py` for policy constants.
- Tests: add or extend `tests/test_titles.py`, `tests/test_cleaning.py`, `tests/test_bypass.py`, or a new `tests/test_<invariant>.py`.
- Invariants: update `GOTCHAS.md` when the behavior becomes a regression contract.

**New Prompt:**
- Implementation: add `prompts/<purpose>.md`.
- Loader/invocation: keep prompt loading inside the script that owns the AI call.
- Critical rules: enforce with code/tests when a rule must be guaranteed; prompts alone are not sufficient.

**New Profile/Source:**
- Source row: edit `/Users/wendy/park-io/sources.md`.
- Profile id: use explicit `profile_id` in the row, and add `lib.PROFILE_ID_BY_SOURCE_NAME` only when code needs a stable name mapping.
- Library: allow `archive-items.py` to create `/Users/wendy/park-io/library/profiles/<profile_id>/profile.md` and `items/`.

**Utilities:**
- Shared pipeline helpers: `lib.py`.
- Product policy constants and source groups: `digest_config.py`.
- Text cleanup helpers: `digest_text.py`.
- Event grouping helpers: `digest_events.py`.
- Avoid new packages/modules unless the behavior is shared across multiple top-level scripts.

## Special Directories

**`.planning/codebase/`:**
- Purpose: GSD codebase map documents.
- Generated: Yes.
- Committed: Yes, if the orchestrator chooses to commit maps.

**`.claude/worktrees/`:**
- Purpose: Local agent/worktree runtime state.
- Generated: Yes.
- Committed: Treat as tool/runtime state.

**`.ruff_cache/`:**
- Purpose: Ruff cache.
- Generated: Yes.
- Committed: No.

**`__pycache__/`:**
- Purpose: Python bytecode cache.
- Generated: Yes.
- Committed: No.

---

*Structure analysis: 2026-06-04*
