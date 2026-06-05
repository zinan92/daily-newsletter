# Codebase Concerns

**Analysis Date:** 2026-06-05

---

## Root-Level .py Classification Table

> **Owner's primary question:** which root `.py` files are wrappers, which are active, and which are safe to delete?

All 20 wrapper targets were verified to exist. No broken wrappers detected.

### Wrappers (thin compatibility shims — all targets confirmed present)

| File | Classification | Re-export Target | Safe to Delete? | Note |
|------|---------------|-----------------|-----------------|------|
| `ai-quality-check.py` | WRAPPER | `aggregation/digest/ai_quality.py` | verify | Referenced by `tests/test_ingestion_wrappers.py` implicitly; check if any .sh uses it directly |
| `archive-items.py` | WRAPPER | `aggregation/digest/archive.py` | verify | In `push-digest.sh` STAGES list; NOT deletable until push-digest.sh is updated |
| `build-digest.py` | WRAPPER | `aggregation/digest/build.py` | verify | In `push-digest.sh` STAGES list; NOT deletable until push-digest.sh is updated |
| `check-quality.py` | WRAPPER | `aggregation/digest/check_stage.py` | verify | In `push-digest.sh` STAGES list; NOT deletable until push-digest.sh is updated |
| `fetch-douyin.py` | WRAPPER | `ingestion/douyin/run.py` | verify | Called via `fetch.py` subprocess; `tests/test_ingestion_wrappers.py` checks it |
| `fetch-manual-links.py` | WRAPPER | `ingestion/manual_links/run.py` | verify | Called via `fetch.py` subprocess; `tests/test_ingestion_wrappers.py` checks it |
| `fetch-media-transcripts.py` | WRAPPER | `enrichment/media/run.py` | verify | Called via `fetch.py` subprocess; `tests/test_ingestion_wrappers.py` checks it |
| `fetch-rss.py` | WRAPPER | `ingestion/rss/run.py` | verify | Called via `fetch.py`; also loaded via `importlib` in `onboard-source.py` and `onboard-baseline.py` |
| `fetch-scrape.py` | WRAPPER | `ingestion/web_scrape/run.py` | verify | Called via `fetch.py`; loaded via `importlib` in `backfill-claude-blog-library.py` |
| `fetch-twitter.py` | WRAPPER | `ingestion/x/timeline.py` | verify | Called via `fetch.py`; loaded via `importlib` in `onboard-source.py` and `onboard-baseline.py` |
| `fetch-twitter-saved.py` | WRAPPER | `ingestion/x/saved.py` | verify | Called via `fetch.py`; `tests/test_ingestion_wrappers.py` checks it |
| `fetch-wechat.py` | WRAPPER | `ingestion/manual_links/wechat_seed.py` | verify | Called via `fetch.py`; `tests/test_ingestion_wrappers.py` checks it |
| `fetch-wechat-exporter.py` | WRAPPER | `ingestion/wechat_rss/exporter.py` | verify | Called via `fetch.py`; `tests/test_ingestion_wrappers.py` checks it |
| `fetch-wechat-rss.py` | WRAPPER | `ingestion/wechat_rss/run.py` | verify | Called via `fetch.py`; `tests/test_ingestion_wrappers.py` checks it |
| `html-to-long-image.py` | WRAPPER | `aggregation/digest/html_to_long_image.py` | verify | Called by `aggregation/digest/build.py` via `ROOT / "html-to-long-image.py"` subprocess — actively needed |
| `quality-check.py` | WRAPPER | `aggregation/digest/quality.py` | verify | `GOTCHAS.md` lists it; `tests/test_ingestion_wrappers.py` checks it |
| `score.py` | WRAPPER | `aggregation/digest/score_stage.py` | verify | In `push-digest.sh` STAGES; in workflow graph JSON and YAML; NOT deletable |
| `score-items.py` | WRAPPER | `aggregation/digest/score_items.py` | verify | Called by `aggregation/digest/score_stage.py` via `ROOT / "score-items.py"` subprocess — actively needed |
| `summarize.py` | WRAPPER | `aggregation/digest/summarize.py` | verify | Called by `aggregation/digest/build.py` via `ROOT / "summarize.py"` subprocess — actively needed; uses `globals().update` + `sys.modules` trick |
| `finalize-local.py` | WRAPPER | `aggregation/digest/finalize_local.py` | verify | In `push-digest.sh` STAGES; `tests/test_finalize_local.py` loads it directly via `importlib`; NOT deletable |

