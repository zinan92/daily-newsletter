# Phase 4: Reader Quality Regression Lock - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning
**Source:** Brownfield quality audit after Phase 3

<domain>
## Phase Boundary

This phase locks the reader-facing fixes that recently stabilized the daily digest. The pipeline already contains focused checks for X title truncation, media publishability, Douyin source routing, metadata leaks, raw English body lines, third-person narrator leakage, and Markdown/HTML heading parity. The remaining risk is that these checks are scattered across files and can be weakened independently.

The phase output should be a compact regression contract and planning closeout, not a rewrite of the digest pipeline.
</domain>

<decisions>
## Implementation Decisions

### Reader Quality Contract
- X application titles must not be chopped first-sentence prefixes.
- Media items enter the reader body only after transcript-backed, non-promo summarization.
- Douyin source inclusion must follow active rows in `sources.md`, not a hardcoded channel list.
- The visible reader body must reject ingestion metadata, transcript/status errors, third-person narrator leakage, raw English prose, and Markdown/HTML divergence.

### Test Contract
- Keep existing focused tests in place.
- Add one consolidated `tests/test_reader_quality_contract.py` that proves the Phase 4 success criteria together.
- Prefer tests over production edits unless the contract reveals a missing guard.
</decisions>

<canonical_refs>
## Canonical References

### Product and Planning
- `.planning/PROJECT.md` - Reader value and operating contract.
- `.planning/REQUIREMENTS.md` - QUAL-01, QUAL-02, QUAL-03, QUAL-04.
- `.planning/ROADMAP.md` - Phase 4 success criteria.
- `.planning/STATE.md` - Phase 4 as current focus.
- `HANDOVER.md` and `GOTCHAS.md` - Recent reader-facing regressions.

### Code and Tests
- `summarize.py` - X headline regeneration, media publishability, source health, rendering.
- `digest_config.py` - Source-group routing and active Douyin source discovery.
- `quality-check.py` - Visible product gate for metadata, raw English, and divergence.
- `tests/test_titles.py` - X title truncation coverage.
- `tests/test_media.py` - Media publishability coverage.
- `tests/test_douyin_delivery.py` - Douyin delivery-state coverage.
- `tests/test_reader_quality_contract.py` - Phase 4 consolidated contract.
</canonical_refs>

<scope_fence>
## Scope Fence

Allowed files: `tests/test_reader_quality_contract.py`, existing focused test files if needed, `summarize.py`, `digest_config.py`, `quality-check.py`, `.planning/*`.

Avoid changing: source fetchers, generated daily artifacts, `~/park-io/sources.md`, model provider configuration, health classification from Phase 3.
</scope_fence>

---
*Phase: parkio-04-reader-quality-regression-lock*
*Context gathered: 2026-06-04 via brownfield quality audit*
