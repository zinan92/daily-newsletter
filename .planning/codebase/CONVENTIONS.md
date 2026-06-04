# Coding Conventions

**Analysis Date:** 2026-06-04

## Naming Patterns

**Files:**
- Use flat, top-level CLI scripts for pipeline stages: `fetch.py`, `score.py`, `build-digest.py`, `quality-check.py`, `archive-items.py`, `finalize-local.py`.
- Use kebab-case for executable scripts and shell entrypoints: `fetch-manual-links.py`, `fetch-twitter-saved.py`, `score-items.py`, `push-digest.sh`.
- Use snake_case for reusable import modules: `lib.py`, `digest_config.py`, `digest_events.py`, `digest_text.py`.
- Use `tests/test_<topic>.py` for regression tests: `tests/test_bypass.py`, `tests/test_cleaning.py`, `tests/test_llm_fallback.py`.
- Use `prompts/<verb>-<domain>.md` for prompt files: `prompts/summarize-blogs.md`, `prompts/summarize-tweets.md`, `prompts/digest-intro.md`.

**Functions:**
- Use snake_case for functions: `load_sources()`, `profile_id_for_source()`, `write_source_output()`, `processed_batch_dir()`, `batch_artifact_paths()`.
- CLI scripts should expose a `main()` function and finish with `if __name__ == "__main__": raise SystemExit(main())` when returning status codes, as in `build-digest.py` and `fetch-manual-links.py`.
- Helper functions should name the domain object they operate on: `source_for_article()`, `save_independent_article()`, `render_manual_links()`, `archive_item()`.
- Predicate helpers should read as booleans: `is_youtube_short()`, `bypasses_score()`, `bad_llm_text()`, `item_is_today()`.

**Variables:**
- Use uppercase module constants for paths, thresholds, regexes, and policy lists: `PARKIO`, `SOURCES_PATH`, `PROCESSED_DIR`, `SCORE_THRESHOLD`, `BAD_PATTERNS`, `WECHAT_URL_RE`.
- Use short local names only in tight loops or local transformations: `src`, `it`, `fm`, `dt`.
- Use explicit state keys for JSON-backed state, for example `manual-links` in `fetch-manual-links.py`.
- Keep path values as `pathlib.Path` objects until rendering or JSON serialization.

**Types:**
- Use built-in generic type annotations where useful: `list[dict]`, `dict[str, list[dict]]`, `tuple[Path, Path, Path]`.
- Keep markdown/frontmatter records as simple dictionaries, not dataclasses, because the pipeline reads/writes JSON and markdown frontmatter directly.
- Use custom exceptions only where they communicate operational behavior, as with `LLMUnavailable` and `LLMNonRetryable` in `lib.py`.

## Code Style

**Formatting:**
- No formatter config was detected in the repo root.
- Follow existing Python style: 4-space indentation, module docstring at top, imports after docstring, constants near top, functions grouped by domain.
- Keep lines readable and pragmatic; existing files often use long constant lists and explicit regex definitions.
- Preserve UTF-8 Chinese text in docs, prompts, and reader-facing strings where the product requires Chinese output.

**Linting:**
- No `.eslintrc`, `.prettierrc`, `eslint.config.*`, `biome.json`, or visible Ruff config was detected.
- `.ruff_cache/` exists, so Ruff has been run locally, but rules are not declared in this repo.
- Do not introduce lint-only churn across the flat scripts without an explicit task.

**Shell Style:**
- Use `#!/usr/bin/env bash` and `set -uo pipefail`, as in `fetch-all.sh` and `push-digest.sh`.
- Resolve `SCRIPT_DIR`, `cd` into it, and write logs under `logs/`.
- Use timestamp helper `ts() { date '+%F %T'; }` for runtime logs.
- Avoid failing the whole fetch run on one fetcher failure unless the stage contract requires it; `fetch-all.sh` logs nonzero stage exits.

## Import Organization

**Order:**
1. Standard library imports: `json`, `os`, `re`, `sys`, `subprocess`, `urllib`, `datetime`, `pathlib`.
2. Local shared modules: `from lib import ...`, `from digest_config import ...`, `from digest_events import ...`, `from digest_text import ...`.
3. Lazy or optional imports inside functions when needed to avoid cycles or optional dependency failures, as in `digest_config.active_douyin_source_names()` and `fetch-manual-links.py load_fetch_wechat()`.

**Path Aliases:**
- No Python package alias system is used.
- Tests prepend the repo root to `sys.path` with `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`.
- Scripts import local modules directly by filename module name, for example `import summarize` or `from lib import ROOT`.