**Key finding:** All 20 wrappers are still load-bearing. The `push-digest.sh` script references `score.py`, `build-digest.py`, `check-quality.py`, `archive-items.py`, `finalize-local.py` by name. `fetch.py` dispatches all fetch-* wrappers via subprocess. Three folder modules (`score_stage.py`, `build.py`) re-invoke root wrappers via `ROOT / "score-items.py"` and `ROOT / "summarize.py"` subprocesses, creating a wrapper→folder→wrapper chain that must be preserved until those folder modules are updated to call folder siblings directly.

---

### Active Entrypoints (hold real logic AND are invoked by live systems)

| File | Classification | What References It | Safe to Delete? | Note |
|------|---------------|-------------------|-----------------|------|
| `fetch.py` | ACTIVE-ENTRYPOINT | `fetch-all.sh` (sole consumer) | no | Dispatches all 10 fetch-* wrappers via subprocess; ~30 lines of real logic |
| `open-batch.py` | ACTIVE-ENTRYPOINT | `push-digest.sh`, `README.md`, `workflow/*.json/yaml` | no | Real batch-open logic; imports from `lib`; called first in every digest run |
| `generate-status.py` | ACTIVE-ENTRYPOINT | `push-digest.sh`, `README.md` | no | 1002 lines of real status-page generation logic; no folder counterpart |
| `channel-health.py` | ACTIVE-ENTRYPOINT | `tests/test_channel_health.py`, `README.md`, `aggregation/digest/summarize.py` (subprocess) | no | Contains truthful per-channel health logic; used by summarize.py at runtime |
| `source-health.py` | ACTIVE-ENTRYPOINT | `tests/test_source_health.py`, `workflow/*.json/yaml`, `README.md` | no | Fetch health tracking; no folder counterpart; referenced in workflow graph |
| `check-pipeline-health.py` | ACTIVE-ENTRYPOINT | `tests/test_alerts.py`, `tests/test_workflow_graph.py` | no | Daily pipeline alerter; contains real Telegram alert logic |
| `push-telegram.py` | ACTIVE-ENTRYPOINT | `send-artifacts.py` (subprocess call), `README.md`, `AGENTS.md`, `GOTCHAS.md` | no | ~490 lines of real Telegram push logic; called by `send-artifacts.py` |
| `send-artifacts.py` | ACTIVE-ENTRYPOINT | `push-digest.sh` (conditional STAGES), `README.md` | no | Thin but real: sets env, delegates to `push-telegram.py` |

---

### Shared Libraries (imported widely; not entrypoints but not deletable)

| File | Classification | What References It | Safe to Delete? | Note |
|------|---------------|-------------------|-----------------|------|
| `lib.py` | SHARED-LIB | 41+ import statements across root scripts, tests, and folder modules (`aggregation/digest/build.py`, `ingestion/rss/run.py`, etc.) | no | Core shared library: `llm_call`, `load_sources`, `batch_id`, `batch_artifact_paths`, `log`, `today`, `_load_secret`, etc. 800 lines. |
| `digest_config.py` | SHARED-LIB | `digest_events.py`, `digest_text.py`, `aggregation/digest/summarize.py`, `aggregation/digest/score_items.py`, `tests/test_bypass.py`, `tests/test_reader_quality_contract.py` | no | Source authority, category order, media source names config |
| `digest_events.py` | SHARED-LIB | `aggregation/digest/summarize.py`, `tests/test_thread_merge.py` | no | Event clustering + thread merge logic |
| `digest_text.py` | SHARED-LIB | `aggregation/digest/summarize.py`, `tests/test_cleaning.py` | no | Text cleaning utilities |

