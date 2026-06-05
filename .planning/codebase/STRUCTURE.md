# Codebase Structure

**Analysis Date:** 2026-06-05

## Directory Layout

```
input-to-park/                        # Repo root
│
├── contracts/                        # Global contract layer (schema-first)
│   ├── README.md                     # Contract rules and boundary definition
│   └── ingestion-artifact.schema.json  # Standard artifact JSON schema
│
├── ingestion/                        # Per-channel source adapters
│   ├── common/                       # Shared ingestion primitives (no fetch logic)
│   │   └── CONTRACT.md
│   ├── rss/                          # RSS/Atom feeds (blogs, podcasts, YouTube RSS)
│   │   ├── CONTRACT.md
│   │   └── run.py
│   ├── web_scrape/                   # Scrape-based ingestion (non-RSS sites)
│   │   ├── CONTRACT.md
│   │   └── run.py
│   ├── x/                            # Twitter/X timeline and saved posts
│   │   ├── CONTRACT.md
│   │   ├── timeline.py               # Fetch user timeline
│   │   └── saved.py                  # Fetch saved/bookmarked posts
│   ├── wechat_rss/                   # WeChat via WeWe RSS bridge
│   │   ├── CONTRACT.md
│   │   ├── run.py                    # WeWe RSS bridge fetcher
│   │   └── exporter.py              # External collector bridge importer
│   ├── manual_links/                 # Owner-curated URLs
│   │   ├── CONTRACT.md
│   │   ├── run.py                    # Main manual link ingestion
│   │   └── wechat_seed.py           # Seeded WeChat article handling
│   ├── douyin/                       # Douyin (TikTok CN) video discovery
│   │   ├── CONTRACT.md
│   │   └── run.py
│   ├── release_feed/                 # GitHub/changelog release feeds [CONTRACT ONLY]
│   │   └── CONTRACT.md
│   └── youtube/                      # YouTube-specific discovery [CONTRACT ONLY]
│       └── CONTRACT.md
│
├── enrichment/                       # Cross-channel post-processing
│   ├── media/                        # Video/audio transcript and deep summary
│   │   ├── CONTRACT.md
│   │   └── run.py
│   └── quoted_article/               # X-quoted URL resolution [CONTRACT ONLY]
│       └── CONTRACT.md
│
├── aggregation/
│   └── digest/                       # Final reader-facing digest pipeline
│       ├── CONTRACT.md
│       ├── score_stage.py            # Stage: score all batch items
│       ├── score_items.py            # Item-level scoring helpers
│       ├── build.py                  # Assemble ranked digest Markdown
│       ├── summarize.py             # LLM summarisation
│       ├── check_stage.py           # Rule-based quality gate
│       ├── quality.py               # Quality check helpers
│       ├── ai_quality.py            # LLM-based quality gate
│       ├── archive.py               # Archive items post-digest
│       ├── finalize_local.py        # Write final MD + HTML + PNG
│       └── html_to_long_image.py   # Render HTML to long PNG image
│
├── workflow/
│   ├── diagram/                      # Canonical executable workflow graph
│   │   ├── README.md
│   │   ├── daily-newsletter.graph.json  # Node/edge definitions with commands
│   │   └── schema.json              # Graph JSON schema
│   └── n8n/                         # Generated n8n adapter artifacts
│       ├── README.md
│       └── daily-newsletter.workflow.json  # n8n-format export (generated)
│
├── scripts/                          # Ops/automation scripts (not in daily pipeline)
│   ├── task_graph_lib.py            # Task graph data model
│   ├── task_graph_validate.py       # Validate task graph JSON
│   ├── task_graph_ready.py          # Compute ready tasks from graph
│   ├── task_graph_threads.py        # Thread/parallelism analysis
│   ├── task_agent_loop.py           # Agent claim/complete loop
│   ├── task_claim.py                # Claim a task (agent protocol)
│   ├── task_complete.py             # Mark task complete
│   ├── task_next.py                 # Query next claimable task
│   ├── workflow_graph_lib.py        # Workflow graph data model
│   ├── workflow_graph_validate.py   # Validate workflow graph
│   ├── workflow_graph_run.py        # Execute workflow graph nodes
│   ├── workflow_graph_dry_run.py    # Dry-run workflow (no production data)
│   ├── n8n_export.py               # Export graph to n8n JSON format
│   └── n8n_import_diff.py          # Diff n8n import against canonical graph
│
├── tasks/                            # Planning agent task documents
│   ├── README.md
│   ├── agent-claim-protocol.md
│   ├── cross-ai-review.md
│   └── review-checklist.md
│
├── tests/                            # Test suite
│   ├── test_ingestion_contracts.py
│   ├── test_ingestion_wrappers.py
│   ├── test_reader_quality_contract.py
│   ├── test_alerts.py
│   ├── test_bypass.py
│   ├── test_channel_health.py
│   ├── test_chinese_fallback.py
│   ├── test_cleaning.py
│   ├── test_douyin_delivery.py
│   ├── test_empty_x.py
│   ├── test_finalize_local.py
│   ├── test_health_dashboard.py
│   ├── test_llm_fallback.py
│   ├── test_media.py
│   ├── test_n8n_export.py
│   ├── test_n8n_import_diff.py
│   ├── test_scrape_sitemap.py
│   ├── test_shorts.py
│   ├── test_source_health.py
│   ├── test_task_graph.py
│   ├── test_thread_merge.py
│   ├── test_titles.py
│   └── test_workflow_graph.py
│
├── prompts/                          # LLM prompt templates
│   ├── digest-intro.md
│   ├── summarize-blogs.md
│   └── summarize-tweets.md
│
│── .planning/                        # GSD planning docs (not shipped)
│   ├── STATE.md
│   ├── ROADMAP.md
│   ├── codebase/
│   └── phases/
│
│   ── Root-level Python (see below for classification)
├── lib.py                            # Shared utilities (path constants, LLM, frontmatter)
├── digest_config.py                 # Product policy constants (thresholds, roles)
├── digest_events.py                 # Event identity and grouping rules
├── digest_text.py                   # Text cleaning helpers
│
│   ── Shell orchestrators (cron/launchd primary entry)
├── fetch-all.sh                      # Cron: runs fetch.py every 4h with lock
├── push-digest.sh                   # Daily: open-batch → score → build → deliver
│
│   ── Python pipeline runners (called by shells)
├── fetch.py                          # Stage 1 fan-out: runs all fetch-*.py
├── open-batch.py                    # Move unprocessed → processed/<batch-id>/
├── generate-status.py               # Owner inbox dashboard (post-deliver)
├── push-telegram.py                 # Direct Telegram delivery
│
│   ── Root compatibility wrappers (re-export only — no logic here)
├── fetch-rss.py                     # → ingestion/rss/run.py
├── fetch-scrape.py                  # → ingestion/web_scrape/run.py
├── fetch-twitter.py                 # → ingestion/x/timeline.py
├── fetch-twitter-saved.py           # → ingestion/x/saved.py
├── fetch-wechat.py                  # → ingestion/manual_links/wechat_seed.py
├── fetch-wechat-rss.py              # → ingestion/wechat_rss/run.py
├── fetch-wechat-exporter.py         # → ingestion/wechat_rss/exporter.py
├── fetch-douyin.py                  # → ingestion/douyin/run.py
├── fetch-manual-links.py            # → ingestion/manual_links/run.py
├── fetch-media-transcripts.py       # → enrichment/media/run.py
├── score.py                         # → aggregation/digest/score_stage.py
├── score-items.py                   # → aggregation/digest/score_items.py
├── build-digest.py                  # → aggregation/digest/build.py
├── summarize.py                     # → aggregation/digest/summarize.py
├── check-quality.py                 # → aggregation/digest/check_stage.py
├── quality-check.py                 # → aggregation/digest/quality.py
├── ai-quality-check.py              # → aggregation/digest/ai_quality.py
├── archive-items.py                 # → aggregation/digest/archive.py
├── finalize-local.py                # → aggregation/digest/finalize_local.py
├── html-to-long-image.py            # → aggregation/digest/html_to_long_image.py
├── send-artifacts.py                # delegates to push-telegram.py
│
│   ── Utility / ops scripts (not in daily pipeline)
├── channel-health.py                # Per-channel health from fetch logs
├── check-pipeline-health.py         # Daily pipeline alert (post-digest Telegram)
├── source-health.py                 # Source-level fetch health tracker
├── refresh-twitter-auth.py          # Manual X cookie refresh
├── onboard-source.py                # One-time: build source profile from history
├── onboard-baseline.py              # One-time: refresh source profile baseline
├── polish-douyin.py                 # Corpus maintenance: transcript polish
├── fix-asr-errors.py                # Corpus maintenance: ASR error corrections
├── build-index.py                   # Library index for 慢学AI corpus
└── backfill-claude-blog-library.py  # Backfill Claude Blog articles into library
```