**Dependency Boundaries:**
- Put repo/Park-IO path constants and shared IO in `lib.py`.
- Do not import `digest_config.py` into `lib.py`; `digest_config.active_douyin_source_names()` lazily imports `lib.load_sources()` to keep the dependency direction one-way.
- Keep AI prompts close to the script that calls `llm_call()` unless the prompt is a reusable markdown file under `prompts/`.

## Error Handling

**Patterns:**
- Operational scripts log and continue where partial failure is expected: `fetch-all.sh` records nonzero fetch exits; `fetch-manual-links.py` records failed URLs and continues.
- Configuration/request errors should fail fast for LLM calls: `lib.LLMNonRetryable` is raised for non-retryable HTTP/provider errors.
- Transient LLM failures retry and can fail over from DeepSeek to Anthropic/Sonnet through `lib.llm_call()`.
- Reader-facing quality failures should block release through `quality-check.py`.
- Local owner alerts should be written through `lib.write_health_alert()` to `/Users/wendy/park-io/inbox/health-alerts.md`; alert writing must not break the pipeline.

**Do This:**
- Surface pipeline degradation explicitly in `scoring-health.json`, `source-health.json`, `health-alerts.md`, logs, or status pages.
- Preserve bypass behavior for official, manual, saved, WeChat, and media inputs when scoring is down.
- Return nonzero from `main()` for hard stage failures so shell wrappers stop correctly.

**Avoid This:**
- Do not silently drop curated sources because an upstream service failed.
- Do not add content/template fallbacks beyond the single LLM provider fallback described in `HANDOVER.md`.
- Do not catch broad exceptions around reader-facing generation unless the exception is recorded and the output remains valid.

## Logging

**Framework:** console/file logging through shared helpers and shell redirection.

**Patterns:**
- Use `lib.log(stage, message)` from Python pipeline scripts for consistent stage logs.
- Shell wrappers append to `logs/fetch-all.log` and `logs/push-digest.log`.
- Include stage start/end messages and counts, for example `fetch-manual-links.py` logs `START`, per-source `NEW`, and `DONE`.
- For health and owner action, write durable alerts through `lib.write_health_alert()`.

## Comments

**When to Comment:**
- Comment non-obvious product invariants and failure modes, especially those tied to `GOTCHAS.md`.
- Use comments to explain why fallback, bypass, or guard behavior exists, as in `lib.llm_call()` and `summarize.py event_title()`.
- Keep comments operational and specific; avoid comments that only restate the code.

**JSDoc/TSDoc:**
- Not applicable.

**Docstrings:**
- Use module docstrings for scripts to state the stage purpose: `"""Stage 4: Build Digest."""`, `"""Pre-push quality checks for the Park-IO daily product."""`.
- Use function docstrings for shared helpers and behavior with important contracts: `lib.load_sources()`, `lib.write_source_output()`, `digest_text.strip_source_meta()`.

## Function Design

**Size:**
- Small wrappers and helpers should stay focused, for example `build-digest.py main()` delegates to `summarize.py` and `html-to-long-image.py`.
- Larger orchestration functions are acceptable in pipeline scripts when they represent a whole stage, but pull reusable parsing/path/text logic into `lib.py`, `digest_text.py`, or `digest_events.py`.

**Parameters:**
- Pass plain dictionaries for source and item records; use the same keys that markdown/frontmatter and JSON state use (`name`, `profile_id`, `platform`, `category`, `url`, `title`, `content`, `published`).
- Use optional batch parameters for artifact path helpers, as in `processed_batch_dir(batch: str | None = None)` and `batch_artifact_paths(batch: str | None = None, prefix: bool = True)`.
- Prefer environment variables for runtime overrides: `PARKIO_BATCH_ID`, `PARKIO_BATCH_DIR`, `PARKIO_DATE`, `PARKIO_SKIP_SEND`, `PARKIO_LLM_PROVIDER`, `PARKIO_DEEPSEEK_MODEL`.

**Return Values:**
- CLI `main()` should return an int when the stage can fail.
- Parser helpers should return empty containers on missing/invalid optional state, as in `load_sources()`, `load_scores()`, and `load_media_summaries()`.
- Path helpers should return `Path`, not strings.

## Module Design

**Exports:**
- No explicit `__all__` convention is used.
- Modules export functions/constants directly; import only the names needed with `from lib import ...`.
- Keep shared constants centralized: paths in `lib.py`, product policy in `digest_config.py`, text cleaning markers in `digest_config.py` and `digest_text.py`.

**Barrel Files:**
- Not used.