---

### Investigation Files — Manual/Maintenance Scripts (no live cron/shell references)

| File | Classification | What References It | Safe to Delete? | Note |
|------|---------------|-------------------|-----------------|------|
| `onboard-source.py` | ACTIVE-ENTRYPOINT | `README.md` (documented), `.planning/phases/parkio-07-CONTEXT.md` | no | Run manually to onboard new sources; loads fetch-rss/twitter via importlib |
| `onboard-baseline.py` | ACTIVE-ENTRYPOINT | `README.md` (implicit), `.planning/phases/parkio-07-CONTEXT.md` | no | Historical profile builder; loads fetch-rss/twitter via importlib |
| `backfill-claude-blog-library.py` | ACTIVE-ENTRYPOINT | `.planning/phases/parkio-07-CONTEXT.md` | verify | One-shot backfill; only reference is in planning docs, not live cron — low risk if unused |
| `build-index.py` | ACTIVE-ENTRYPOINT | Self-documents usage in its own docstring comment; no external references found | verify | Generates 慢学 AI profile index; only referenced inside the file itself; candidate for archival |
| `polish-douyin.py` | ACTIVE-ENTRYPOINT | Only self-referenced in docstring | verify | Post-processes Douyin transcripts; no external callers found; one-shot maintenance |
| `fix-asr-errors.py` | ACTIVE-ENTRYPOINT | Only self-referenced in docstring | verify | ASR error fixer for 慢学AI corpus; no external callers; likely one-shot |
| `refresh-twitter-auth.py` | ACTIVE-ENTRYPOINT | `generate-status.py` reads the output file `twitter-auth.env` | no | Needed to refresh Twitter cookies; `generate-status.py` checks for its output |
| `push-telegram.py` | ACTIVE-ENTRYPOINT | (see above table) | no | (repeated for clarity) |

---

### Safe-to-Delete Shortlist

**No file can be confidently marked "yes, delete now."** Reasons:

- All 20 wrappers remain live: `push-digest.sh` and `fetch.py` invoke them by name; folder modules invoke some via subprocess.
- The 4 SHARED-LIB files (`lib.py`, `digest_config.py`, `digest_events.py`, `digest_text.py`) are imported by folder modules — deleting them would break `aggregation/digest/summarize.py` immediately.
- Maintenance scripts (`build-index.py`, `fix-asr-errors.py`, `polish-douyin.py`, `backfill-claude-blog-library.py`) have no live cron callers but may be needed on-demand.

**Candidates for eventual deletion (after prerequisite work is done):**

| File | Prerequisite Before Deleting |
|------|------------------------------|
| All 20 WRAPPER files | Update `push-digest.sh`, `fetch.py`, and folder module subprocesses to call folder paths directly |
| `score-items.py` wrapper | Update `aggregation/digest/score_stage.py` to import `score_items` directly instead of via subprocess |
| `summarize.py` wrapper | Update `aggregation/digest/build.py` to import `summarize.main` directly |
| `html-to-long-image.py` wrapper | Update `aggregation/digest/build.py` subprocess call |
| `build-index.py` | Confirm it has been run and output is up to date; archive |
| `fix-asr-errors.py` | Confirm corpus cleanup is complete; archive |
| `polish-douyin.py` | Confirm corpus polishing is complete; archive |
| `backfill-claude-blog-library.py` | Confirm backfill is complete; archive |

---

## Tech Debt

**Wrapper-to-folder-to-wrapper subprocess chains:**
- Issue: `aggregation/digest/score_stage.py` invokes `ROOT / "score-items.py"` via subprocess (a root wrapper), which then re-imports `aggregation/digest/score_items.py`. Similarly `aggregation/digest/build.py` calls `ROOT / "summarize.py"` and `ROOT / "html-to-long-image.py"`.
- Files: `aggregation/digest/score_stage.py`, `aggregation/digest/build.py`
- Impact: Extra subprocess overhead; the "folderization" refactor is incomplete — folder modules still delegate back to root wrappers instead of calling folder siblings directly.
- Fix approach: Replace `subprocess.run([sys.executable, str(ROOT / "score-items.py")])` with a direct `from aggregation.digest.score_items import main; main()` call pattern.

