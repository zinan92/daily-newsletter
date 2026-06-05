# Coding Conventions

**Analysis Date:** 2026-06-05

## Naming Patterns

**Files:**
- Root compatibility wrappers: kebab-case, non-executable in some cases: `fetch-*.py` (RSS, scrape, Twitter, Twitter saved, Douyin, WeChat RSS/exporter, manual links), `score-items.py`, `build-digest.py`, `check-quality.py`, `finalize-local.py`, `html-to-long-image.py`
- Folderized core modules under `ingestion/`, `enrichment/`, `aggregation/`: `run.py` (main entrypoint per channel/module)
- Channel-specific utilities: `timeline.py` (X timeline), `saved.py` (X saved), `exporter.py` (WeChat exporter), `wechat_seed.py` (manual links WeChat parser)
- Aggregation stages: `score_stage.py`, `score_items.py`, `build.py`, `summarize.py`, `check_stage.py`, `quality.py`, `ai_quality.py`, `archive.py`, `finalize_local.py`, `html_to_long_image.py`
- Shared libraries: `lib.py`, `digest_config.py`, `digest_text.py`, `digest_events.py` (lowercase, descriptive)
- Test files: `test_*.py` (always lowercase, import root scripts by filepath)
- Contract specs: `CONTRACT.md` under each module folder, plus `contracts/ingestion-artifact.schema.json` (JSON schema)

**Functions:**
- snake_case universally: `load_sources()`, `parse_feed()`, `is_youtube_short()`, `awemes_to_deliver()`, `item_from_tweet()`, `validate_graph()`, `ready_tasks()`, `claim_task()`
- Internal helpers prefixed with `_`: `_load_secret()`, `_llm_endpoint_config()`, `_deepseek_is_v4()`, `_parse_first_md_table()`
- Descriptive action verbs: `fetch_url()`, `parse_date()`, `record_usage()`, `write_source_output()`, `write_health_alert()`, `dry_run_plan()`

**Variables:**
- Constants: UPPERCASE: `ROOT`, `PARKIO`, `SOURCES_PATH`, `STATE_PATH`, `INBOX`, `LOGS`, `PROCESSED_DIR`, `DEEPSEEK_ENDPOINT`, `YOUTUBE_MIN_SECONDS`
- Module-level accumulation state: `_USAGE = {...}` (token tracking), `_LLM_FAILURES = [...]` (failure recording)
- Loop/local vars: snake_case: `items`, `entries`, `headers`, `response`, `last_exc`, `payload`, `awemes`, `tasks`

**Types:**
- Type hints used throughout: `def fetch_url(url: str, timeout=30)`, `def llm_call(prompt: str, max_tokens: int = 2000, *, retries: int = 3, timeout: int = 120) -> str`
- Union types for optional values: `list[str] | None`, `dict | None`, `Exception | None`
- Type comments in older sections: `# type: dict` where inline hints not used

**Dicts/Data structures:**
- Source records: `{"name": str, "platform": str, "profile_id": str, "url": str, "active": str, "authority": int, ...}`
- Item dicts follow contract schema (`contracts/ingestion-artifact.schema.json`): `{"id": str, "title": str, "url": str, "published": str, "content": str, "content_kind": str, "metadata": dict}`
- Score records: `{"relevance_score": int, "line_fit": list[str], "tags": list[str], "reason": str}`
- Task records (task graph): `{"id": str, "title": str, "type": str, "status": str, "dependencies": list[str], "success_criteria": list[str]}`
- Workflow node records (n8n export): `{"id": str, "name": str, "type": str, "command": str, "inputs": list, "outputs": list}`

## Code Style

**Formatting:**
- No explicit formatter configured (no ruff.toml, .black, autopep8 config)
- Observed style: 4-space indentation, max ~100-120 characters per line
- Import statements: stdlib, then blank, then local/relative modules
- Docstrings: single-line for simple functions, multi-line with `"""` for complex behavior
- Type hints preferred throughout (Python 3.10+)

**Linting:**
- No linter configuration found (.flake8, ruff.toml, etc.)
- `.ruff_cache/` exists, suggesting ruff runs locally
- No enforced gate in test/CI

## Import Organization

**Order (observed pattern):**
1. System imports: `asyncio`, `json`, `os`, `re`, `sys`, `time`, `urllib.*`, `subprocess`
2. Standard library time/path: `from datetime import datetime, timezone, timedelta`, `from pathlib import Path`
3. Blank line
4. Local/relative imports: `from lib import (...)`, `from digest_config import ...`, `from ingestion.x.timeline import ...`
5. Conditional/optional imports: wrapped in try/except for runtime dependencies (Douyin SDK, `content_downloader`, `task_graph_lib`)

**Path Aliases:**
- None used; all imports are module names or relative paths
- Root detection pattern: `ROOT = Path(__file__).resolve().parents[N]`, then `sys.path.insert(0, str(ROOT))` to enable imports
- Example: `aggregation/digest/score_items.py` uses `REPO_ROOT = Path(__file__).resolve().parents[2]`
- Test pattern: `ROOT = Path(__file__).resolve().parents[1]`, `sys.path.insert(0, str(ROOT))`

