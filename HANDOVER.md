# Handover - Park-IO digest stabilization (2026-06-04)

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

Recent GSD commits:
- `a3a9863` - codebase map
- `0ebc923` - GSD planning baseline
- `832de12` - local PNG finalization
- `a4b347f` - pending WeWe RSS health visibility
- `1180f22` - reader quality contract test
- `b9fb41d` - Phase 5 proof plan

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
- **Ray在思考**: wewe-rss subscription `MP_WXS_3226075849` frozen since 2026-03-23.
  Refresh/re-subscribe in wewe-rss (localhost:4000), or confirm account dormant.
- **克劳德猎手**: `sources.md` `rss_url` is "pending WeWe subscription" — create the
  wewe-rss subscription for `gh_c4e5d8c9bdc6` and fill `rss_url`, else seed-only.
  The health layer now surfaces this as `WeWe RSS 未配置` instead of marking the
  seed article as a healthy automated feed.
- **PNG**: derives correctly (md→html→png via `html-to-long-image.py`) in the
  build stage, and `finalize-local.py` now copies it into `sent/<date>.png`
  when the processed PNG exists. It does not re-render or call the LLM.

## Latest proof run

Controlled proof on **2026-06-04 18:31-18:34 Asia/Shanghai**:
- `PARKIO_BATCH_ID=20260604 python3 build-digest.py` completed.
- Output: `~/park-io/inbox/processed/26-06-04/000-26-06-04.{md,html,png}`.
- LLM usage: 33,566 tokens over 67 calls, reasoning tokens 0.
- `PARKIO_BATCH_ID=20260604 python3 finalize-local.py` wrote
  `~/park-io/inbox/sent/26-06-04.{md,html,png}`.
- `PARKIO_BATCH_ID=20260604 PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py`
  passed: 19 events, 10 push URLs.
- `python3 channel-health.py` showed 1 DOWN (`克劳德猎手` pending WeWe RSS) and
  1 STALE (`Ray在思考` feed 73d old). These are owner/infra actions, not code
  blockers.

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
