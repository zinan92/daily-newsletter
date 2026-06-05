<!-- refreshed: 2026-06-05 -->
# Architecture

**Analysis Date:** 2026-06-05

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│              Shell Orchestrators (cron / launchd)                    │
│   `fetch-all.sh`  (every 4h)      `push-digest.sh`  (daily fixed)   │
└────────────────────────┬─────────────────────────────────────────────┘
                         │ invokes root entrypoints
┌────────────────────────▼─────────────────────────────────────────────┐
│  Stage 1 – Ingestion   `fetch.py`  (fans out to all fetchers)        │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ingestion/ │ │ingestion/│ │ingestion/│ │ingestion/│ │ingestion/│  │
│  │  rss/     │ │web_scrape│ │  x/      │ │wechat_rss│ │ douyin/  │  │
│  │  run.py   │ │  run.py  │ │timeline  │ │  run.py  │ │  run.py  │  │
│  └───────────┘ └──────────┘ │  saved   │ │exporter  │ └──────────┘  │
│  ┌───────────┐               └──────────┘ └──────────┘               │
│  │ingestion/ │                                                        │
│  │manual_links/run.py, wechat_seed.py                                │
│  └───────────┘                                                        │
│  Output → `~/park-io/inbox/unprocessed/<date>-<profile>.md`          │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│  Stage 1b – Enrichment   `fetch-media-transcripts.py` (wrapper)      │
│  `enrichment/media/run.py`  — transcript, clean, deep summary        │
│  `enrichment/quoted_article/`  — future: resolve X-quoted URLs       │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│  Stage 2 – Batch Open   `open-batch.py`                              │
│  Moves unprocessed/<date>-*.md → processed/<batch>/                  │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│  Stage 3 – Aggregation / Digest  `aggregation/digest/`               │
│  score_stage → build → check_stage → archive → finalize_local        │
│  summarize (LLM) · quality (rules) · ai_quality (LLM gate)           │
│  html_to_long_image (PNG artifact)                                    │
│  Output → `~/park-io/inbox/processed/<batch>/` (md + html + png)     │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│  Stage 4 – Deliver   `send-artifacts.py` → `push-telegram.py`        │
│  Output → Telegram channel + `~/park-io/inbox/sent/`                 │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | Key Files |
|-----------|----------------|-----------|
| Shell orchestrators | Cron/launchd entry; sequencing; lock management | `fetch-all.sh`, `push-digest.sh` |
| `fetch.py` | Fan-out stage 1: runs all ingestion wrappers | `fetch.py` |
| `ingestion/rss/` | RSS/Atom feed ingestion (blogs, podcasts, YouTube feeds) | `ingestion/rss/run.py` |
| `ingestion/web_scrape/` | Scrape-based ingestion for non-RSS sites | `ingestion/web_scrape/run.py` |
| `ingestion/x/` | Twitter/X timeline and saved-post ingestion | `ingestion/x/timeline.py`, `ingestion/x/saved.py` |
| `ingestion/wechat_rss/` | WeChat public-account articles via WeWe RSS bridge | `ingestion/wechat_rss/run.py`, `ingestion/wechat_rss/exporter.py` |
| `ingestion/douyin/` | Douyin (TikTok CN) video source discovery | `ingestion/douyin/run.py` |
| `ingestion/manual_links/` | Owner-curated URLs and WeChat seed links | `ingestion/manual_links/run.py`, `ingestion/manual_links/wechat_seed.py` |
| `ingestion/release_feed/` | GitHub release / changelog feeds (future split from rss) | `ingestion/release_feed/CONTRACT.md` (contract-only) |
| `ingestion/youtube/` | YouTube-specific discovery (future split from rss) | `ingestion/youtube/CONTRACT.md` (contract-only) |
| `ingestion/common/` | Shared helpers: source loading, artifact building, URL normalisation | `ingestion/common/CONTRACT.md` |
| `enrichment/media/` | Transcript fetch, transcript cleanup, deep summary, publishability | `enrichment/media/run.py` |
| `enrichment/quoted_article/` | Future: resolve links quoted in X posts | `enrichment/quoted_article/CONTRACT.md` (contract-only) |
| `aggregation/digest/` | Scoring, digest build, summarise (LLM), quality gates, archive, HTML/PNG | `aggregation/digest/score_stage.py` … `finalize_local.py` |
| `open-batch.py` | Move unprocessed raw files into a named batch directory | `open-batch.py` |
| `push-telegram.py` | Deliver artifacts to Telegram | `push-telegram.py` |
| `generate-status.py` | Owner-facing daily inbox dashboard HTML | `generate-status.py` |
| `lib.py` | Shared path constants, LLM helpers, frontmatter parsing | `lib.py` |
| `digest_config.py` | Score thresholds, category order, source roles | `digest_config.py` |
| `digest_events.py` | Event identity and grouping rules | `digest_events.py` |
| `digest_text.py` | Text cleaning helpers (HTML strip, release bullets) | `digest_text.py` |
| `contracts/` | Contract layer: schema JSON and README defining the standard artifact | `contracts/README.md` |
| `workflow/diagram/` | Executable workflow graph (JSON) — canonical node/edge definition | `workflow/diagram/daily-newsletter.graph.json` |
| `workflow/n8n/` | Generated n8n adapter artifact from graph | `workflow/n8n/daily-newsletter.workflow.json` |
| `scripts/` | Task-graph OS, workflow graph runners, n8n export/diff | `scripts/task_graph_lib.py`, `scripts/workflow_graph_lib.py` |