## Directory Purposes

**`contracts/`:**
- Purpose: Global schema and boundary contract definitions. Defined first — before implementation.
- Contains: `ingestion-artifact.schema.json` (required fields for every channel output), `README.md` (boundary rules)
- Key files: `contracts/README.md`, `contracts/ingestion-artifact.schema.json`

**`ingestion/<channel>/`:**
- Purpose: One folder per source channel. Each owns fetching, source-specific normalisation, and writing raw items to `~/park-io/inbox/unprocessed/`.
- Contains: `run.py` (main entrypoint), `CONTRACT.md` (boundary prose), optional channel-specific modules
- Key files: `ingestion/rss/run.py`, `ingestion/x/timeline.py`, `ingestion/wechat_rss/exporter.py`
- Note: `ingestion/release_feed/` and `ingestion/youtube/` are `CONTRACT.md`-only stubs — no `run.py` yet.

**`ingestion/common/`:**
- Purpose: Shared ingestion primitives (not a channel). Provides source loading, artifact building, URL normalisation, health/error payloads, and test helpers.
- Does not contain: any channel-specific fetch logic.

**`enrichment/`:**
- Purpose: Cross-channel post-processing. Each subfolder owns one enrichment concern.
- Key files: `enrichment/media/run.py` (transcript + deep summary), `enrichment/quoted_article/CONTRACT.md` (future)

