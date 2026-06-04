# Roadmap: Park-IO Daily AI Digest

## Overview

This brownfield milestone turns the existing Park-IO daily digest into a boring production routine: one local daily artifact family, visible channel health, locked reader-quality gates, and a full end-to-end proof. The project already has the core pipeline and codebase map; this roadmap focuses on bounded stabilization phases that can become one-shot atomic implementation units.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions if needed

- [x] **Phase 1: Planning Baseline And Contract Reconciliation** - Make the existing project state explicit and parser-readable for GSD.
- [x] **Phase 2: Local Artifact Parity** - Produce Markdown, HTML, and PNG from the normal local daily path.
- [x] **Phase 3: Health Visibility Closure** - Keep compact digest health plus detailed status-page diagnosis.
- [x] **Phase 4: Reader Quality Regression Lock** - Prevent X title, media, Douyin, and metadata regressions.
- [x] **Phase 5: End-To-End Daily Run Proof** - Prove the full routine with real verification and clean handover.

## Phase Details

### Phase 1: Planning Baseline And Contract Reconciliation
**Goal**: Make the existing project state explicit enough that future agents can plan and execute without rediscovering the same context.
**Depends on**: Nothing (first phase)
**Requirements**: [OPS-02, OPS-03]
**Success Criteria** (what must be TRUE):
  1. `.planning/codebase/` is committed.
  2. `.planning/PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, and `config.json` exist.
  3. The known documentation drift is recorded: brief digest health dashboard is allowed and desired, while detailed health stays in status page.
  4. Next phases are small enough to become one-shot atomic implementation units.
**Plans**: 1 plan

Plans:
- [x] 01-01: Commit parser-readable GSD planning baseline.

### Phase 2: Local Artifact Parity
**Goal**: The normal local daily path produces the same complete artifact family every day: Markdown, HTML, and PNG from one Markdown source.
**Depends on**: Phase 1
**Requirements**: [ART-01, ART-02, ART-03]
**Success Criteria** (what must be TRUE):
  1. Running the daily local path writes `~/park-io/inbox/sent/<date>.md`, `.html`, and `.png`.
  2. PNG generation uses Markdown -> HTML -> PNG and does not introduce an independent content path.
  3. Existing `PARKIO_SKIP_SEND=1` behavior remains local-only and does not require Telegram credentials.
  4. Tests or quality checks cover artifact presence and Markdown/HTML heading parity.
**Plans**: 1 plan

Plans:
- [x] 02-01: Add local daily PNG generation and artifact parity tests.

### Phase 3: Health Visibility Closure
**Goal**: Channel health should be immediately visible in the daily digest while detailed diagnosis remains in the status page and alert file.
**Depends on**: Phase 2
**Requirements**: [HLTH-01, HLTH-02, HLTH-03]
**Success Criteria** (what must be TRUE):
  1. `## 渠道概览` appears near the top of the Markdown digest.
  2. The dashboard is compact and does not crowd out the reader product.
  3. Detailed per-source health stays in `status.html` or local health alerts.
  4. WeWe frozen feeds and pending RSS setup are visible as actionable health states.
**Plans**: 1 plan

Plans:
- [x] 03-01: Reconcile digest health, status health, and health documentation.

### Phase 4: Reader Quality Regression Lock
**Goal**: Recent reader-facing fixes stay fixed through deterministic tests and quality gates.
**Depends on**: Phase 3
**Requirements**: [QUAL-01, QUAL-02, QUAL-03, QUAL-04]
**Success Criteria** (what must be TRUE):
  1. X title truncation and first-sentence duplication are rejected or regenerated.
  2. Promo/no-transcript media cannot enter the reader body.
  3. Active Douyin sources are derived from `sources.md`, not a hardcoded whitelist.
  4. Metadata leaks, third-person narrator leakage, raw English body lines, and Markdown/HTML divergence are covered by tests or gates.
**Plans**: 1 plan

Plans:
- [x] 04-01: Tighten reader-quality regression tests and gates.

### Phase 5: End-To-End Daily Run Proof
**Goal**: Prove the current milestone ships as a production routine, not just individual fixes.
**Depends on**: Phase 4
**Requirements**: [OPS-01, OPS-02]
**Success Criteria** (what must be TRUE):
  1. Full test suite passes.
  2. A real or controlled daily batch regenerates successfully.
  3. `check-quality.py` passes.
  4. Local sent artifacts are present.
  5. Any remaining infra-only blockers are listed in handover with owner action, not hidden in code comments.
**Plans**: 1 plan

Plans:
- [x] 05-01: Run milestone verification and update handover.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Planning Baseline And Contract Reconciliation | 1/1 | Complete | 2026-06-04 |
| 2. Local Artifact Parity | 1/1 | Complete | 2026-06-04 |
| 3. Health Visibility Closure | 1/1 | Complete | 2026-06-04 |
| 4. Reader Quality Regression Lock | 1/1 | Complete | 2026-06-04 |
| 5. End-To-End Daily Run Proof | 1/1 | Complete | 2026-06-04 |

## Current Recommendation

The stabilization milestone is complete. Next work should be a new owner-selected milestone, or the two remaining infra actions in `HANDOVER.md` for WeWe RSS.

---
*Roadmap created: 2026-06-04 from HANDOVER.md, README.md, GOTCHAS.md, AGENTS.md, and .planning/codebase/.*
