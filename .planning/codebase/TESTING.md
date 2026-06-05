# Testing Patterns

**Analysis Date:** 2026-06-05

## Test Framework

**Runner:**
- Plain Python executable test files under `tests/`; each `tests/test_*.py` exposes `test_` functions and includes an `if __name__ == "__main__"` runner
- Pytest-compatible shape is partially supported; `tests/test_cleaning.py` documents `python3 -m pytest tests/ -q`, but repo does not include `pytest.ini`, `pyproject.toml`, or dependency manifest
- Config: Not detected

**Assertion Library:**
- Built-in `assert` statements
- `unittest.mock.patch` used in `tests/test_llm_fallback.py`
- Temporary files created with `tempfile` in `tests/test_alerts.py`
- Dynamic module loading via `importlib.util.spec_from_file_location` for loading hyphenated scripts

**Run Commands:**
```bash
# From STATE.md Verification Baseline (2026-06-05)
python3 -m py_compile summarize.py digest_config.py lib.py quality-check.py fetch-douyin.py
for t in tests/test_*.py; do python3 "$t"; done
PARKIO_BATCH_ID=20260604 python3 build-digest.py
PARKIO_BATCH_ID=20260604 python3 finalize-local.py
PARKIO_BATCH_ID=20260604 PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py
python3 channel-health.py
```

**Current Status:**
- All 23 test files in `tests/` pass when run directly: `for t in tests/test_*.py; do python3 "$t"; done`
- Recent test additions: contract tests, ingestion wrapper tests, task graph tests, workflow graph tests, n8n export/import diff tests

## Test File Organization

**Location:**
- Tests centralized in `tests/`
- Root-level scripts imported via `importlib.util.spec_from_file_location` (handles kebab-case filenames)
- Folderized modules imported as regular Python modules

**Test Files (23 total):**
```
tests/
├── test_alerts.py                  # failure alerts + transcription retry semantics
├── test_bypass.py                  # score bypass for official/manual/media sources
├── test_channel_health.py          # DOWN/STALE/QUIET/NEW classification from logs
├── test_chinese_fallback.py        # suppress raw English in reader output
├── test_cleaning.py                # strip source/ingestion metadata from text
├── test_douyin_delivery.py         # delivery-vs-archival dedupe, late-first-seen fix
├── test_empty_x.py                 # empty/link-only X handling
├── test_finalize_local.py          # local artifact packaging (Markdown/HTML/PNG)
├── test_health_dashboard.py        # compact health dashboard rendering
├── test_ingestion_contracts.py     # CONTRACT.md presence + schema strictness
├── test_ingestion_wrappers.py      # root wrapper re-export + folderized module location
├── test_llm_fallback.py            # DeepSeek retry/failover + non-retryable fast-fail
├── test_media.py                   # media summary inclusion/exclusion rules
├── test_n8n_export.py              # n8n JSON export node/connection parity
├── test_n8n_import_diff.py         # drift detection: added/removed visual connections
├── test_reader_quality_contract.py # Phase 4 product-level regression lock
├── test_scrape_sitemap.py          # sitemap extraction + age-gate behavior
├── test_shorts.py                  # YouTube Shorts filtering
├── test_source_health.py           # false-green prevention for bridge failures
├── test_task_graph.py              # task graph validation, claim/complete semantics
├── test_thread_merge.py            # X conversation thread merge keys
├── test_titles.py                  # Chinese titles + truncation guard + stale template
└── test_workflow_graph.py          # workflow diagram validation + dry-run planning
```

## Test Structure

**Suite Organization:**
```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_behavior_name():
    assert production_function(input_value) == expected_value

if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)
```

**Patterns:**
- Keep tests self-running so verification baseline can use simple for-loop
- Keep tests deterministic and mostly offline; mock network calls
- Use fixed synthetic dates for date-sensitive logic (e.g., `TODAY = "2026-06-04"` in `test_douyin_delivery.py`)
- Use current local date only for alert recency tests (e.g., `test_alerts.py`)
- Test exact historical failures documented in GOTCHAS.md rather than broad snapshots

## Contract Tests

**Location:** `tests/test_ingestion_contracts.py`