**`aggregation/digest/`:**
- Purpose: The complete reader-facing digest pipeline — all stages from raw scores to final PNG artifact.
- Key files: `score_stage.py`, `build.py`, `summarize.py`, `check_stage.py`, `finalize_local.py`, `html_to_long_image.py`

**`workflow/`:**
- Purpose: Executable workflow graph specs (canonical source of truth) and generated n8n adapters.
- `workflow/diagram/daily-newsletter.graph.json` — canonical; edit this.
- `workflow/n8n/daily-newsletter.workflow.json` — generated by `scripts/n8n_export.py`; do not edit directly.

**`scripts/`:**
- Purpose: Automation, task-graph OS, and workflow graph tooling. Not part of the daily ingestion/digest pipeline.
- Key files: `task_graph_lib.py`, `workflow_graph_lib.py`, `n8n_export.py`, `n8n_import_diff.py`

**`tests/`:**
- Purpose: Full test suite. Co-located with repo root (not inside src subdirectory).
- Naming: `test_<feature>.py`. Coverage spans contracts, wrappers, quality gates, health, n8n adapters, workflow graph.

**`prompts/`:**
- Purpose: LLM prompt templates loaded at runtime. Markdown files, not Python.

## Root-Level Files: Wrapper vs Real Entrypoint

### Compatibility Wrappers (contain NO business logic — always delegate)

Every file in this category follows the same pattern:
```python
from ingestion.<channel>.run import *  # or enrichment / aggregation
if __name__ == "__main__":
    raise SystemExit(main())
```

| Root file | Delegates to | Why it exists |
|-----------|-------------|---------------|
| `fetch-rss.py` | `ingestion/rss/run.py` | cron CLI compat |
| `fetch-scrape.py` | `ingestion/web_scrape/run.py` | cron CLI compat |
| `fetch-twitter.py` | `ingestion/x/timeline.py` | cron CLI compat |
| `fetch-twitter-saved.py` | `ingestion/x/saved.py` | cron CLI compat |
| `fetch-wechat.py` | `ingestion/manual_links/wechat_seed.py` | cron CLI compat |
| `fetch-wechat-rss.py` | `ingestion/wechat_rss/run.py` | cron CLI compat |
| `fetch-wechat-exporter.py` | `ingestion/wechat_rss/exporter.py` | cron CLI compat |
| `fetch-douyin.py` | `ingestion/douyin/run.py` | cron CLI compat |
| `fetch-manual-links.py` | `ingestion/manual_links/run.py` | cron CLI compat |
| `fetch-media-transcripts.py` | `enrichment/media/run.py` | cron CLI compat |
| `score.py` | `aggregation/digest/score_stage.py` | push-digest.sh compat |
| `score-items.py` | `aggregation/digest/score_items.py` | push-digest.sh compat |
| `build-digest.py` | `aggregation/digest/build.py` | push-digest.sh compat |
| `summarize.py` | `aggregation/digest/summarize.py` | push-digest.sh compat (uses `globals().update()` due to name collision) |
| `check-quality.py` | `aggregation/digest/check_stage.py` | push-digest.sh compat |
| `quality-check.py` | `aggregation/digest/quality.py` | push-digest.sh compat |
| `ai-quality-check.py` | `aggregation/digest/ai_quality.py` | push-digest.sh compat |
| `archive-items.py` | `aggregation/digest/archive.py` | push-digest.sh compat |
| `finalize-local.py` | `aggregation/digest/finalize_local.py` | push-digest.sh compat |
| `html-to-long-image.py` | `aggregation/digest/html_to_long_image.py` | push-digest.sh compat |
| `send-artifacts.py` | `push-telegram.py` | push-digest.sh compat |

