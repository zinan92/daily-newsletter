# Phase 3: Health Visibility Closure - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning
**Source:** Brownfield health audit after Phase 2

<domain>
## Phase Boundary

This phase reconciles the health contract: the daily digest should show compact channel health, while `status.html` and `health-alerts.md` keep detailed diagnosis. The concrete gap found during audit is `克劳德猎手`: `sources.md` says `rss_url pending WeWe subscription`, but digest/source health can treat a seed article as `ok_new`, hiding the fact that the automated WeWe feed is not configured.

This phase should not redesign the digest layout or status page. It should make pending WeWe setup explicit and test-covered.
</domain>

<decisions>
## Implementation Decisions

### Health Contract
- A WeChat source whose notes contain `rss_url pending` is not an automated healthy channel.
- Pending WeWe RSS setup should surface as a failed/action-needed health state even if a seed/manual article appears in today's digest.
- `Ray在思考` frozen feed remains `stale`.
- `克劳德猎手` pending RSS should be visible in digest dashboard, status/detail surfaces, and local health alerts as an actionable setup issue.

### Test Contract
- Add focused tests for `channel-health.py` pending WeWe detection.
- Add focused tests for `summarize.source_health()` so seed-only WeChat content does not mask pending feed setup.
- Keep dashboard compact: names may appear in the digest; detailed reasons stay in status/local alerts.
</decisions>

<canonical_refs>
## Canonical References

### Product and Planning
- `.planning/PROJECT.md` - Health visibility and owner contract.
- `.planning/REQUIREMENTS.md` - HLTH-01, HLTH-02, HLTH-03.
- `.planning/ROADMAP.md` - Phase 3 success criteria.
- `.planning/STATE.md` - Current state and stale risk list.
- `HANDOVER.md` - Owner action items for Ray在思考 and 克劳德猎手.
- `README.md` and `GOTCHAS.md` - Reader/operator health contract.

### Code and Tests
- `channel-health.py` - Truthful per-channel state.
- `summarize.py` - `source_health()` and digest dashboard mapping.
- `check-pipeline-health.py` - Local health alerts via `broken_sources()`.
- `tests/test_channel_health.py` - Channel-state unit tests.
- `tests/test_health_dashboard.py` - Compact digest dashboard tests.
- `tests/test_source_health.py` - Source-health false-green tests.
</canonical_refs>

<specifics>
## Specific Ideas

- Add a pure helper in `channel-health.py`, for example `pending_setup(src)`, that detects active WeChat rows whose notes contain `rss_url pending`.
- In `channel_rows()`, classify pending setup before log lookup as `DOWN` with error text like `WeWe RSS 未配置：rss_url pending WeWe subscription`.
- In `summarize.source_health()`, check the same pending condition before treating `today_src` WeChat items as `ok_new`.
- Add a test row for `克劳德猎手` style notes and assert the health state is actionable.
- Update `.planning/STATE.md` once the `GOTCHAS.md` drift risk is resolved.
</specifics>

<deferred>
## Deferred Ideas

- Creating the actual WeWe RSS subscription for `克劳德猎手` remains owner/infra action.
- Replacing WeWe RSS is not in scope.
- Changing digest layout beyond the existing compact dashboard is not in scope.
</deferred>

<scope_fence>
## Scope Fence

Allowed files: `channel-health.py`, `summarize.py`, `tests/test_channel_health.py`, `tests/test_health_dashboard.py`, `README.md`, `GOTCHAS.md`, `HANDOVER.md`, `.planning/*`.

Avoid changing: fetchers, WeWe runtime data, `~/park-io/sources.md`, generated daily artifacts unless needed for verification.
</scope_fence>

---
*Phase: parkio-03-health-visibility-closure*
*Context gathered: 2026-06-04 via brownfield health audit*
