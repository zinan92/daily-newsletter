# Park-IO Daily — Regression Gotchas

Hard-won invariants. Before editing `summarize.py`, `digest_events.py`,
`quality-check.py`, `fetch-twitter.py`, `score-items.py`, `push-telegram.py`,
or `fetch-wechat.py`, check the change against this list.

**Enforcement legend**
- 🟢 **gate** — `quality-check.py` blocks the push deterministically
- 🧪 **test** — locked by a `tests/` regression test
- 🔵 **code** — implemented in the pipeline (verified), no explicit lock yet
- 🟡 **partial** — partially handled; remaining work noted
- ⚪ **manual** — discipline / convention, not automated

Run all tests: `for t in tests/test_*.py; do python3 "$t"; done`

---

| # | Invariant | Status | Where |
|---|-----------|--------|-------|
| 1 | Official channels never depend on score (survive a 502 outage) | 🧪🔵 | `summarize.bypasses_score()` · `tests/test_bypass.py` |
| 2 | Manual input (saved / manual links / WeChat) never filtered | 🧪🔵 | `bypasses_score()` (saved/wechat groups) · `test_bypass.py` |
| 3 | Podcast / YouTube / 抖音 not scored like ordinary feed | 🧪🔵 | `bypasses_score()` (media/video) · `test_bypass.py` |
| 4 | No ops/meta in consumer body (公众号/作者/WeChat ID/Source/…) | 🟢🧪 | `quality-check.py` BAD/METADATA_PATTERNS · `digest_text.strip_source_meta()` · `test_cleaning.py` |
| 5 | Final body must be Chinese, never raw English | 🟢🧪 | `has_chinese()` guards + Chinese fallback · `quality-check.raw_english_body_lines()` · `test_chinese_fallback.py` |
| 6 | No stale-title pollution; titles from current content | 🧪 | `event_title()` (map removed) + `display_title()` · `test_titles.py` |
| 7 | Dedup only within today's batch | 🔵 | `read_today_items()` within-batch dedupe; `state.json` status-only |
| 8 | X quote/retweet: prefer the quoted long content | 🔵 | `fetch-twitter.nested_tweets()` / `tweet_text()` |
| 9 | X thread replies merge into one event, not split | 🧪 | `fetch-twitter` captures `conversation_id`; `build_events` merges same-thread · `test_thread_merge.py` (future fetches only) |
| 10 | Cross-source merge only on URL/thread/semantic, not keyword alone | 🔵 | `digest_events._semantic_cluster` (v4-pro judgment) replaced the ~40 hardcoded keyword rules; `event_key` is now unique-by-default. Kill switch: `PARKIO_SEMANTIC_CLUSTER=0`; safe fallback (no merge) on LLM failure |
| 11 | Section structure fixed; ordinary X not in official section | 🔵 | `summarize.py` `official_plus_raw` excludes app-layer |
| 12 | Empty sections hidden on consumer page | 🔵 | `render_html_*_card()` return "" on empty |
| 13 | HTML / Markdown / PNG share cleaning + content | 🔵 | shared `render_panel`/`render_html_panel`; PNG from HTML |
| 14 | PNG trims trailing whitespace | 🔵 | `html-to-long-image.trim_bottom_whitespace()` |
| 15 | `sent/` keeps only `YY-MM-DD.md`; HTML/PNG transient | 🔵 | `push-telegram.move_sent_artifacts()` |
| 16 | Stable file naming `YY-MM-DD`, no 早/晚/hhmm | ⚪ | convention |
| 17 | Manual links: single `manual-links.md` (Pending/Imported/Failed) | ⚪ | convention · `fetch-manual-links.py` |
| 18 | Library: `library/profiles/<id>/items/`, no legacy layers | ⚪ | convention |
| 19 | Workflow diagram is a closed system | 🔵 | `validate-workflow.py`. **Note:** v12 contract = 4 independent paths (see `inbox-workflow.yaml`); `AGENTS.md` updated to match |
| 20 | Quality gate is deterministic first, AI second | 🟢 | `quality-check.py` (hard) → `ai-quality-check.py` (non-blocking) |
| 21 | Scoring outage degrades but is NOT silent | 🟢🔵 | bypass keeps official/manual/media · `score-items` writes `scoring-health.json` + log · `generate-status` shows banner |
| 22 | Source health on owner page, not newsletter body | 🔵 | `health` isolated from `render_panel` body |
| 23 | WeChat auto-fetch is fragile; manual links reliable | 🟡 | manual path reliable. **TODO**: surface auto-feed success/failure in status |
| 24 | Empty-content X items don't enter consumer body | 🧪 | `x_item_has_content()` skips link-only single-X events · `test_empty_x.py` |

---

## Open items (tracked)

- **#23** — Surface WeChat auto-feed success/failure in the status dashboard
  (manual-links path is already reliable). The only remaining 🟡.
- **#10 (cross-source semantic merge)** — the keyword cascade is kept because it
  currently produces net-positive merges; a semantic-similarity replacement is a
  future improvement, not a present bug.

## How this maps to the workflow contract

`inbox-workflow.yaml` (v12) is the behavioral contract: four independent paths
(official / X application / media / saved+manual), each from entry to its
Section sink. Nodes are typed `script | ai | local_model | human | sink`.
Routing is deterministic; AI acts only *inside* nodes (scoring, summaries, QC).
This file lists the invariants those paths must preserve.