**No `__init__.py` files in any folder package:**
- Issue: `aggregation/`, `aggregation/digest/`, `ingestion/`, `enrichment/` have no `__init__.py`. Imports work only because each module manually prepends `REPO_ROOT` to `sys.path`.
- Files: All modules under `aggregation/`, `ingestion/`, `enrichment/`
- Impact: Not proper Python packages; tools like mypy, pytest import discovery, and IDE navigation may behave unexpectedly. The sys.path manipulation is fragile if the repo is installed or used from a non-root working directory.
- Fix approach: Add `__init__.py` to each package directory OR convert to proper installable package with `pyproject.toml`.

**`lib.py` is a 800-line monolith with no folder counterpart:**
- Issue: All shared utilities (`llm_call`, `load_sources`, `batch_id`, `_load_secret`, etc.) live in a single root file. Folder modules must import from the root-level `lib.py` breaking the layered folder design.
- Files: `lib.py`, all folder modules that `from lib import ...`
- Impact: Can't be moved without updating 41+ import sites. Blocks clean separation of layers.
- Fix approach: Split into `contracts/lib_paths.py`, `contracts/lib_llm.py`, etc. as the refactor matures.

**`digest_config.py`, `digest_events.py`, `digest_text.py` not yet folderized:**
- Issue: These shared modules remain at root and are imported by `aggregation/digest/summarize.py` directly from root. They are referenced in `README.md` as root-level files.
- Files: `digest_config.py`, `digest_events.py`, `digest_text.py`
- Impact: Same layering violation as `lib.py`. Blocks clean root cleanup.
- Fix approach: Move to `aggregation/digest/` or a new `shared/` folder; add re-export wrappers at root if needed.

**`summarize.py` wrapper uses `sys.modules` monkey-patch:**
- Issue: `summarize.py` does `sys.modules[__name__] = _impl` after `globals().update(...)`. This is unusual and may confuse importers or test frameworks.
- Files: `summarize.py`
- Impact: Works in practice but is fragile — any code importing `summarize` as a module may get surprising behavior. `finalize-local.py` uses a different manual delegation pattern.
- Fix approach: Standardize wrapper pattern to pure `from aggregation.digest.summarize import *` like the other wrappers.

---

## Refactor Divergence Risks