**Script Boundaries:**
- `fetch.py` orchestrates fetch stage scripts; individual fetchers own platform-specific extraction.
- `score.py` delegates scoring to `score-items.py`.
- `build-digest.py` delegates digest rendering to `summarize.py` and image rendering to `html-to-long-image.py`.
- `check-quality.py` is a thin wrapper over `quality-check.py`.
- `send-artifacts.py` delegates Telegram behavior to `push-telegram.py`.

## Source/Profile/Library Conventions

**Source Configuration:**
- Add/remove/disable sources in `/Users/wendy/park-io/sources.md`; this is the source list parsed by `lib.load_sources()`.
- The first markdown table in `/Users/wendy/park-io/sources.md` must keep columns used by the parser: `id`, `profile_id`, `name`, `platform`, `url`, `category`, `priority`, `frequency`, `active`, `added_date`, `notes`.
- Disable without deleting by setting `active` to `false`.
- Keep WeChat `rss_url` and `user_name` notes in the `notes` column when available; pending WeWe subscriptions can remain noted there.

**Profile IDs:**
- Prefer explicit `profile_id` in `/Users/wendy/park-io/sources.md`.
- Use stable slugs such as `anthropic`, `openai`, `claude-hunter`, `zhuzi-tzfilm`.
- If no explicit profile is present, `lib.profile_id_for_source()` maps known names through `PROFILE_ID_BY_SOURCE_NAME` or sanitizes the source `name`.

**Library Files:**
- Use `archive-items.py` and `lib.item_filename()` for archived item names.
- Archived item filenames follow `YY-MM-DD-profile-channel-slug-hash.md`.
- Keep profile metadata in `/Users/wendy/park-io/library/profiles/<profile_id>/profile.md`.
- Keep items under `/Users/wendy/park-io/library/profiles/<profile_id>/items/`.
- Use `/Users/wendy/park-io/library/独立链接/` for independent/manual items without a tracked profile.

## Manual Links Conventions

- Manual links are operator data in `/Users/wendy/park-io/inbox/manual-links.md`, not repo code.
- Preserve the `Pending`, `Imported`, and `Failed` section headings exactly.
- Add one URL per line under `Pending`.
- `fetch-manual-links.py` imports only WeChat article URLs matching `WECHAT_URL_RE`.
- Unsupported URLs stay in `Pending`; do not delete them in cleanup.
- Imported records are capped in rendered output to the last 200; failed records to the last 100.
- Duplicate detection is URL-based through `state.json` key `manual-links`.

## Prompt Conventions

- Prompt files are markdown and instruction-heavy, with explicit output format and forbidden behavior sections.
- Prompts should tell the model to output Chinese summaries while keeping product/tool names in original language when needed.
- Prompt files can guide tone and format, but hard product constraints belong in code and tests.
- Do not let prompt changes bypass `quality-check.py` or `GOTCHAS.md` invariants.

## Documentation Conventions

- `README.md` is reader/operator-facing and can include Chinese product explanations, command examples, stage tables, environment variables, and output examples.
- `AGENTS.md` is the agent editing contract; check it before modifying workflow, digest, fetch, scoring, Telegram, or quality code.
- `GOTCHAS.md` is the regression invariant source; update it when a new failure mode becomes a contract.
- `HANDOVER.md` records current operational context, current model choices, recent changes, and known owner/infra actions.
- Use concrete file paths in docs, especially paths under `/Users/wendy/park-io/` when documenting runtime data.

## Test Conventions

- Tests are plain Python modules with top-level `test_*` functions and direct-run harnesses.
- Each test file imports repo modules by injecting the repo root into `sys.path`.
- Run all tests with:

```bash
for t in tests/test_*.py; do python3 "$t"; done
```

- Many tests can also run under pytest, but direct execution is the repo-native pattern.
- Test docstrings should name the gotcha or regression they lock, as in `tests/test_bypass.py` and `tests/test_cleaning.py`.
- Prefer focused invariant tests over broad end-to-end tests when changing source routing, text cleanup, score bypass, title generation, health alerts, or media handling.

## Reader-Facing Output Conventions

- Final digest content must be Chinese-first, value-first, and free of ingestion metadata.
- Markdown is the single content source; HTML and PNG must derive from final Markdown.
- Final processed artifact names should stay stable: `000-YY-MM-DD.md`, `000-YY-MM-DD.html`, `000-YY-MM-DD.png`.
- Do not produce timestamped daily digest variants such as morning/evening copies unless the product contract changes.
- Keep `parkio-push-items` and `parkio-processed-items` markers machine-readable and hidden from visible reader content.
- Never allow raw `公众号：`, `作者：`, `WeChat ID：`, `Source:`, `channel:`, `platform:`, `category:`, or `https://t.co/` metadata into reader-facing output.

---

*Convention analysis: 2026-06-04*