**Rule:** Never add business logic to wrapper files. All changes go in the folder-layer module.

### Real Pipeline Entrypoints (contain logic)

| File | Role |
|------|------|
| `fetch-all.sh` | Cron shell orchestrator; fetch stage |
| `push-digest.sh` | Daily shell orchestrator; aggregation + deliver |
| `fetch.py` | Stage 1 Python runner; fans out to all fetchers |
| `open-batch.py` | Opens a digest batch (moves files, emits BATCH_ID) |
| `push-telegram.py` | Telegram delivery with section/item selection logic |
| `generate-status.py` | Owner inbox dashboard HTML generator |

### Shared Library Modules (not entrypoints, not wrappers)

| File | Role |
|------|------|
| `lib.py` | Path constants, LLM calls, frontmatter, source loading |
| `digest_config.py` | Score thresholds, category order, source roles |
| `digest_events.py` | Event identity and grouping rules |
| `digest_text.py` | Text cleaning (HTML strip, release bullets) |

## Naming Conventions

**Files:**
- Ingestion adapters: `run.py` inside channel folder (plus `timeline.py`, `saved.py`, `exporter.py` for multi-entrypoint channels)
- Aggregation stage files: `<verb>_stage.py` or `<noun>.py` (e.g., `score_stage.py`, `build.py`)
- Root wrappers: `fetch-<channel>.py` (ingestion), bare stage name (`score.py`, `build-digest.py`) for aggregation — all use hyphens
- Test files: `test_<feature>.py`
- Contract docs: `CONTRACT.md` in each channel/enrichment/aggregation folder

**Directories:**
- Channel names use `snake_case` under `ingestion/` (e.g., `web_scrape`, `wechat_rss`, `manual_links`)
- Aggregation has a single `digest/` subdirectory under `aggregation/`
- Scripts use `snake_case` filenames with underscore separators

## Where to Add New Code

**New ingestion channel:**
1. Create `ingestion/<channel_name>/CONTRACT.md` — define boundary first
2. Create `ingestion/<channel_name>/run.py` — implement `main()` following the standard artifact schema
3. Create a root compatibility wrapper `fetch-<channel>.py` re-exporting from `run.py`
4. Add the wrapper to the `STAGES` list in `fetch.py`
5. Tests: `tests/test_ingestion_contracts.py` (contract) + `tests/test_ingestion_wrappers.py` (wrapper)

**New aggregation stage:**
1. Create `aggregation/digest/<stage>.py`
2. Create a root wrapper `<stage-name>.py` re-exporting from the module
3. Add wrapper to `STAGES` in `push-digest.sh` at the correct sequence position
4. Update `aggregation/digest/CONTRACT.md` entrypoint list

**New enrichment type:**
1. Create `enrichment/<concern>/CONTRACT.md` — define inputs/outputs/boundary
2. Create `enrichment/<concern>/run.py` — implement `main()`
3. Create root wrapper `fetch-<concern>.py`
4. Add to `fetch.py` STAGES if it runs in the fetch window, or handle separately

**New utility/ops script:**
- Place at repo root if it needs direct CLI access alongside existing ops tools
- Place in `scripts/` if it is workflow-graph, task-graph, or n8n tooling

**Shared helper code:**
- Pipeline-wide constants and utilities: `lib.py`
- Digest-specific configuration: `digest_config.py`
- Digest event logic: `digest_events.py`
- Digest text manipulation: `digest_text.py`

## Special Directories

**`~/park-io/inbox/unprocessed/`:**
- Purpose: Landing zone for raw ingestion artifacts (`<date>-<profile>.md`)
- Generated: Yes (by ingestion adapters at runtime)
- Committed: No (outside the repo, in `~/park-io/`)

**`~/park-io/inbox/processed/<batch-id>/`:**
- Purpose: Batch working directory created by `open-batch.py`
- Generated: Yes
- Committed: No

**`~/park-io/inbox/sent/`:**
- Purpose: Final delivered artifacts
- Generated: Yes
- Committed: No

**`logs/`:**
- Purpose: Runtime logs (`fetch-all.log`, `push-digest.log`) and lock file (`fetch.lock`)
- Generated: Yes
- Committed: No (gitignored)

**`.planning/`:**
- Purpose: GSD planning documents, phase plans, and codebase maps
- Generated: Partially (codebase maps are written by mapping agents)
- Committed: Yes

---

*Structure analysis: 2026-06-05*
