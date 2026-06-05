# Codex task: finish & clean up the ingestion-decomposition refactor

## Repo & context

Repository: **Park-IO Daily AI Digest** — a personal Python content pipeline that fetches from many
sources, enriches, scores, and builds a daily Chinese AI digest (Markdown/HTML/PNG). It is a
**CLI / cron pipeline, not a library or web service.** It runs locally via launchd:
`fetch-all.sh` every 4h, `push-digest.sh` daily at 08:30.

It was recently refactored from "everything at the repo root" into layered folders:

- `contracts/` — interface/contract definitions (defined first)
- `ingestion/<channel>/` — per-channel source adapters (each has a `run.py`)
- `enrichment/` — transcript/media enrichment
- `aggregation/digest/` — scoring, digest build, summarize, quality gates, archive, finalize, html→image
- `workflow/`, `tasks/`, `scripts/`, `tests/`, `prompts/`

To keep cron/CLI working, ~20 thin **compatibility wrappers** live at the repo root (e.g.
`fetch-rss.py` → `ingestion/rss/run.py`, `score.py` → `aggregation/digest/score_stage.py`).

## DECISIONS ALREADY MADE BY THE OWNER (do not revisit these)

The owner weighed "keep the wrappers vs collapse them" and several deeper refactors, and chose the
**conservative, keep-it-stable** path. These are settled — implement accordingly, do NOT propose or
perform the rejected alternatives:

- **KEEP all 20 root compatibility wrappers.** They are the permanent public command surface.
  cron/launchd calls the two `.sh` orchestrators, which call the wrappers; `tests/test_ingestion_wrappers.py`
  enforces them; ~39 files import shared modules by bare top-level name against `ROOT`-on-`sys.path`.
  **Do NOT delete, collapse, or relocate any wrapper.**
- **Do NOT move `lib.py`, `digest_config.py`, `digest_events.py`, `digest_text.py`** out of the root.
  39 files import `lib` by bare name; `digest_*` are imported bare by folder modules and tests.
  Moving them is explicitly out of scope.
- **Do NOT add `__init__.py`, `pyproject.toml`, or any packaging.** Out of scope.
- **Do NOT edit `push-digest.sh`, `fetch.py`, `fetch-all.sh`, cron/launchd, or `README.md`'s command
  surface.** They correctly call the wrappers, which we are keeping.

The actual goal is narrow: **remove the one real mess the refactor left behind (internal code that
bounces back out through the root wrappers), and do two small, safe declutters.** Nothing else.

---

## STAGE 1 (REQUIRED) — Break the 3 wrapper→folder→wrapper bounce chains

Three modules under `aggregation/digest/` currently `subprocess` BACK OUT to a root wrapper, which
only re-imports the folder sibling sitting right next to the caller. This is wasteful and a
silent-divergence hazard. Repoint each subprocess at the **folder sibling directly**. Keep it a
subprocess (same process-isolation behavior); do NOT convert to an in-process import unless a test
forces it (and justify if you do). Behavior must stay byte-for-byte identical.

1. **`aggregation/digest/score_stage.py:15`**
   ```python
   return subprocess.run([sys.executable, str(ROOT / "score-items.py")]).returncode
   ```
   → target `aggregation/digest/score_items.py` via `Path(__file__).resolve().parent / "score_items.py"`.

2. **`aggregation/digest/build.py:15`**
   ```python
   result = subprocess.run([sys.executable, str(ROOT / "summarize.py")])
   ```
   → target `aggregation/digest/summarize.py`.

3. **`aggregation/digest/build.py:20-24`** (the screenshot / html→image call)
   ```python
   screenshot = subprocess.run([... str(ROOT / "html-to-long-image.py") ...])
   ```
   → target `aggregation/digest/html_to_long_image.py`.

Before each: OPEN the folder sibling, confirm it runs as `python3 <path>` and exposes the same
entrypoint/exit-code behavior the wrapper did (the wrapper is the current source of truth). If the
sibling's `__main__`/exit handling differs, make the sibling match the wrapper's contract — do not
change observable output.

**Leave `aggregation/digest/summarize.py:422` (the `channel-health` load) ALONE** — `channel-health.py`
is a genuine root entrypoint with no folder counterpart, so that call is correct.

Commit each of the 3 as a separate atomic commit, running the full verification block (below) before
each commit.

---

## STAGE 2 (REQUIRED, GATED) — Archive the dead one-shot maintenance scripts

These 4 root scripts appear to be one-shot maintenance tools with no live caller:
`build-index.py`, `fix-asr-errors.py`, `polish-douyin.py`, `backfill-claude-blog-library.py`.

**Before moving ANY of them, prove it is unreferenced.** For each file, grep every surface:
```bash
f=build-index.py   # repeat per file
grep -rn --include='*.sh' --include='*.py' --include='*.json' --include='*.yaml' --include='*.yml' \
  --include='*.md' -F "$f" . | grep -v "^\./$f:"
grep -rn -F "${f%.py}" workflow/ tasks/ tests/ *.sh README.md AGENTS.md GOTCHAS.md
```
Also check for dynamic `importlib` loads of the file's basename.

