# GSD State: Park-IO Daily AI Digest

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-04)

**Core value:** Every morning the owner gets one trustworthy Chinese AI intelligence digest that is worth reading, with enough source-health visibility to know whether silence means no news or a broken channel.

**Current focus:** Phase 7 - Core Channel Folderization

## Current Position

- Codebase map completed and committed.
- Brownfield planning baseline created from repo-local docs.
- Phase 2 - Local Artifact Parity completed: local sent artifacts now include Markdown, HTML, and PNG when processed artifacts exist.
- Phase 3 - Health Visibility Closure completed: `Ray在思考` surfaces as stale, and pending WeWe RSS setup is action-needed instead of being hidden by seed content.
- Phase 4 - Reader Quality Regression Lock completed: X title truncation, media publishability, active Douyin source routing, metadata/transcript leaks, raw English prose, narrator leakage, and Markdown/HTML divergence are covered by deterministic tests or gates.
- Phase 5 - End-To-End Daily Run Proof completed: the 2026-06-04 controlled batch regenerated, local sent Markdown/HTML/PNG were finalized, quality gate passed, and handover was refreshed.
- Post-proof source fix completed: `克劳德猎手` WeWe RSS now uses `MP_WXS_3935644082`, fetches successfully, and is no longer a DOWN source.
- New milestone started: Daily Newsletter Source-Ingestion Decomposition.
- Owner decision: decompose by runtime channel/source adapter, not by final digest section.
- Root CLI/cron entrypoints must remain compatible until the refactor is fully proven.
- Phase 6 completed: contract files, folder skeleton, workflow spec, and contract tests are in place.

## Locked Decisions

<decisions>
- Markdown is the single content source for HTML and PNG.
- No Telegram by default; local sent artifacts are the owner path.
- DeepSeek -> CLIProxy/Sonnet is the only fallback; other failures must surface.
- Source routing is deterministic; AI does not decide which section an item belongs to.
- Curated Douyin/podcast/video sources are valuable by default but enter reader body only when transcript and summary are good.
</decisions>

## Known Risks

- `Ray在思考` remains STALE, but owner has marked it low priority.
- External auth dependencies can expire: WeWe, YouTube cookies, Twitter auth, Douyin cookies.
- If processed PNG rendering fails upstream, local finalization warns and continues with Markdown/HTML.

## Verification Baseline

Use this command set before claiming a shipping milestone:

```bash
python3 -m py_compile summarize.py digest_config.py lib.py quality-check.py fetch-douyin.py
for t in tests/test_*.py; do python3 "$t"; done
PARKIO_BATCH_ID=20260604 python3 build-digest.py
PARKIO_BATCH_ID=20260604 python3 finalize-local.py
PARKIO_BATCH_ID=20260604 PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py
python3 channel-health.py
```

## Next Command

Next recommended command:

```text
$gsd-plan-phase 7 --skip-research
```

This should create the atomic plan for core channel folderization.

---
*State updated: 2026-06-04 after Phase 6 contracts and skeleton.*
