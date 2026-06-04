# Phase 2: Local Artifact Parity - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning
**Source:** Brownfield planning bootstrap from HANDOVER.md, README.md, GOTCHAS.md, AGENTS.md, and codebase map

<domain>
## Phase Boundary

This phase only closes the local artifact parity gap. `build-digest.py` already renders the processed PNG from processed HTML when the digest is built. `finalize-local.py` currently copies Markdown and HTML from processed into `~/park-io/inbox/sent/`, but ignores the processed PNG. The phase should make the normal local daily path preserve PNG in sent as well.

This phase does not redesign the digest, source health, media filtering, Telegram sending, or the workflow graph.
</domain>

<decisions>
## Implementation Decisions

### Artifact Contract
- The normal local daily path should write `sent/<date>.md`, `sent/<date>.html`, and `sent/<date>.png` when processed artifacts exist.
- Markdown remains the only content source. HTML derives from Markdown, and PNG derives from HTML.
- `finalize-local.py` should copy the existing processed PNG. It should not re-render or call the LLM.
- Missing processed Markdown is a hard failure, as today.
- Missing processed HTML or PNG may warn and continue, because `build-digest.py` can continue if Chrome screenshot rendering fails.

### Test Contract
- Add a focused offline regression test for `finalize-local.py` that patches paths and proves Markdown, HTML, and PNG are copied atomically to a temp sent directory.
- Do not rely on real `~/park-io/`, Chrome, live batches, Telegram, or secrets in the unit test.

### Documentation Contract
- Update stale docs that say sent keeps only Markdown or only Markdown/HTML.
- The target owner contract is: processed contains `000-<date>.{md,html,png}` and sent contains `<date>.{md,html,png}` when all artifacts exist.
</decisions>

<canonical_refs>
## Canonical References

### Project Contracts
- `HANDOVER.md` - Current owner operating principles and known PNG gap.
- `README.md` - Operator runbook and artifact description.
- `GOTCHAS.md` - Regression invariants that must not contradict the new artifact contract.
- `AGENTS.md` - Required test loop and agent editing rules.

### Code Paths
- `finalize-local.py` - Local artifact finalization target.
- `build-digest.py` - Existing processed PNG rendering path.
- `html-to-long-image.py` - Existing HTML to PNG renderer, not called by this phase.
- `lib.py` - `batch_artifact_paths()`, `batch_label()`, and `SENT_DIR` helpers.

### Codebase Map
- `.planning/codebase/STRUCTURE.md` - Entry points and artifact folders.
- `.planning/codebase/TESTING.md` - Test style and verification commands.
</canonical_refs>

<specifics>
## Specific Ideas

- `finalize-local.py` already destructures `panel, html, _png = batch_artifact_paths()`. Rename `_png` to `png` and copy it to `SENT_DIR / f"{label}.png"` if it exists.
- Factor repeated optional copy behavior only if it keeps the file simpler; avoid broad refactors.
- A good test can import `finalize-local.py` through `importlib.util.spec_from_file_location`, patch `SENT_DIR`, `batch_label`, and `batch_artifact_paths`, then call `main()`.
</specifics>

<deferred>
## Deferred Ideas

- Re-rendering PNG in `finalize-local.py` if processed PNG is missing. That introduces a second render path and more launchd/Chrome failure surface; keep this phase to copying the artifact produced by `build-digest.py`.
- Restoring Telegram delivery. Local artifacts are the owner product path.
- Source health or content-quality changes. Those are Phase 3 and Phase 4.
</deferred>

<scope_fence>
## Scope Fence

Allowed files: `finalize-local.py`, `tests/test_finalize_local.py`, `README.md`, `GOTCHAS.md`, `HANDOVER.md`.

Avoid changing: `summarize.py`, `build-digest.py`, `html-to-long-image.py`, source fetchers, scoring, Telegram delivery, secrets, runtime data under `~/park-io/`.
</scope_fence>

---
*Phase: parkio-02-local-artifact-parity*
*Context gathered: 2026-06-04 via brownfield planning bootstrap*