- **If a file has ZERO live references** (only its own definition / planning docs under `.planning/`):
  `git mv <file> scripts/archive/<file>`. Create `scripts/archive/` if needed; add a one-line
  `scripts/archive/README.md` noting these are retired one-shot scripts kept for reference.
- **If a file HAS any live reference** (a `.sh`, a workflow `*.json`/`*.yaml`, a test, an `importlib`
  load, or a documented command in README): **do NOT move it. STOP and report** which reference
  blocks it. Do not rewrite the caller to unblock the move — that is a separate decision.

Commit the archived files in one commit. If all 4 are blocked, skip this stage and say so.

---

## STAGE 3 (OPTIONAL, GATED) — Simplify the one non-uniform wrapper, only if proven safe

`summarize.py` (root wrapper) uses an unusual pattern: `globals().update(...)` plus
`sys.modules[__name__] = _impl`. This is *probably* load-bearing (some module may do
`import summarize` and need the real module object), so do NOT blindly flatten it.

**Do this only AFTER Stage 1 is committed and verified.** Then check whether anything still imports
these wrappers *as modules* (not runs them as scripts):
```bash
grep -rn --include='*.py' -E '\bimport summarize\b|from summarize import|\bimport score_items\b|importlib.*summarize|importlib.*score-items|importlib.*html-to-long-image' . \
  | grep -v "^\./summarize.py:"
```
- **If nothing imports `summarize` as a module anymore** (Stage 1 removed the last such use):
  simplify `summarize.py` to the same plain shape as the other wrappers
  (`from aggregation.digest.summarize import *` + a standard `if __name__ == "__main__": raise SystemExit(main())`),
  run the full verification block, and commit. The goal is all wrappers sharing one boring shape.
- **If anything still imports it as a module:** leave `summarize.py` exactly as-is and report why.
  Cosmetic uniformity is not worth breaking a working import.

Do NOT touch any other wrapper in this stage — the rest are already uniform.

---

## Verification (run after EVERY change; ALL must pass before committing)

```bash
python3 -m py_compile summarize.py digest_config.py lib.py quality-check.py fetch-douyin.py \
  aggregation/digest/score_stage.py aggregation/digest/build.py aggregation/digest/summarize.py
for t in tests/test_*.py; do echo "== $t =="; python3 "$t" || exit 1; done
PARKIO_BATCH_ID=20260604 python3 build-digest.py
PARKIO_BATCH_ID=20260604 python3 finalize-local.py
PARKIO_BATCH_ID=20260604 PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py
python3 channel-health.py
```

`tests/test_ingestion_wrappers.py` and `tests/test_ingestion_contracts.py` assert the wrapper↔folder
relationship and MUST still pass.

**Behavior-parity — do NOT use byte-identical artifacts.** `build-digest.py` calls the LLM live on
every run, so the `20260604` md/html/png vary run-to-run regardless of any code change (pre-existing
nondeterminism, not a regression — confirm once by running `build-digest.py` twice with no code change;
the hashes already differ). This refactor only repoints which file path a subprocess targets; it runs
the SAME module code either way. Verify equivalence STRUCTURALLY: a Stage-1 change is accepted when
(1) the full verification block exits 0, (2) the wrapper + contract tests pass, and (3) the folder
sibling derives repo paths from its OWN `__file__` (not argv[0]/cwd) and the subprocess passes the same
args/env as before. This is already true for `score_items.py`, `summarize.py`, `html_to_long_image.py`
(each computes `REPO_ROOT = Path(__file__).resolve().parents[2]`; the wrappers are pure
`from … import *` + `main()` passthroughs). If you hit a sibling that does NOT satisfy (3), STOP and report.

## Workflow & guardrails

- Work on a branch. Do NOT push or open a PR unless asked.
- Atomic commits, conventional-commit messages (e.g.
  `refactor(aggregation): call summarize folder sibling directly instead of root wrapper`).
- **Git attribution is disabled — do NOT add Co-Authored-By or any attribution trailer.**
- Keep every change minimal and surgical. No drive-by reformatting, no renames, no "while I'm here".

## STOP and report instead of guessing if

- A folder sibling does not behave identically to its root wrapper (different `main()` signature,
  exit code, side effect, or output).
- Any verification command fails and the fix is not an obvious typo in your own change.
- A Stage-2 file has a live reference, or a Stage-3 wrapper is still imported as a module.
- You discover a 4th hidden bounce chain not listed in Stage 1.

## When done, report

- The Stage 1 diffs (file:line before/after) and confirmation the bounce chains are gone.
- Which Stage 2 files were archived vs blocked (and by what).
- Whether Stage 3 simplified `summarize.py` or left it (and why).
- Confirmation the full verification block passes and the `20260604` artifacts are byte-identical pre/post.
```
