# Session Summary — Park-IO Daily Newsletter Takeover

A long working session that took over the inbox pipeline from a thrashing state
and stabilized it: root-caused today's failures, fixed them by cause (not
symptom), and built the safety net that was missing.

## The starting situation

The daily 08:30 newsletter didn't push. Underneath that were eight reported
problems and a deeper meta-problem: **the project had no version control and no
tests**, so every Codex edit risked breaking something else silently. A
2271-line `summarize.py`, 7 copy-pasted LLM clients, and stale hardcoded titles
made the code "break one thing, break another."

## The single biggest insight

Today's problems #2, #3, #4 were **not three bugs — they were one**. Every
script hit the same `localhost:8317` endpoint with its own copy-pasted
`llm_call` and **no retry**. When that endpoint had a transient 502:
- scoring failed → 238 items unscored,
- summarization failed → Chinese rewriting fell back to raw English,
- AI quality-check failed too.

One endpoint blip = the whole product line collapsed. That reframed the work
from "patch symptoms" to "fix the cascade + build a safety net."

## What we did (15 atomic commits, each reversible)

| Area | Before | After |
|---|---|---|
| **Version control** | none — couldn't roll back | `git` initialized; secrets/state gitignored |
| **08:30 push** | blocked by meta-leak (`公众号:`/`作者:` in body) | gate passes legitimately; meta stripped everywhere |
| **Stale titles** | "Fast Mode 更新" on Opus 4.8 content | titles derived from real content, in Chinese |
| **English in body** | "To learn more, see our docs…" | suppressed; Chinese-only fallback |
| **Official on outage** | suppressed when scoring 502'd | `bypasses_score()` keeps official/manual/media |
| **LLM client** | 7 copy-pasted, no retry, silent fail | 1 shared `lib.llm_call` with retry + typed `LLMUnavailable` |
| **Scoring outage** | silent — looked like an empty day | `scoring-health.json` + log + dashboard banner |
| **X threads** | one thread split into many events | merged via `conversation_id` |
| **Empty X items** | title-only stubs | excluded from the body |
| **WeChat meta** | prepended into article content | stored as structured fields |
| **Regression safety** | none | 6 test suites + deterministic quality gate |
| **Agent guidance** | `AGENTS.md` fought the v12 workflow | rewritten to match; `GOTCHAS.md` checklist added |

## Mapping to the reported problems

- **#1 push blocked** ✅ meta-leak fixed at source + centralized cleaning
- **#2 scoring 502 cascade** ✅ retry + visible degradation
- **#3 official suppressed** ✅ score bypass extracted, verified by test
- **#4 English summaries** ✅ Chinese-only fallback + gate check
- **#5 stale title reuse** ✅ hardcoded title map removed
- **#6 thread reply split** ✅ conversation_id merge (future fetches)
- **#7 incomplete cleaning** ✅ single `strip_source_meta()` on all paths
- *(scoring transient outage)* — proven transient; resilience added

## The benefits, concretely

**Before:** unversioned code, no tests, one endpoint blip took down the whole
newsletter, stale titles and English leaked into a "Chinese-only" product, and a
scoring outage was indistinguishable from a slow news day.

**After:**
1. **It can't silently regress.** 6 test suites + a deterministic quality gate
   catch the exact failures we fixed. Two latent breaks were caught *during*
   this session by that net.
2. **One endpoint blip no longer collapses the product.** Retry absorbs
   transient 502s; when it truly fails, official/manual/media still ship and the
   outage is visible, not silent.
3. **The "Chinese-only" promise holds.** Titles and bodies are content-derived
   Chinese; raw English is blocked at the gate.
4. **Edits are safe again.** `git` for rollback, `GOTCHAS.md` as the pre-edit
   checklist, and `AGENTS.md` aligned with the real v12 workflow contract (it
   had been instructing agents to undo it).

## Verification

Every fix was verified on the **real** 26-05-30 batch via full digest rebuilds:
the deterministic quality gate goes from FAIL→blocked to **PASS (exit 0)**, with
content-derived Chinese titles and no English leak. The AI quality-check's two
`title_body_mismatch` findings were eliminated.

## Still open (tracked, low priority)

- **#23** — surface WeChat auto-feed success/failure on the status dashboard.
- **#10** — a semantic-similarity replacement for the keyword merge cascade
  (kept for now because it currently produces net-positive merges).
