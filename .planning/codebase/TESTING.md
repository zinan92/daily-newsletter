# Testing Patterns

**Analysis Date:** 2026-06-04

## Test Framework

**Runner:**
- Plain Python executable test files under `tests/`; each `tests/test_*.py` exposes `test_` functions and usually includes an `if __name__ == "__main__"` runner.
- Pytest-compatible shape is partially supported; `tests/test_cleaning.py` documents `python3 -m pytest tests/ -q`, but the repo does not include `pytest.ini`, `pyproject.toml`, or a dependency manifest.
- Config: Not detected.

**Assertion Library:**
- Built-in `assert` statements.
- `unittest.mock.patch` is used in `tests/test_llm_fallback.py`.
- Temporary files are created with `tempfile` in `tests/test_alerts.py`.

**Run Commands:**
```bash
for t in tests/test_*.py; do python3 "$t"; done
python3 -m py_compile summarize.py digest_config.py lib.py quality-check.py fetch-douyin.py
PARKIO_BATCH_ID=20260604 PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py
python3 channel-health.py
python3 check-pipeline-health.py
```

**Current Verification:**
- `for t in tests/test_*.py; do python3 "$t"; done` passes in the live repo on 2026-06-04.
- The full loop prints one expected failover log from `tests/test_llm_fallback.py` while still passing: primary `deepseek` transient failure falls back to `anthropic`.

## Test File Organization

**Location:**
- Tests are centralized in `tests/` and import root-level scripts by injecting the repo root into `sys.path`.
- Hyphenated production scripts are imported via `importlib.util.spec_from_file_location`, e.g. `tests/test_channel_health.py` loads `channel-health.py`, `tests/test_douyin_delivery.py` loads `fetch-douyin.py`, and `tests/test_source_health.py` loads `source-health.py`.

**Naming:**
- Test files use `tests/test_<area>.py`.
- Test functions use `test_<behavior>()`.
- Tests are behavior/regression named, not implementation named: examples include `test_late_first_seen_within_window_is_delivered` in `tests/test_douyin_delivery.py` and `test_bridge_connection_refused_is_failed` in `tests/test_source_health.py`.

**Structure:**
```text
tests/
├── test_alerts.py              # failure alerts + retryable transcription failures
├── test_bypass.py              # score bypass for official/manual/media/curated sources
├── test_channel_health.py      # DOWN/STALE/QUIET/NEW classification
├── test_chinese_fallback.py    # suppress raw English in reader output
├── test_cleaning.py            # strip source/ingestion metadata from consumer text
├── test_douyin_delivery.py     # delivery-vs-archival dedupe
├── test_empty_x.py             # empty/link-only X handling
├── test_health_dashboard.py    # compact digest health dashboard rendering
├── test_llm_fallback.py        # DeepSeek retry/failover behavior
├── test_media.py               # media summary inclusion/exclusion
├── test_scrape_sitemap.py      # scrape sitemap extraction and age gates
├── test_shorts.py              # YouTube Shorts filtering
├── test_source_health.py       # source-health false-green prevention
├── test_thread_merge.py        # X conversation/thread merge keys
└── test_titles.py              # Chinese titles and stale-template guard
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
    sys.exit(1 if failed else 0)
```

**Patterns:**
- Keep tests self-running so `AGENTS.md` can use `for t in tests/test_*.py; do python3 "$t"; done` without pytest.
- Keep tests deterministic and mostly offline; mock network calls in `tests/test_llm_fallback.py`.
- Use fixed synthetic dates for date-sensitive logic where possible, e.g. `TODAY = "2026-06-04"` in `tests/test_douyin_delivery.py`.
- Use current local date only for alert recency tests where the production code also uses `today()`, e.g. `tests/test_alerts.py`.
- Test exact historical failures documented in `GOTCHAS.md` rather than broad snapshots.

## Mocking

**Framework:** `unittest.mock.patch`

**Patterns:**
```python
with patch.object(lib, "LLM_PROVIDER", "deepseek"), \
        patch.object(lib, "LLM_FALLBACK_PROVIDER", "anthropic"), \
        patch("urllib.request.urlopen", fake_urlopen), \
        patch("time.sleep", lambda *_args: None):
    out = lib.llm_call("hello", max_tokens=20, retries=3, timeout=1)
```

**What to Mock:**
- Mock LLM HTTP calls in `tests/test_llm_fallback.py`; never hit DeepSeek, CLIProxy, or Anthropic from unit tests.
- Mock mutable file paths for stateful helpers, e.g. `tests/test_alerts.py` replaces `check-pipeline-health.py` module paths with temporary JSON files.
- Mock time sleeping when testing retry loops.

