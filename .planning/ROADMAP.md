# Roadmap: Park-IO Daily AI Digest

## Overview

The previous brownfield milestone turned the existing Park-IO daily digest into a boring production routine. The new milestone decomposes source ingestion by runtime channel while preserving the current daily output.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions if needed

- [x] **Phase 1: Planning Baseline And Contract Reconciliation** - Make the existing project state explicit and parser-readable for GSD.
- [x] **Phase 2: Local Artifact Parity** - Produce Markdown, HTML, and PNG from the normal local daily path.
- [x] **Phase 3: Health Visibility Closure** - Keep compact digest health plus detailed status-page diagnosis.
- [x] **Phase 4: Reader Quality Regression Lock** - Prevent X title, media, Douyin, and metadata regressions.
- [x] **Phase 5: End-To-End Daily Run Proof** - Prove the full routine with real verification and clean handover.
- [x] **Phase 6: Source Ingestion Contracts And Skeleton** - Create standard contracts, folder skeleton, compatibility rules, and workflow map.
- [x] **Phase 7: Core Channel Folderization** - Move RSS, web scrape, release feed, and X ingestion behind channel folders with thin root wrappers.
- [x] **Phase 8: Media And WeChat Folderization** - Move YouTube/media, Douyin, WeChat RSS, manual links, and media enrichment behind channel/enrichment folders.
- [x] **Phase 9: Aggregation Boundary And Workflow Spec** - Move digest aggregation behind an aggregation folder and add n8n-ready workflow-as-code.
- [ ] **Phase 10: Full Verification And Cross-AI Review** - Prove output compatibility, run full verification, run Claude Code review, fix findings, and close the milestone.

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

### Phase 6: Source Ingestion Contracts And Skeleton
**Goal**: Establish the project boundaries and standard artifacts before moving production code.
**Depends on**: Phase 5
**Requirements**: [DEC-01, DEC-02]
**Success Criteria** (what must be TRUE):
  1. `ingestion/common/`, channel folders, `enrichment/media/`, `aggregation/digest/`, and `workflow/` exist.
  2. Contracts define channel input, output, health, error, and artifact paths.
  3. Root scripts remain the public CLI/cron surface for compatibility.
  4. The phase plan makes later channel moves atomic.
**Plans**: 1 plan

Plans:
- [x] 06-01: Add source-ingestion contracts and skeleton.

### Phase 7: Core Channel Folderization
**Goal**: Move deterministic text/feed ingestion code into channel-owned folders without changing outputs.
**Depends on**: Phase 6
**Requirements**: [DEC-01, DEC-05]
**Success Criteria** (what must be TRUE):
  1. RSS, web scrape, release feed, and X ingestion have channel folders.
  2. Existing root entrypoints still work as wrappers.
  3. Existing tests and focused ingestion smoke tests pass.
**Plans**: 1 plan

Plans:
- [x] 07-01: Folderize RSS, scrape, release, and X ingestion.

### Phase 8: Media And WeChat Folderization
**Goal**: Move media-heavy and WeChat/manual ingestion into proper channel/enrichment boundaries.
**Depends on**: Phase 7
**Requirements**: [DEC-01, DEC-03, DEC-05]
**Success Criteria** (what must be TRUE):
  1. YouTube/media, Douyin, WeChat RSS, and manual links have channel folders.
  2. Shared transcript/summary/publishability logic is documented under `enrichment/media/`.
  3. Existing direct commands still work.
**Plans**: 1 plan

Plans:
- [x] 08-01: Folderize media, Douyin, WeChat, and manual ingestion.

### Phase 9: Aggregation Boundary And Workflow Spec
**Goal**: Separate final digest aggregation from source ingestion and document the runtime workflow as code.
**Depends on**: Phase 8
**Requirements**: [DEC-04, DEC-07]
**Success Criteria** (what must be TRUE):
  1. Aggregation code has a clear folder boundary.
  2. Workflow spec shows source paths, enrichment, aggregation, quality, and artifact outputs.
  3. Spec is n8n-ready but the repo remains source-of-truth.
**Plans**: 1 plan

Plans:
- [x] 09-01: Add aggregation boundary and workflow-as-code spec.

### Phase 10: Full Verification And Cross-AI Review
**Goal**: Prove the refactor preserved behavior and receive independent Claude Code review.
**Depends on**: Phase 9
**Requirements**: [DEC-06, DEC-08]
**Success Criteria** (what must be TRUE):
  1. Full test suite passes.
  2. Controlled daily batch still builds, finalizes, and passes quality.
  3. Claude Code CLI review is run and actionable findings are fixed or documented.
  4. Handover explains the new project layout and next-thread boundaries.
**Plans**: 1 plan

Plans:
- [ ] 10-01: Verify, review, fix, and close source-ingestion decomposition.

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
| 6. Source Ingestion Contracts And Skeleton | 1/1 | Complete | 2026-06-04 |
| 7. Core Channel Folderization | 1/1 | Complete | 2026-06-04 |
| 8. Media And WeChat Folderization | 1/1 | Complete | 2026-06-04 |
| 9. Aggregation Boundary And Workflow Spec | 1/1 | Complete | 2026-06-04 |
| 10. Full Verification And Cross-AI Review | 0/1 | In progress | - |

## Current Recommendation

Next target is Phase 8: folderize media, Douyin, WeChat RSS, and manual ingestion behind compatibility wrappers.

---
*Roadmap created: 2026-06-04 from HANDOVER.md, README.md, GOTCHAS.md, AGENTS.md, and .planning/codebase/.*