## Pattern Overview

**Overall:** Contract-first layered ingestion pipeline

**Key Characteristics:**
- Contracts (interface schemas) are defined in `contracts/` and per-channel `CONTRACT.md` files before implementation changes. Channels may not embed reader-facing logic.
- Ingestion is channel-parallel: each channel adapter is independently runnable via its own `run.py`.
- Root-level `fetch-*.py` wrappers are thin compatibility shims — they re-export from the new module and call `main()`. All real logic lives in the folder layer.
- Aggregation stages are strictly sequential (open-batch → score → build → quality-check → archive → finalize), gated by `push-digest.sh`.
- The pipeline writes to `~/park-io/inbox/` (outside the repo) as its artifact store.

## Layers

**Contracts Layer:**
- Purpose: Define the schema and boundary rules for every channel before any implementation.
- Location: `contracts/` (global), `ingestion/*/CONTRACT.md`, `enrichment/*/CONTRACT.md`, `aggregation/digest/CONTRACT.md`
- Contains: JSON schema (`contracts/ingestion-artifact.schema.json`), boundary prose
- Depends on: nothing
- Used by: all ingestion adapters and downstream enrichment/aggregation

**Ingestion Layer:**
- Purpose: Per-channel raw data fetching and source-specific normalisation into standard artifacts
- Location: `ingestion/<channel>/run.py` (or `timeline.py`, `saved.py`, `exporter.py` for multi-entrypoint channels)
- Contains: HTTP fetch, feed parsing, dedup, `~/park-io/inbox/unprocessed/<date>-<profile>.md` writes
- Depends on: `lib.py`, `ingestion/common/`, channel-specific external runtime (content-toolkit, wewe-rss, twitter-cli)
- Used by: root wrapper scripts, `fetch.py`

**Enrichment Layer:**
- Purpose: Cross-channel post-processing of individual items (transcript, quoted article resolution)
- Location: `enrichment/media/run.py`, `enrichment/quoted_article/` (future)
- Contains: yt-dlp / MLX Whisper / content-toolkit calls, transcript cleaning, deep LLM summary, `publishable` flag
- Depends on: `lib.py`, ingestion outputs
- Used by: root wrapper `fetch-media-transcripts.py`, runs alongside ingestion in `fetch.py`

**Aggregation Layer:**
- Purpose: Batch assembly, scoring, summarisation, quality gating, archiving, rendering
- Location: `aggregation/digest/`
- Contains: `score_stage.py`, `score_items.py`, `build.py`, `summarize.py`, `check_stage.py`, `quality.py`, `ai_quality.py`, `archive.py`, `finalize_local.py`, `html_to_long_image.py`
- Depends on: `lib.py`, `digest_config.py`, `digest_events.py`, `digest_text.py`, Anthropic/DeepSeek LLM API
- Used by: root wrapper scripts, `push-digest.sh`

**Workflow / Task-Graph Layer:**
- Purpose: Executable graph specs for n8n and planning-agent task orchestration
- Location: `workflow/diagram/`, `workflow/n8n/`, `scripts/workflow_graph_*.py`, `scripts/task_graph_*.py`
- Contains: Graph JSON, export/diff adapters, dry-run runners
- Depends on: nothing in the pipeline (spec-only at this stage)
- Used by: CI verification, future n8n automation

