# GSD State: Park-IO Daily AI Digest

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-04)

**Core value:** Every morning the owner gets one trustworthy Chinese AI intelligence digest that is worth reading, with enough source-health visibility to know whether silence means no news or a broken channel.

**Current focus:** Phase 3 - Health Visibility Closure

## Current Position

- Codebase map completed and committed.
- Brownfield planning baseline created from repo-local docs.
- Phase 2 - Local Artifact Parity completed: local sent artifacts now include Markdown, HTML, and PNG when processed artifacts exist.
- Next implementation target should be Phase 3 - Health Visibility Closure.

## Locked Decisions

<decisions>
- Markdown is the single content source for HTML and PNG.
- No Telegram by default; local sent artifacts are the owner path.
- DeepSeek -> CLIProxy/Sonnet is the only fallback; other failures must surface.
- Source routing is deterministic; AI does not decide which section an item belongs to.
- Curated Douyin/podcast/video sources are valuable by default but enter reader body only when transcript and summary are good.
</decisions>

## Known Risks

- `GOTCHAS.md` still contains older wording saying source health stays out of newsletter body, while the newer owner contract wants a compact digest health dashboard.
- WeWe RSS owner actions remain unresolved: Ray在思考 frozen feed and 克劳德猎手 pending RSS subscription.
- If processed PNG rendering fails upstream, local finalization warns and continues with Markdown/HTML.
- External auth dependencies can expire: WeWe, YouTube cookies, Twitter auth, Douyin cookies.

## Verification Baseline

Use this command set before claiming a shipping milestone:

```bash
python3 -m py_compile summarize.py digest_config.py lib.py quality-check.py fetch-douyin.py
for t in tests/test_*.py; do python3 "$t"; done
PARKIO_BATCH_ID=20260604 PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py
python3 channel-health.py
```

## Next Command

Next recommended planning command:

```text
$gsd-plan-phase 3 --tdd
```

This should produce the next atomic plan: health visibility closure and doc reconciliation.

---
*State initialized: 2026-06-04 after GSD brownfield planning bootstrap.*
