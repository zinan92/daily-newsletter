# Handover - Park-IO digest stabilization and decomposition (2026-06-04)

Context for the next engineer/agent (Codex) taking over `input-to-park` (the
Park-IO daily AI digest pipeline). Everything below is committed to `main` and
pushed to `github.com/zinan92/daily-newsletter`.

## Owner's operating principles (respect these)
- **Markdown is the single content source.** HTML and PNG MUST derive from the
  final Markdown — never call the LLM separately for HTML (that caused content
  drift). `summarize.py main()` writes MD, then `render_html_from_markdown(md)`.
- **Fixed pipeline, one fallback only.** The ONLY fallback is the LLM:
  DeepSeek → Anthropic/Sonnet (`PARKIO_LLM_FALLBACK_PROVIDER`). Do NOT add
  fallbacks elsewhere — if something breaks, surface it loudly, don't degrade
  silently.
- **No Telegram.** Owner reads locally. Digest -> `~/park-io/inbox/sent/<date>.{md,html,png}`.
  Failure alerts -> `~/park-io/inbox/health-alerts.md` (newest first).
- **Curated Douyin/podcast video sources are valuable by default** — they bypass
  the X-style score filter; they enter the body only if transcribed+summarized.

## Default model (changed this session)
- `deepseek-v4-flash` with **thinking disabled** (`lib.DEEPSEEK_MODEL`,
  `DEEPSEEK_THINKING=disabled`). The V4 API defaults thinking to *enabled*
  (reasoning tokens → a ~50-min digest); we send `thinking:{"type":"disabled"}`.
- `deepseek-chat`/`deepseek-reasoner` are deprecated **2026-07-24** (aliases for
  v4-flash non-/thinking) — that's why we target `deepseek-v4-flash` directly.
- Full digest now runs in **~212s** (was ~50 min). Opt into reasoning with
  `PARKIO_DEEPSEEK_THINKING=enabled` (and `PARKIO_DEEPSEEK_MODEL=deepseek-v4-pro`).
- The 300s timeout / output-headroom bump applies ONLY when thinking is actually
  on (`lib._deepseek_thinking_on`).

## Current GSD milestone state
- **Phase 1 - Planning baseline:** complete. Codebase map and parser-readable
  planning files are committed.
- **Phase 2 - Local artifact parity:** complete. `finalize-local.py` writes local
  Markdown, HTML, and PNG when processed artifacts exist.
- **Phase 3 - Health visibility closure:** complete. Frozen WeWe feeds and
  pending WeWe RSS setup are visible in digest/status health.
- **Phase 4 - Reader quality regression lock:** complete. `tests/test_reader_quality_contract.py`
  consolidates title, media, Douyin, metadata, raw-English, and MD/HTML gates.
- **Phase 5 - End-to-end daily proof:** complete after the 2026-06-04 controlled
  batch regeneration and local finalize proof.
- **Post-proof source fix:** `克劳德猎手` WeWe RSS is now configured as
  `http://localhost:4000/feeds/MP_WXS_3935644082.json` in `~/park-io/sources.md`
  and fetches successfully.
- **Phase 6 - Source ingestion contracts and skeleton:** complete. Standard
  contracts, folder skeleton, JSON schema, and workflow map are committed.
- **Phase 7 - Core channel folderization:** complete. RSS, web scrape, X
  timeline, and X saved items now live under channel folders with root wrappers.
- **Phase 8 - Media and WeChat folderization:** complete. Douyin, WeChat RSS,
  WeChat exporter, manual links, seeded WeChat parser, and media enrichment now
  live under channel/enrichment folders with root wrappers.
- **Phase 9 - Aggregation boundary:** complete. Score/build/summarize/quality,
  AI quality, archive, finalize, and HTML-to-PNG implementations now live under
  `aggregation/digest/` with root wrappers.
- **Phase 10 - Verification:** complete. Local verification passed, and Claude
  Code CLI review returned no blocking findings after a narrower wrapper/path
  review prompt.

