# GSD State: Park-IO Daily AI Digest

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-04)

**Core value:** Every morning the owner gets one trustworthy Chinese AI intelligence digest that is worth reading, with enough source-health visibility to know whether silence means no news or a broken channel.

**Current focus:** Milestone complete - waiting for next owner-selected milestone

## Current Position

- Codebase map completed and committed.
- Brownfield planning baseline created from repo-local docs.
- Phase 2 - Local Artifact Parity completed: local sent artifacts now include Markdown, HTML, and PNG when processed artifacts exist.
- Phase 3 - Health Visibility Closure completed: `Ray在思考` surfaces as stale, and `克劳德猎手` pending WeWe RSS setup surfaces as action-needed instead of being hidden by seed content.
- Phase 4 - Reader Quality Regression Lock completed: X title truncation, media publishability, active Douyin source routing, metadata/transcript leaks, raw English prose, narrator leakage, and Markdown/HTML divergence are covered by deterministic tests or gates.
- Phase 5 - End-To-End Daily Run Proof completed: the 2026-06-04 controlled batch regenerated, local sent Markdown/HTML/PNG were finalized, quality gate passed, and handover was refreshed.
- No remaining code blockers in this milestone.

## Locked Decisions

<decisions>
- Markdown is the single content source for HTML and PNG.
- No Telegram by default; local sent artifacts are the owner path.
- DeepSeek -> CLIProxy/Sonnet is the only fallback; other failures must surface.
- Source routing is deterministic; AI does not decide which section an item belongs to.
- Curated Douyin/podcast/video sources are valuable by default but enter reader body only when transcript and summary are good.
</decisions>

## Known Risks

- WeWe RSS owner actions remain unresolved: Ray在思考 frozen feed and 克劳德猎手 pending RSS subscription.
- If processed PNG rendering fails upstream, local finalization warns and continues with Markdown/HTML.
- External auth dependencies can expire: WeWe, YouTube cookies, Twitter auth, Douyin cookies.

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
Choose the next milestone, or resolve WeWe owner actions from HANDOVER.md.
```

The current stabilization milestone is complete.

---
*State updated: 2026-06-04 after Phase 5 end-to-end daily proof.*