**What NOT to Mock:**
- Do not mock pure rendering, cleaning, routing, title, thread, health classification, or score-bypass logic; assert directly against `summarize.py`, `digest_text.py`, `digest_events.py`, `source-health.py`, and `channel-health.py`.
- Do not rely on real `twitter-auth.env`, `~/park-io/secrets/*`, `~/park-io/inbox/*`, or live feeds in regression tests.

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
```

**Location:**
- Fixtures are local to each test file; there is no shared `tests/conftest.py`.
- Historical leak strings live inline in `tests/test_cleaning.py`.
- WeChat bridge fixture rows live inline in `tests/test_source_health.py`.
- Synthetic tweet and event dictionaries live inline in `tests/test_thread_merge.py`, `tests/test_empty_x.py`, and `tests/test_titles.py`.

## Coverage

**Requirements:** None enforced by tooling.

**View Coverage:**
```bash
python3 -m coverage run -m pytest tests
python3 -m coverage report
```
- Coverage tooling is not configured in the repo; install/use it only as an ad hoc check.

## Test Types

**Unit Tests:**
- Use `tests/test_bypass.py` for `summarize.bypasses_score()` and score outage invariants.
- Use `tests/test_cleaning.py` for `digest_text.consumer_text()`, `sanitize_product_text()`, and `strip_source_meta()`.
- Use `tests/test_titles.py` for `summarize.has_chinese()`, title truncation guards, and stale template prevention.
- Use `tests/test_llm_fallback.py` for `lib.llm_call()` retryability, non-retryable 401 behavior, and DeepSeek thinking flags.

**Integration-Style Regression Tests:**
- Use `tests/test_alerts.py` for `check-pipeline-health.py` plus `fetch-media-transcripts.py` retry behavior against temp state files.
- Use `tests/test_source_health.py` for `source-health.py` classification of WeChat bridge failures.
- Use `tests/test_channel_health.py` for `channel-health.py` log parsing and feed freshness states.
- Use `tests/test_scrape_sitemap.py` for `fetch-scrape.py` sitemap extraction and age-gate behavior.

**E2E Tests:**
- Not used as automated tests.
- Manual pipeline verification is documented in `README.md` and `HANDOVER.md`: open a batch with `open-batch.py`, score with `score.py`, build with `build-digest.py`, gate with `check-quality.py`, archive with `archive-items.py`, and finalize with `finalize-local.py`.

## Common Patterns

**Async Testing:**
```python
_spec = importlib.util.spec_from_file_location("fetch_douyin", os.path.join(_ROOT, "fetch-douyin.py"))
fd = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(fd)
except Exception as exc:
    print(f"SKIP (cannot import fetch-douyin: {type(exc).__name__}: {exc})")
    sys.exit(0)
```
- `tests/test_douyin_delivery.py` tolerates missing optional Douyin runtime dependencies by exiting success after a clear SKIP message.

**Error Testing:**
```python
raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", hdrs=None, fp=None)
```
- `tests/test_llm_fallback.py` asserts 401/400-style configuration errors fail fast and do not fall back.
- `tests/test_channel_health.py` asserts fetch errors classify as `DOWN`, not `QUIET`.
- `tests/test_source_health.py` asserts a WeChat bridge connection refusal is `failed`, even if `last_fetch` is stamped for today.

## Quality Gates

**Deterministic Quality Gate:**
- Run `python3 check-quality.py` or `PARKIO_BATCH_ID=<batch> PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py`.
- `check-quality.py` delegates to `quality-check.py`.
- `quality-check.py` blocks reader-facing output containing raw English body text, source metadata, AI refusal artifacts, Telegram marker leaks, duplicate visible URLs, missing push markers, and Markdown/HTML heading divergence.

**AI Quality Gate:**
- `ai-quality-check.py` is a second review layer.
- The AI layer is non-blocking by default; make it blocking with `PARKIO_STRICT_AI_QUALITY`.
- Use deterministic checks first. `GOTCHAS.md` states quality gate is deterministic first, AI second.

## Files To Read Before Changing Tests

- Read `AGENTS.md` for the required regression command and workflow invariants.
- Read `GOTCHAS.md` for the current regression contract.
- Read `HANDOVER.md` for current operational state, including local-only finalize behavior and outstanding infra actions.
- Read the target production file and its paired test file together, e.g. `quality-check.py` with `tests/test_cleaning.py` and `tests/test_chinese_fallback.py`.

---

*Testing analysis: 2026-06-04*