## Error Handling

**Patterns:**
- Custom exception classes:
  - `LLMUnavailable(RuntimeError)`: raised when endpoint unreachable after retries (transient)
  - `LLMNonRetryable(RuntimeError)`: raised for config/request errors (fast fail, no retry)
  - `TaskGraphError(ValueError)`: raised for task graph validation/execution failures
  - `WorkflowGraphError(ValueError)`: raised for workflow diagram validation failures
- All exception handling uses `try/except` blocks; broad catches only for optional/runtime dependencies
- **Never silent swallowing:** errors either re-raised, logged, or explicitly handled with fallback
- Health alerts via `write_health_alert()` — failures recorded to disk, never raise

## Logging

**Framework:** `log()` helper in `lib.py` + file-based logs

**log() signature:**
- `log(source: str, msg: str)`: appends to per-day logfile under `logs/`, also prints
- Example: `log("fetch-rss", "  skip YouTube short: ...")`

**Patterns:**
- Summary at start: `log(script_name, "Starting...")`
- Per-item filtering: `log(script_name, f"  skip {reason}")`
- Retry/error: `log(script_name, f"Retry {n}/{retries}: {err}")`
- Summary at end: new count, error count, processed count
- No debug/info/warn levels; all output is INFO-equivalent

**Health alerts (separate from logs):**
- `write_health_alert(summary: str, details: list[str] | None = None) -> bool`
- Used for observable failures (transcription failed, source DOWN, scoring outage)
- Written to `~/park-io/inbox/health-alerts.md`, newest first
- Never raises

## Comments

**When to Comment:**
- Docstrings on public functions: describe inputs, outputs, side effects
- Algorithmic intent: why workarounds exist (YouTube fallback, DeepSeek thinking reasoning)
- External references: API quirks, platform behavior ("Owner wants long videos only — drop Shorts at ingestion")
- Disabled/suppressed behavior: `# pragma: no cover - optional runtime dependency`
- Product invariants tied to GOTCHAS.md or HANDOVER.md

## Function Design

**Size:** Under 80 lines typical; many under 30
- Short: `fetch_url()` (6 lines), `is_youtube_short()` (17 lines), `published_local_date()` (8 lines)
- Medium: `parse_feed()` (40+ lines, complex XML/Atom), `_llm_call_provider()` (35 lines, retry)
- Long: `summarize.py main()` orchestrates whole digest stage

**Parameters:**
- Use keyword-only for options: `def llm_call(prompt: str, max_tokens: int = 2000, *, retries: int = 3, timeout: int = 120)`
- Defaults for common optional: `timeout=30`, `retries=3`, `max_len=72`
- Positional for essential; keyword-only for optional/config

## Module Design

**Exports:**
- Root compatibility wrappers re-export key functions from folderized equivalents
- Example: `fetch-rss.py` defines `main()` and re-exports `parse_feed()`, `fetch_url()`
- Actual implementation in `ingestion/rss/run.py`
- Shared utilities in `lib.py` — single definition, imported by all

**Contract-First Pattern:**
- Every ingestion channel exports items matching `contracts/ingestion-artifact.schema.json`
- `CONTRACT.md` defines boundaries under each module folder
- Schema enforced by tests: `tests/test_ingestion_contracts.py`

## Compatibility Wrapper Pattern

**Why:**
- Root scripts remain public interface (backward compatible)
- Folderized modules own channel/stage logic
- Tests verify both layers work together

**Implementation:**
- Root script: minimal CLI entrypoint, imports and calls folderized module
- Folderized module: `run.py` with actual implementation
- Root script re-exports helper functions for backward compat (tested in `tests/test_ingestion_wrappers.py`)

## Environment Configuration

**Env vars (from lib.py, never hardcoded):**
- LLM: `PARKIO_LLM_PROVIDER` (default "deepseek"), `PARKIO_LLM_FALLBACK_PROVIDER` (default "anthropic")
- DeepSeek: `PARKIO_DEEPSEEK_ENDPOINT`, `PARKIO_DEEPSEEK_MODEL`, `PARKIO_DEEPSEEK_THINKING`, `PARKIO_DEEPSEEK_MAX_OUTPUT`
- Anthropic: `PARKIO_CLIPROXY_ENDPOINT`, `PARKIO_CLIPROXY_MODEL`
- YouTube: `PARKIO_YOUTUBE_MIN_SECONDS` (default 90)
- Batch control: `PARKIO_BATCH_ID`, `PARKIO_SKIP_AI_QUALITY`, `PARKIO_RESCORE_CONTEXT`, `PARKIO_REFETCH_TODAY`

**Secrets (from ~/park-io/secrets/, never in repo):**
- `deepseek-key`, `cliproxy-key`, `telegram-bot-token`, `telegram-chat-id`
- Load via `_load_secret(env_name: str, secret_filename: str) -> str`

---

*Convention analysis: 2026-06-05*