## Data Flow

### Primary Daily Run

1. `fetch-all.sh` (cron, every 4h) → invokes `fetch.py`
2. `fetch.py` → fans out to all `fetch-*.py` wrappers sequentially
3. Each wrapper → re-exports and calls `main()` from its `ingestion/<channel>/run.py`
4. Each adapter writes raw items to `~/park-io/inbox/unprocessed/<date>-<profile>.md`
5. `fetch-media-transcripts.py` → `enrichment/media/run.py` runs transcript/summary enrichment
6. `push-digest.sh` (daily launchd, fixed time) waits for fetch lock to clear
7. `open-batch.py` → moves `unprocessed/` files into `processed/<batch-id>/`; emits `PARKIO_BATCH_ID`
8. `score.py` → `aggregation/digest/score_stage.py`: scores all items in the batch
9. `build-digest.py` → `aggregation/digest/build.py`: assembles ranked digest Markdown
10. `check-quality.py` → `aggregation/digest/check_stage.py`: rule-based quality gate
11. `archive-items.py` → `aggregation/digest/archive.py`: archives items
12. `finalize-local.py` → `aggregation/digest/finalize_local.py`: writes final MD + HTML + PNG
13. `send-artifacts.py` → `push-telegram.py`: pushes selected sections to Telegram; moves to `sent/`
14. `generate-status.py`: writes owner-facing daily inbox dashboard

### Batch Abort Path

If any stage in `push-digest.sh`'s `STAGES` array exits non-zero, the shell script stops immediately and logs `push-digest STOPPED at <stage>`. No subsequent stages run.

**State Management:**
- Inter-stage state is filesystem-based: files in `~/park-io/inbox/` are the shared artifact store.
- `PARKIO_BATCH_ID` environment variable carries the batch identifier from `open-batch.py` through all downstream stages in a single `push-digest.sh` run.
- `state.json` in the repo root carries persistent cross-run state (source tracking, last-seen items).
- `source-health.json` tracks fetch health per source.

## Key Abstractions

**Standard Ingestion Artifact:**
- Purpose: Channel-neutral JSON structure emitted by every ingestion adapter
- Schema: `contracts/ingestion-artifact.schema.json`
- Fields: `schema_version`, `channel`, `source`, `run`, `items`, `health`, `errors`
- Channel-specific details go in `item.metadata` or `source.metadata`, never in `content`

**Compatibility Wrapper:**
- Purpose: Root-level `fetch-*.py` / `score.py` / `build-digest.py` etc. keep cron/launchd CLI paths stable during refactor
- Pattern: `from ingestion.<channel>.run import *; main()` — zero business logic
- Governed by: `STATE.md` decision "Root CLI/cron entrypoints must remain compatible until the refactor is fully proven"

**`lib.py` Shared Utilities:**
- Purpose: Single import point for path constants, LLM calls, frontmatter parsing, source loading
- Location: `lib.py`
- Key exports: `ROOT`, `PARKIO`, `INBOX`, `UNPROCESSED_DIR`, `SENT_DIR`, `load_sources()`, `llm_call()`, `parse_frontmatter()`, `batch_id()`

**Digest Config / Events / Text:**
- `digest_config.py`: product policy constants (score thresholds, category order, source roles)
- `digest_events.py`: event identity, grouping, source-role resolution
- `digest_text.py`: text cleaning and HTML-to-Markdown helpers

## Entry Points

**Shell Orchestrators (primary cron / launchd entrypoints):**
- `fetch-all.sh`: Runs every 4 hours; acquires a lock file; calls `fetch.py`; handles Python discovery
- `push-digest.sh`: Daily fixed-time run; waits for fetch lock; runs `open-batch.py` then the aggregation stage sequence

**Python Stage Runners (invoked by shells):**
- `fetch.py`: Stage 1 fan-out — sequentially runs all `fetch-*.py` wrappers
- `open-batch.py`: Moves unprocessed items into a named batch; prints `PARKIO_BATCH_ID`
- `generate-status.py`: Generates daily inbox dashboard; not gated, runs after deliver

**Root Compatibility Wrappers (NOT real entrypoints — thin re-exports):**