Recent GSD commits:
- `a3a9863` - codebase map
- `0ebc923` - GSD planning baseline
- `832de12` - local PNG finalization
- `a4b347f` - pending WeWe RSS health visibility
- `1180f22` - reader quality contract test
- `b9fb41d` - Phase 5 proof plan
- `628825d` - Phase 6 source ingestion decomposition plan
- `17d1774` - source ingestion contracts
- `3d37449` - core ingestion folderization
- `d7baad3` - media and WeChat folderization
- `0577323` - digest aggregation folderization
- `a2e6a92` - decomposition verification handoff

## Current folder boundaries

- `ingestion/rss/`: RSS feeds and YouTube feed fallback.
- `ingestion/web_scrape/`: official web scraping.
- `ingestion/x/`: X timeline and saved items.
- `ingestion/douyin/`: Douyin profile monitoring and late-first-seen delivery.
- `ingestion/wechat_rss/`: WeWe RSS plus exporter bridge imports.
- `ingestion/manual_links/`: owner-provided links and seeded WeChat article parser.
- `enrichment/media/`: YouTube/Douyin/podcast transcript and media summary work.
- `aggregation/digest/`: scoring, digest assembly, quality gates, archive,
  local finalize, and PNG rendering.
- Root scripts remain the public command/import surface for cron, tests, and
  operator commands.

## Executable task graph

The first repo-local task graph is now in place:

- Schema: `tasks/schema.json`
- Graph: `tasks/daily-inbox-task-graph.json`
- Docs: `tasks/README.md`
- Validator: `python3 scripts/task_graph_validate.py`
- Ready tasks: `python3 scripts/task_graph_ready.py`
- Next task: `python3 scripts/task_next.py`
- Agent loop preview: `python3 scripts/task_agent_loop.py --agent codex`
- Execution waves/threads: `python3 scripts/task_graph_threads.py`
- Claim: `python3 scripts/task_claim.py <TASK_ID> --agent <name>`
- Complete: `python3 scripts/task_complete.py <TASK_ID> --agent <name> --commit <sha>`
- GitHub issue dry-run export:
  `python3 scripts/task_graph_github_export.py --task <TASK_ID> --json`
- Protocol: `tasks/agent-claim-protocol.md`
- Review checklist: `tasks/review-checklist.md`

This is the foundation for the owner's Symphony-like operating model: atomic
units first, execution threads derived from dependencies, then future GitHub
Issues or n8n sync. Keep the local graph canonical unless a later milestone
explicitly changes that contract.

## Executable workflow diagram

The first runtime workflow graph is now in place:

- Schema: `workflow/diagram/schema.json`
- Graph: `workflow/diagram/daily-newsletter.graph.json`
- Docs: `workflow/diagram/README.md`
- Validator: `python3 scripts/workflow_graph_validate.py`
- Dry-run: `python3 scripts/workflow_graph_dry_run.py`
- Safe runner: `python3 scripts/workflow_graph_run.py`

The graph currently has 22 nodes covering channel fetch, media enrichment,
source health, digest build, quality, archive, local finalize, status, and
failure alert. Dry-run is normal-path only; failure-only alert nodes are kept in
the graph but excluded from normal dry-run order.

`workflow_graph_run.py` is dry-run by default. Real execution requires a node
selection and explicit `--run --confirm-production`.

## n8n export

The canonical workflow graph can now export to n8n JSON:

```bash
python3 scripts/n8n_export.py --dry-run
python3 scripts/n8n_export.py --output workflow/n8n/daily-newsletter.workflow.json
```

Generated artifact: `workflow/n8n/daily-newsletter.workflow.json`.

The n8n-visible projection can now be checked against the canonical graph:

```bash
python3 scripts/n8n_import_diff.py
```

Do not treat the generated n8n JSON as canonical. It is an adapter artifact;
the diff command is for drift detection and does not overwrite
`workflow/diagram/daily-newsletter.graph.json`.