**Coverage:**
- Verify all `CONTRACT.md` files exist under ingestion/enrichment/aggregation modules
- Verify each CONTRACT.md names its folder/boundary
- Verify ingestion schema JSON is parseable and strict (`additionalProperties: false`)
- Verify schema includes all channel types (rss, web_scrape, x, douyin, wechat_rss, etc.)
- Verify workflow spec YAML exists and declares `source_of_truth: repo`
- Verify workflow spec includes all channel/enrichment/aggregation workflow IDs

**Example test:**
```python
def test_contract_files_exist_and_name_boundaries():
    for rel in EXPECTED_CONTRACTS:
        path = ROOT / rel
        assert path.exists(), f"missing {rel}"
        text = path.read_text(encoding="utf-8")
        assert rel.rsplit("/", 1)[0] in text, rel
        assert "## Boundary" in text, rel
```

## Ingestion Wrapper Tests

**Location:** `tests/test_ingestion_wrappers.py`

**Coverage:**
- Verify root fetch wrappers re-export expected symbols (e.g., `fetch-rss.py` exports `main`, `parse_feed`, `fetch_youtube_fallback`)
- Verify folderized modules exist at expected paths
- Verify manual links uses folderized WeChat parser (from `ingestion/manual_links/wechat_seed.py`)

**Example:**
```python
def test_root_fetch_wrappers_reexport_expected_symbols():
    for filename, attrs in WRAPPERS.items():
        module = load_module(filename)
        for attr in attrs:
            assert hasattr(module, attr), f"{filename} missing {attr}"
```

## Reader Quality Contract Tests

**Location:** `tests/test_reader_quality_contract.py`

**Coverage (Phase 4 regression lock):**
- X title truncation guard: `summarize.x_title_looks_truncated(title, body)`
- Media publishability: transcript-backed, non-promo summaries only
- Active Douyin sources: loaded from config, respect `active` flag
- Quality gate blocks: `no_transcript`, `AI refusal markers`, raw English, source metadata, Markdown/HTML divergence

**Example:**
```python
def test_x_titles_reject_truncated_first_sentence_prefixes():
    cases = [
        ("Codex 昨晚上线的这个 Site 插件非",
         "Codex 昨晚上线的这个 Site 插件非常厉害。..."),
    ]
    for title, body in cases:
        assert summarize.x_title_looks_truncated(title, body), title
```

## Mocking

**Framework:** `unittest.mock.patch`

**Patterns:**
```python
# Mock LLM HTTP calls
with patch.object(lib, "LLM_PROVIDER", "deepseek"), \
        patch.object(lib, "LLM_FALLBACK_PROVIDER", "anthropic"), \
        patch("urllib.request.urlopen", fake_urlopen), \
        patch("time.sleep", lambda *_args: None):
    out = lib.llm_call("hello", max_tokens=20, retries=3, timeout=1)

# Mock file paths
ph.MEDIA_SUMMARIES = __import__("pathlib").Path(_write_json({
    "u1": {"status": "failed", "title": "柱子哥视频", "updated_at": f"{TODAY}T10:00:00"},
}))
```

**What to Mock:**
- LLM HTTP calls: never hit DeepSeek, CLIProxy, or Anthropic from unit tests
- Mutable file paths for stateful helpers (e.g., `test_alerts.py` replaces module paths with temp files)
- Time sleeping in retry loops

**What NOT to Mock:**
- Pure rendering, cleaning, routing, title, thread, health classification, or bypass logic
- Real `twitter-auth.env`, `~/park-io/secrets/*`, `~/park-io/inbox/*` (skip if not available)
- Parsing/extraction logic (assert directly against production functions)

## Fixtures and Factories

**Test Data:**
```python
def aweme(aid: str, date_str: str) -> dict:
    return {"aweme_id": aid, "create_time": _epoch(date_str)}

def _write_json(obj):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return path

def minimal_task(task_id, deps=None, status="todo"):
    return {
        "id": task_id, "title": task_id, "type": "implementation",
        "status": status, "dependencies": deps or [],
        "success_criteria": ["done"], "test_commands": ["true"],
    }
```

**Location:**
- Fixtures are local to each test file; no shared `conftest.py`
- Historical leak strings inline in `test_cleaning.py`
- WeChat bridge fixtures inline in `test_source_health.py`
- Synthetic tweet/event dicts inline in `test_thread_merge.py`, `test_empty_x.py`, `test_titles.py`
- Task graph fixtures inline in `test_task_graph.py`

