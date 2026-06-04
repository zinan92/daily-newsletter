# Requirements: Park-IO Daily AI Digest

**Defined:** 2026-06-04
**Core Value:** Every morning the owner gets one trustworthy Chinese AI intelligence digest that is worth reading, with enough source-health visibility to know whether silence means no news or a broken channel.

## Current Milestone Requirements

### Executable Task Graph / Agent Claim System

- [x] **TG-01**: The repo contains a task graph schema that defines task id, dependencies, status, success criteria, test commands, review requirements, linter commands, and claim metadata.
- [x] **TG-02**: The repo contains a Daily Inbox task graph with at least 20 atomic units and explicit dependencies.
- [x] **TG-03**: A validator rejects missing fields, invalid statuses, unknown dependencies, and dependency cycles.
- [x] **TG-04**: Ready-task and execution-thread commands derive claimable tasks, parallel waves, and serial execution threads from the graph.
- [x] **TG-05**: Claim and complete commands update the local graph with agent and history metadata.
- [ ] **TG-06**: A future GitHub Issues sync layer can export local tasks without making GitHub the source of truth.
- [x] **TG-07**: A future n8n/executable diagram layer can map workflow graph nodes into visual runtime nodes.

### Executable Workflow Diagram

- [x] **DG-01**: The repo contains a workflow diagram schema defining nodes, edges, commands, inputs, outputs, and failure paths.
- [x] **DG-02**: The repo contains an executable Daily Inbox workflow graph that splits channel fetching, media enrichment, scoring, aggregation, quality, finalization, health, and alerts into nodes.
- [x] **DG-03**: A validator rejects invalid node references, missing command payloads, cycles, and invalid edge types.
- [x] **DG-04**: A dry-run runner derives execution order from graph edges without running production commands.
- [x] **DG-05**: Tests prove changing graph edges changes execution order.

### Source-Ingestion Decomposition

- [x] **DEC-01**: Each runtime channel has a separate folder boundary: `rss`, `web_scrape`, `release_feed`, `x`, `youtube`, `douyin`, `wechat_rss`, and `manual_links`.
- [x] **DEC-02**: Shared ingestion primitives live under `ingestion/common/` and are used for contracts, artifact writing, health payloads, source loading, URL normalization, and test helpers.
- [x] **DEC-03**: Media post-processing is separated from ingestion under `enrichment/media/`, because YouTube, podcast, and Douyin all share transcript/summary/publishability behavior.
- [x] **DEC-04**: Aggregation remains separate from ingestion under `aggregation/digest/`; it consumes standardized channel artifacts and preserves the current reader-facing digest.
- [x] **DEC-05**: Existing CLI/cron entrypoints remain working through compatibility wrappers, so `fetch-all.sh`, `push-digest.sh`, and direct `python3 fetch-*.py` commands do not break.
- [x] **DEC-06**: The refactor preserves current Markdown/HTML/PNG outputs and current tests/quality gates.
- [x] **DEC-07**: The repo contains a workflow-as-code spec describing source paths, enrichment paths, aggregation, quality, and artifact output in n8n-ready terms.
- [x] **DEC-08**: The milestone receives an independent Claude Code CLI review and fixes actionable findings before completion.

### Artifacts

- [x] **ART-01**: The normal daily local path produces `sent/<date>.md`, `sent/<date>.html`, and `sent/<date>.png`.
- [x] **ART-02**: HTML and PNG are generated from the final Markdown only, with no second LLM summarization path.
- [x] **ART-03**: Each date has one canonical processed digest and one canonical sent digest.

### Health

- [x] **HLTH-01**: The digest contains a compact 4-5 line channel health dashboard near the top.
- [x] **HLTH-02**: The detailed status page remains the source for per-channel debugging.
- [x] **HLTH-03**: Frozen WeWe feeds, pending WeChat RSS setup, transcription retry failures, and scoring outages are surfaced as local alerts or health states.

### Content Quality

- [x] **QUAL-01**: X application titles cannot be raw content prefixes, obvious truncations, or duplicated first sentences.
- [x] **QUAL-02**: Media section excludes promo videos, no-transcript videos, too-short transcripts, and summary-free videos from the reader body.
- [x] **QUAL-03**: Active Douyin sources are included by source configuration, not a hardcoded whitelist.
- [x] **QUAL-04**: Reader-facing digest body contains Chinese summaries, not raw English, ingestion metadata, transcript errors, or third-person narrator leakage.

### Operations

- [x] **OPS-01**: Default model remains `deepseek-v4-flash` with thinking disabled, with DeepSeek -> CLIProxy/Sonnet fallback only for transient provider failures.
- [x] **OPS-02**: The owner can run a documented verification command set after any milestone.
- [x] **OPS-03**: Planning docs, handover docs, and GOTCHAS do not contradict each other on artifact and health contracts.

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
| TG-01 | Phase 11 | Complete |
| TG-02 | Phase 11 | Complete |
| TG-03 | Phase 11 | Complete |
| TG-04 | Phase 11 | Complete |
| TG-05 | Phase 11 | Complete |
| TG-06 | Future | Pending |
| TG-07 | Phase 12 | Complete |
| DG-01 | Phase 12 | Complete |
| DG-02 | Phase 12 | Complete |
| DG-03 | Phase 12 | Complete |
| DG-04 | Phase 12 | Complete |
| DG-05 | Phase 12 | Complete |
| DEC-01 | Phase 6, Phase 7, Phase 8 | In progress |
| DEC-02 | Phase 6 | Complete |
| DEC-03 | Phase 8 | Complete |
| DEC-04 | Phase 9 | Complete |
| DEC-05 | Phase 7, Phase 8, Phase 9 | Complete |
| DEC-06 | Phase 10 | Complete |
| DEC-07 | Phase 9 | Complete |
| DEC-08 | Phase 10 | Complete |
| OPS-02 | Phase 1, Phase 5 | Complete |
| OPS-03 | Phase 1, Phase 5 | Complete |
| ART-01 | Phase 2 | Complete |
| ART-02 | Phase 2 | Complete |
| ART-03 | Phase 2 | Complete |
| HLTH-01 | Phase 3 | Complete |
| HLTH-02 | Phase 3 | Complete |
| HLTH-03 | Phase 3 | Complete |
| QUAL-01 | Phase 4 | Complete |
| QUAL-02 | Phase 4 | Complete |
| QUAL-03 | Phase 4 | Complete |
| QUAL-04 | Phase 4 | Complete |
| OPS-01 | Phase 5 | Complete |

**Coverage:**
- Current stabilization requirements: 13 total, complete
- Source-ingestion decomposition requirements: 8 total, mapped to phases
- Unmapped: 0

---
*Requirements defined: 2026-06-04*
*Last updated: 2026-06-04 after Phase 12 executable workflow diagram.*