| Root file | Real implementation |
|-----------|---------------------|
| `fetch-rss.py` | `ingestion/rss/run.py` |
| `fetch-scrape.py` | `ingestion/web_scrape/run.py` |
| `fetch-twitter.py` | `ingestion/x/timeline.py` |
| `fetch-twitter-saved.py` | `ingestion/x/saved.py` |
| `fetch-wechat.py` | `ingestion/manual_links/wechat_seed.py` |
| `fetch-wechat-rss.py` | `ingestion/wechat_rss/run.py` |
| `fetch-wechat-exporter.py` | `ingestion/wechat_rss/exporter.py` |
| `fetch-douyin.py` | `ingestion/douyin/run.py` |
| `fetch-manual-links.py` | `ingestion/manual_links/run.py` |
| `fetch-media-transcripts.py` | `enrichment/media/run.py` |
| `score.py` | `aggregation/digest/score_stage.py` |
| `score-items.py` | `aggregation/digest/score_items.py` |
| `build-digest.py` | `aggregation/digest/build.py` |
| `summarize.py` | `aggregation/digest/summarize.py` |
| `check-quality.py` | `aggregation/digest/check_stage.py` |
| `quality-check.py` | `aggregation/digest/quality.py` |
| `ai-quality-check.py` | `aggregation/digest/ai_quality.py` |
| `archive-items.py` | `aggregation/digest/archive.py` |
| `finalize-local.py` | `aggregation/digest/finalize_local.py` |
| `html-to-long-image.py` | `aggregation/digest/html_to_long_image.py` |
| `send-artifacts.py` | delegates to `push-telegram.py` |

**Utility / Ops Scripts (not in daily pipeline):**
- `channel-health.py`: Per-channel health derived from fetch logs
- `check-pipeline-health.py`: Daily health alert via Telegram (post-digest)
- `source-health.py`: Records and renders source-level fetch health
- `push-telegram.py`: Direct Telegram delivery (also called by `send-artifacts.py`)
- `refresh-twitter-auth.py`: Manual X/Twitter cookie refresh
- `onboard-source.py`, `onboard-baseline.py`: One-time source onboarding
- `polish-douyin.py`, `fix-asr-errors.py`: Corpus maintenance tools
- `build-index.py`, `backfill-claude-blog-library.py`: Library index tools

## Architectural Constraints

- **Contract-first refactor in progress:** `ingestion/release_feed/` and `ingestion/youtube/` exist as `CONTRACT.md`-only stubs — no `run.py` yet. RSS adapter handles those sources in the interim.
- **Root wrappers are frozen:** do not add business logic to root `fetch-*.py` / aggregation wrapper files. All changes go in the folder layer.
- **Filesystem as message bus:** stages communicate via `~/park-io/inbox/` files, not in-process calls. No queue or broker.
- **Sequential aggregation:** `push-digest.sh` runs aggregation stages strictly in order; a non-zero exit halts the pipeline.
- **External secrets:** bot token, API keys, and Twitter cookies are stored outside the repo in `~/park-io/secrets/` or env vars. `lib._load_secret()` is the only sanctioned loader.
- **LLM model:** DeepSeek deepseek-chat (deepseek-v4-flash, thinking disabled) with Anthropic as failover. Model selection constants live in `lib.py` / caller code, not in config files.
- **`summarize.py` re-export pattern:** uses `globals().update(vars(_impl))` rather than `import *` because the module name collides with the Python stdlib; all other wrappers use `import *`.

## Error Handling

**Strategy:** Fail-fast with logged exit codes; no silent swallowing.

**Patterns:**
- Each stage in `push-digest.sh` checks exit code; non-zero → log `STOPPED at <stage>` and `exit "$EXIT"`.
- `fetch.py` logs per-fetcher exit but continues to the next fetcher (fetch errors are non-fatal for the fan-out; individual adapter errors are logged).
- `check-pipeline-health.py` sends Telegram alert when today's digest was not sent or a source has been down for 7+ days.
- `lib.py` `llm_call()` raises on HTTP errors; callers are responsible for catching and surfacing failures.

## Cross-Cutting Concerns

**Logging:** File-based (`logs/fetch-all.log`, `logs/push-digest.log`); each stage writes timestamped lines via `lib.log()`.
**Validation:** Source config validated by `ingestion/common/` helpers; item contract validated in tests (`tests/test_ingestion_contracts.py`).
**Authentication:** Secrets loaded via `lib._load_secret()` from env var or `~/park-io/secrets/<file>`; never hardcoded.

---

*Architecture analysis: 2026-06-05*