## Coverage

**Requirements:** None enforced by tooling

**View Coverage:**
```bash
python3 -m coverage run -m pytest tests
python3 -m coverage report
```
- Coverage tooling not configured in repo; use only as ad-hoc check

## Test Types

**Unit Tests:**
- `test_bypass.py`: `summarize.bypasses_score()` + score outage invariants
- `test_cleaning.py`: `digest_text.consumer_text()`, `sanitize_product_text()`, `strip_source_meta()`
- `test_titles.py`: `summarize.has_chinese()`, title truncation, stale template prevention
- `test_llm_fallback.py`: `lib.llm_call()` retryability, non-retryable 401, DeepSeek thinking flags
- `test_shorts.py`: `lib.is_youtube_short()` URL + duration filtering

**Integration-Style Regression Tests:**
- `test_alerts.py`: `check-pipeline-health.py` + `fetch-media-transcripts.py` against temp state
- `test_source_health.py`: `source-health.py` classification of bridge failures
- `test_channel_health.py`: `channel-health.py` log parsing + feed freshness
- `test_scrape_sitemap.py`: `fetch-scrape.py` sitemap extraction + age gates
- `test_douyin_delivery.py`: Douyin delivery-vs-archival dedupe logic

**Contract/Product Tests:**
- `test_ingestion_contracts.py`: Boundary + schema strictness
- `test_ingestion_wrappers.py`: Root wrapper exports + folderized locations
- `test_reader_quality_contract.py`: Phase 4 product regression lock (x truncation, media, active sources, quality gates)
- `test_task_graph.py`: Graph validation, dependency cycles, claim/complete semantics
- `test_workflow_graph.py`: n8n diagram validation, dry-run planning, cycle detection
- `test_n8n_export.py`: Node + connection parity from task graph to n8n JSON
- `test_n8n_import_diff.py`: Drift detection for added/removed connections

**E2E Tests:**
- Not used as automated tests
- Manual verification: `open-batch.py` → `score.py` → `build-digest.py` → `check-quality.py` → `finalize-local.py`

## Common Patterns

**Dynamic Module Loading (hyphenated scripts):**
```python
import importlib.util
spec = importlib.util.spec_from_file_location("fetch_rss", ROOT / "fetch-rss.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
```

**Skip on Missing Optional Dependencies:**
```python
try:
    _spec.loader.exec_module(fd)
except Exception as exc:
    print(f"SKIP (cannot import fetch-douyin: {type(exc).__name__}: {exc})")
    sys.exit(0)
```

**Error Testing:**
```python
raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", hdrs=None, fp=None)
```
- Assert 401/400 errors fail fast without retry
- Assert DOWN vs QUIET classification from fetch errors
- Assert bridge connection refusal marks source as failed

**Date-Sensitive Testing:**
```python
TODAY = "2026-06-04"  # fixed synthetic date
def aweme(aid: str, date_str: str) -> dict:
    return {"aweme_id": aid, "create_time": _epoch(date_str)}

def test_late_first_seen_within_window_is_delivered():
    out = fd.awemes_to_deliver([aweme("2", "2026-06-03")], delivered_ids=set(), today_str=TODAY)
    assert ids(out) == ["2"]
```

## Quality Gates

**Deterministic Quality Gate (tests/test_reader_quality_contract.py):**
- Run `python3 check-quality.py` or `PARKIO_BATCH_ID=<batch> PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py`
- Blocks: raw English, source metadata, AI refusal markers, Telegram leaks, duplicate URLs, Markdown/HTML divergence
- Does NOT block: reader quality from transcripts (no transcript = no publish, but status is visible in health)

**AI Quality Gate:**
- `ai-quality-check.py` is second layer
- Non-blocking by default; use `PARKIO_STRICT_AI_QUALITY` to enforce
- Per GOTCHAS.md: deterministic first, AI second

## Files To Read Before Changing Tests

- `STATE.md`: Verification Baseline section + current phase
- `GOTCHAS.md`: Current regression contract
- `HANDOVER.md`: Operational context, infra actions, model choices
- Target production file + paired test file together (e.g., `quality-check.py` with `test_cleaning.py`, `test_titles.py`)
- `.planning/codebase/CONVENTIONS.md`: Code style + module patterns

---

*Testing analysis: 2026-06-05*
