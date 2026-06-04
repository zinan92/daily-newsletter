# Requirements: Park-IO Daily AI Digest

**Defined:** 2026-06-04
**Core Value:** Every morning the owner gets one trustworthy Chinese AI intelligence digest that is worth reading, with enough source-health visibility to know whether silence means no news or a broken channel.

## Current Milestone Requirements

### Artifacts

- [x] **ART-01**: The normal daily local path produces `sent/<date>.md`, `sent/<date>.html`, and `sent/<date>.png`.
- [x] **ART-02**: HTML and PNG are generated from the final Markdown only, with no second LLM summarization path.
- [x] **ART-03**: Each date has one canonical processed digest and one canonical sent digest.

### Health

- [x] **HLTH-01**: The digest contains a compact 4-5 line channel health dashboard near the top.
- [x] **HLTH-02**: The detailed status page remains the source for per-channel debugging.
- [x] **HLTH-03**: Frozen WeWe feeds, pending WeChat RSS setup, transcription retry failures, and scoring outages are surfaced as local alerts or health states.

### Content Quality

- [ ] **QUAL-01**: X application titles cannot be raw content prefixes, obvious truncations, or duplicated first sentences.
- [ ] **QUAL-02**: Media section excludes promo videos, no-transcript videos, too-short transcripts, and summary-free videos from the reader body.
- [ ] **QUAL-03**: Active Douyin sources are included by source configuration, not a hardcoded whitelist.
- [ ] **QUAL-04**: Reader-facing digest body contains Chinese summaries, not raw English, ingestion metadata, transcript errors, or third-person narrator leakage.

### Operations

- [ ] **OPS-01**: Default model remains `deepseek-v4-flash` with thinking disabled, with DeepSeek -> CLIProxy/Sonnet fallback only for transient provider failures.
- [ ] **OPS-02**: The owner can run a documented verification command set after any milestone.
- [ ] **OPS-03**: Planning docs, handover docs, and GOTCHAS do not contradict each other on artifact and health contracts.

## Deferred Requirements

- **AUTO-01**: Re-enable Telegram delivery after the owner explicitly wants remote push again.
- **SRC-01**: Replace fragile upstreams such as WeWe RSS or archived Douyin tooling with more durable alternatives.
- **APP-01**: Build a hosted dashboard or app around the daily digest.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Telegram-first shipping | Current owner path is local sent artifacts and local alerts |
| Silent best-effort fallback for broken sources | The owner needs to know when sources are broken |
| Rebuilding the full ingestion architecture | Current milestone is stabilization and artifact parity |
| Adding new source categories | Existing sources are enough to verify the operating model |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| OPS-02 | Phase 1 | Pending |
| OPS-03 | Phase 1 | Pending |
| ART-01 | Phase 2 | Complete |
| ART-02 | Phase 2 | Complete |
| ART-03 | Phase 2 | Complete |
| HLTH-01 | Phase 3 | Complete |
| HLTH-02 | Phase 3 | Complete |
| HLTH-03 | Phase 3 | Complete |
| QUAL-01 | Phase 4 | Pending |
| QUAL-02 | Phase 4 | Pending |
| QUAL-03 | Phase 4 | Pending |
| QUAL-04 | Phase 4 | Pending |
| OPS-01 | Phase 5 | Pending |

**Coverage:**
- Current milestone requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0

---
*Requirements defined: 2026-06-04*
*Last updated: 2026-06-04 after Phase 3 health visibility closure.*