## What changed in the stabilization milestone
1. **LLM failover + local finalize** (`lib.py`, `push-digest.sh`, `finalize-local.py`).
2. **Douyin delivery and routing** — `digest_config.active_douyin_source_names()`
   reads active `platform=douyin` rows from `sources.md`; delivery state no longer
   lets archived-but-undelivered videos get swallowed.
3. **Digest quality** (`summarize.py`): compact `## 渠道概览`, chopped X title
   detection/regeneration, media publishability guard, and centralized
   third-person narrator guard. Dead independent HTML rendering was removed, so
   HTML/PNG derive from the Markdown product.
4. **Quality gates** (`quality-check.py`): metadata leak markers, transcript/status
   leak markers, raw-English body detection, and Markdown/HTML heading-divergence
   checks.
5. **No silent failures**: transcription failures, scoring outages, LLM outages,
   frozen feeds, and pending RSS setup surface as local health states or alerts.

## Diagnosed root causes (for reference)
- **柱子哥 missing**: (a) config whitelist excluded it; (b) its 06-02 video failed
  transcription on a one-off Douyin download `ReadTimeout` and was never retried.
  Both fixed; the 06-02 transcript was recovered (now `summarized`).
- The ~50-min digest = `deepseek-v4-pro` reasoning tokens (94k across 48 calls).

## Outstanding (owner/infra action — NOT code)
- **Ray在思考**: wewe-rss subscription `MP_WXS_3226075849` is frozen since 2026-03-23.
  Owner has marked this source as low priority; leave it visible as STALE unless
  the owner later wants to refresh or disable it.
- **克劳德猎手**: resolved. WeWe RSS feed is `MP_WXS_3935644082`; a manual health
  verification on 2026-06-04 showed `克劳德猎手: 1 NEW / 11 entries`.
- **PNG**: derives correctly (md→html→png via `html-to-long-image.py`) in the
  build stage, and `finalize-local.py` now copies it into `sent/<date>.png`
  when the processed PNG exists. It does not re-render or call the LLM.

## Latest proof run

Controlled proof on **2026-06-04 19:32-19:36 Asia/Shanghai** after
folderization:
- `PARKIO_BATCH_ID=20260604 python3 build-digest.py` completed.
- Output: `~/park-io/inbox/processed/26-06-04/000-26-06-04.{md,html,png}`.
- LLM usage: 33,227 tokens over 65 calls, reasoning tokens 0.
- `PARKIO_BATCH_ID=20260604 python3 finalize-local.py` wrote
  `~/park-io/inbox/sent/26-06-04.{md,html,png}`.
- `PARKIO_BATCH_ID=20260604 PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py`
  passed: 19 events, 10 push URLs. It warned about one duplicate visible URL
  (`https://x.com/ClaudeDevs/status/2062274312363770064`) but did not fail.
- After the post-proof WeWe source fix, `python3 fetch-wechat-rss.py` showed
  `克劳德猎手: 1 NEW / 11 entries`, and `python3 channel-health.py` showed no DOWN
  sources. `Ray在思考` remains STALE, intentionally low priority.

## How to run / verify
```bash
python3 -m py_compile summarize.py digest_config.py lib.py quality-check.py fetch-douyin.py
for t in tests/test_*.py; do python3 "$t"; done
# regenerate a batch (writes ~/park-io/inbox/processed/<date>/000-<date>.{md,html,png}):
PARKIO_BATCH_ID=20260604 python3 build-digest.py              # → processed/<date>/000-<date>.{md,html,png}
PARKIO_BATCH_ID=20260604 python3 finalize-local.py            # → sent/<date>.{md,html,png}
PARKIO_BATCH_ID=20260604 PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py
python3 channel-health.py                                     # truthful per-channel state
```
All `tests/test_*.py` pass; `check-quality` passes on the regenerated 06-04.

## Claude Code review result

Claude Code CLI review returned **no blocking findings**. It specifically
checked stale same-directory subprocess paths, root wrapper import/monkeypatch
compatibility, `push-digest.sh` / `fetch.py` command breakage, and
contract/workflow path drift. No files were edited by Claude.
