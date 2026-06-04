# Park-IO Daily AI Digest

## What This Is

Park-IO Daily AI Digest is a local, file-first pipeline that gathers AI signals from official channels, X, podcasts, YouTube, Douyin, WeChat, and manual links, then ships one Chinese reader-facing daily intelligence report. The owner reads local Markdown, HTML, and PNG artifacts under `~/park-io/inbox/`, with health alerts written locally instead of Telegram.

This is a brownfield project. The current codebase already has a deterministic four-path workflow, a Markdown-first rendering contract, source health tooling, LLM failover, and regression tests.

## Core Value

Every morning the owner gets one trustworthy Chinese AI intelligence digest that is worth reading, with enough source-health visibility to know whether silence means no news or a broken channel.

## Requirements

### Validated

- [x] One canonical daily Markdown digest drives HTML rendering; HTML must not call the LLM independently.
- [x] LLM service fallback is limited to DeepSeek -> CLIProxy/Sonnet; all other failures should surface loudly instead of silently degrading.
- [x] Official, manual, WeChat, and curated media sources bypass ordinary score filtering where appropriate.
- [x] Local delivery is the default: daily artifacts are saved to `~/park-io/inbox/sent/<date>.md` and `.html`; Telegram is not the owner path.
- [x] Source health exists as a truth source and distinguishes DOWN, STALE, QUIET, NEW, FILTERED, and pending setup.
- [x] The workflow diagram contract is four independent deterministic paths: official/code, X application, media, and saved/manual/WeChat.
- [x] Regression tests and `check-quality.py` enforce core reader-facing quality gates.

### Active

- [ ] Preserve the recent title/media/Douyin fixes through regression tests so future agents cannot reintroduce raw X truncation, promo videos, no-transcript media, or Douyin whitelist loss.
- [ ] Keep the daily run fast by default: `deepseek-v4-flash` with thinking disabled unless explicitly overridden.

### Out of Scope

- Full autonomous Telegram delivery - Telegram is currently disabled by owner choice; local sent artifacts are the product path.
- A hosted web app or API - this repo is a CLI/cron pipeline.
- Silent fallback outside the LLM provider - non-LLM failures must alert locally or fail the gate.
- Replacing WeWe RSS or Douyin dependencies in this milestone - surface and document their health first; dependency replacement is a separate project.

## Context

- Primary repo: `/Users/wendy/work/input-to-park`.
- Runtime data and outputs: `~/park-io/`, especially `~/park-io/inbox/`, `~/park-io/library/`, and `~/park-io/sources.md`.
- Current handover: `HANDOVER.md`.
- Regression invariants: `GOTCHAS.md`.
- Agent editing rules: `AGENTS.md`.
- Codebase map: `.planning/codebase/`.
- Daily reader product: Chinese, value-first, local artifact set.

## Constraints

- **Content source**: Markdown is the only content source for reader artifacts - prevents Markdown/HTML/PNG drift.
- **Secrets**: Secret values stay outside git under env or `~/park-io/secrets/`; planning docs may reference secret file paths but not values.
- **Failure policy**: Only LLM provider failure may fall back; other broken dependencies must be visible.
- **Source routing**: Source -> profile -> section is deterministic; AI only works inside nodes.
- **Testing**: Any reader-facing behavior change must run focused tests plus `check-quality.py` on a regenerated batch.
- **Performance**: Default digest generation should use `deepseek-v4-flash` with thinking disabled.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Markdown drives HTML and PNG | Two renderer trees caused content drift and inconsistent summaries | Good |
| Telegram is disabled by default | Owner reads locally and wants health alerts in files | Good |
| DeepSeek v4-flash thinking disabled is the default | Reasoning mode made the digest take around 50 minutes | Good |
| Curated media is valuable by default but must have transcript/summary | Media should not be lost to X-style score filters, but promo/no-transcript items should not reach readers | Good |
| Brief channel health belongs in the digest | Owner should not need to open a second status page for basic channel health | Good |

---
*Last updated: 2026-06-04 after Phase 3 health visibility closure.*