**Folder modules calling root wrappers by path (divergence chain):**
- `aggregation/digest/score_stage.py` → `ROOT/"score-items.py"` → `aggregation/digest/score_items.py`
- `aggregation/digest/build.py` → `ROOT/"summarize.py"` → `aggregation/digest/summarize.py`
- `aggregation/digest/build.py` → `ROOT/"html-to-long-image.py"` → `aggregation/digest/html_to_long_image.py`
- `aggregation/digest/summarize.py` → subprocess `ROOT/"channel-health.py"` (root-only, no folder counterpart)
- Risk: If root wrappers diverge from folder modules (e.g. someone edits the root file thinking it's the real implementation), the divergence will be silent — the subprocess call just runs a different version.

**`onboard-source.py` and `onboard-baseline.py` load wrappers via `importlib`:**
- These load `fetch-rss.py`, `fetch-twitter.py` (root wrappers) via `importlib.util.spec_from_file_location`. If wrappers are deleted but `onboard-*.py` scripts are not updated, onboarding breaks silently.
- Files: `onboard-source.py`, `onboard-baseline.py`

**`aggregation/digest/build.py` imports from root `lib` (not a folder module):**
- `from lib import ROOT, batch_artifact_paths` — this is intentional but means the folder module is coupled to the root-level shared library.

---

## Known Issues & Stale State

**`Ray在思考` WeChat source is frozen (STALE since 2026-03-23):**
- `HANDOVER.md` line 177: "wewe-rss subscription `MP_WXS_3226075849` is frozen since 2026-03-23"
- `HANDOVER.md` line 200: "`Ray在思考` remains STALE, intentionally low priority"
- `digest_config.py` line 267 lists it in a special category
- Impact: Source produces no items; health checks show STALE; no action needed unless owner wants to remove the source

**`PARKIO_SKIP_SEND=1` is the production default:**
- `push-digest.sh` line 47: `PARKIO_SKIP_SEND="${PARKIO_SKIP_SEND:-1}"` — Telegram push is disabled by default
- `send-artifacts.py` is only added to STAGES when `PARKIO_SKIP_SEND` is explicitly set to `0`
- Impact: Digest is built locally but never sent to Telegram unless manually re-enabled; owner must consciously flip this flag

---

## Fragile External Auth Dependencies

**Twitter/X cookie auth (`twitter-auth.env`):**
- `refresh-twitter-auth.py` extracts `auth_token` and `ct0` cookies from a locally-installed `twitter-cli` Python package
- `generate-status.py` checks for `twitter-auth.env` existence
- `ingestion/x/timeline.py` and `ingestion/x/saved.py` consume these cookies
- Fragility: Cookies expire without notice; `refresh-twitter-auth.py` requires a logged-in desktop session and a specific Python binary at `/Users/wendy/.local/share/uv/tools/twitter-cli/bin/python`
- No automated re-auth; manual intervention required on each expiry

**WeWe RSS bridge (WeChat public account feeds):**
- `channel-health.py`, `check-pipeline-health.py`, `generate-status.py` all check for `localhost:4000` reachability
- Requires Colima (Docker-compatible VM) to be running locally
- Fragility: If Colima is stopped, all WeChat RSS sources go STALE silently; bridge may need manual WeChat re-login when session expires
- `check-pipeline-health.py` sends Telegram alert when bridge is unreachable (gotcha #23 mitigated)

**YouTube cookies (`~/park-io/secrets/youtube-cookies.txt`):**
- Required for `yt-dlp` video download and transcription
- `README.md` line 148: cookie expiry triggers "Sign in to confirm you're not a bot" — videos fail to download
- No automated renewal; manual browser export required

---

## Security Considerations

**`twitter-auth.env` contains live session tokens:**
- Risk: File written to repo root by `refresh-twitter-auth.py`; if accidentally committed, Twitter session is compromised
- `refresh-twitter-auth.py` line 41 writes a warning comment "Do not commit" in the file header
- Current mitigation: `.gitignore` should exclude it (not verified in this audit); `README.md` warns against committing
- Recommendation: Confirm `twitter-auth.env` is in `.gitignore`

**Secrets loaded via `lib._load_secret()`:**
- Reads from env var or `~/park-io/secrets/<filename>`; never hardcoded
- Pattern is consistent across `push-telegram.py`, `lib.py`
- Mitigation adequate; no secrets found in source code

---

## Test Coverage Gaps

**Health scripts lack unit tests for core logic paths:**
- `generate-status.py` (1002 lines) has no dedicated test file; `tests/test_health_dashboard.py` tests indirectly
- `check-pipeline-health.py` is tested only for alert triggering, not for pipeline state logic

**Maintenance scripts are untested:**
- `polish-douyin.py`, `fix-asr-errors.py`, `build-index.py`, `backfill-claude-blog-library.py` have no test coverage
- Risk: Silent breakage on corpus structure changes; Low priority if these are one-shot scripts

**`onboard-source.py` and `onboard-baseline.py` have no tests:**
- Both load wrapper scripts via `importlib` dynamically; a wrapper deletion would cause silent test gap

---

## Scaling Limits

**`lib.py` `load_sources()` reads `~/park-io/sources.md` on every call:**
- No caching; every script call re-parses the markdown table
- Current source count is small; at ~200+ sources this will become noticeable

**`generate-status.py` (1002 lines) runs synchronously at end of every digest:**
- Makes HTTP probes to WeWe RSS, checks twitter-auth.env, reads all log files
- No timeout guard on HTTP probes (beyond what `urllib.request` provides)

---

*Concerns audit: 2026-06-05*
