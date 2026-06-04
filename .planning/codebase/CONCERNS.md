# Codebase Concerns

**Analysis Date:** 2026-06-04

## Tech Debt

**Large Root-Level Scripts:**
- Issue: Core behavior is concentrated in large root-level scripts instead of smaller importable modules.
- Files: `summarize.py` (2096 lines), `generate-status.py` (1002 lines), `lib.py` (800 lines), `fetch-media-transcripts.py` (664 lines), `fetch-scrape.py` (504 lines), `push-telegram.py` (489 lines), `quality-check.py` (375 lines).
- Impact: Changes to rendering, routing, LLM calls, source health, and delivery state have wide blast radius and require careful regression coverage.
- Fix approach: Extract pure functions only when changing a touched area; keep existing CLI entrypoints stable and add focused tests in `tests/`.

**Hyphenated Script Modules:**
- Issue: Production files such as `channel-health.py`, `source-health.py`, `fetch-douyin.py`, and `fetch-scrape.py` cannot be imported by normal Python module names.
- Files: `tests/test_channel_health.py`, `tests/test_source_health.py`, `tests/test_douyin_delivery.py`, `tests/test_scrape_sitemap.py`.
- Impact: Tests need `importlib.util.spec_from_file_location`, which is easy to copy incorrectly and makes shared fixtures awkward.
- Fix approach: Preserve script filenames for CLI compatibility; when refactoring, move reusable logic into underscore-named modules and keep hyphenated files as thin wrappers.

**Configuration Outside Repo:**
- Issue: Source configuration and runtime data are outside this repository.
- Files: `README.md`, `lib.py`, `fetch-all.sh`, `push-digest.sh`, `source-health.py`.
- External paths: `~/park-io/sources.md`, `~/park-io/inbox/`, `~/park-io/library/`, `~/park-io/secrets/`.
- Impact: Unit tests can pass while an operator run fails because external source rows, cookies, or state files are stale.
- Fix approach: Keep tests for pure behavior in `tests/`; verify production readiness with `python3 channel-health.py`, `python3 check-pipeline-health.py`, and a batch-specific `check-quality.py` run.

## Known Bugs

**WeChat RSS Subscription Gaps:**
- Symptoms: A WeChat source can be registered locally but remain seed-only or frozen because the WeWe RSS subscription/feed is missing or stale.
- Files: `fetch-wechat-rss.py`, `fetch-wechat.py`, `source-health.py`, `check-pipeline-health.py`, `GOTCHAS.md`, `HANDOVER.md`.
- Trigger: WeWe RSS bridge is unreachable, a feed freezes, or a source row has a pending `rss_url`.
- Workaround: Use manual links for important WeChat articles; refresh/re-subscribe in WeWe RSS and confirm `source-health.py` reports the source as healthy.

**PNG Not Produced In Default Local Run:**
- Symptoms: Daily local finalize writes Markdown/HTML but not a PNG when Telegram send is skipped.
- Files: `push-digest.sh`, `finalize-local.py`, `push-telegram.py`, `html-to-long-image.py`, `HANDOVER.md`.
- Trigger: Default `PARKIO_SKIP_SEND=1` path runs `finalize-local.py` and skips `send-artifacts.py`, where PNG rendering currently lives.
- Workaround: Run the send/render path explicitly if a PNG is needed, or add a dedicated PNG render stage to `push-digest.sh` / `finalize-local.py`.

**Digest Can Skip When Fetch Lock Hangs Past 60 Minutes:**
- Symptoms: The daily digest exits successfully with "skip this digest" if `logs/fetch.lock` still points to a live process after 60 minutes.
- Files: `push-digest.sh`, `logs/fetch.lock`, `check-pipeline-health.py`.
- Trigger: Slow or stuck fetch job overlaps the morning digest window.
- Workaround: `check-pipeline-health.py` alerts if the digest is not sent and `push-digest` is not genuinely still running.

## Security Considerations

**Local Auth File In Repo Root:**
- Risk: `twitter-auth.env` exists in the repo root and contains X/Twitter auth material.
- Files: `twitter-auth.env`, `.gitignore`, `fetch-twitter.py`, `fetch-twitter-saved.py`, `refresh-twitter-auth.py`.
- Current mitigation: `.gitignore` excludes `*.env` and `twitter-auth.env`; fetch scripts load only expected keys from the file.
- Recommendations: Never read or print `twitter-auth.env`; keep file permissions restrictive; verify it remains ignored before commits with `git status --short --ignored twitter-auth.env`.

**Secrets Loaded From Environment Or `~/park-io/secrets`:**
- Risk: LLM, Telegram, Douyin, and YouTube credentials/cookies are required for production runs and can leak through logs or accidental file reads.
- Files: `lib.py`, `push-telegram.py`, `fetch-douyin.py`, `fetch-media-transcripts.py`, `README.md`.
- Current mitigation: `lib._load_secret()` reads env or local secret files; `.gitignore` excludes runtime state and env files; README instructs local secret storage.
- Recommendations: Do not add secret defaults to source; avoid logging full request headers, bot URLs, cookie paths with values, or env values.

**Telegram Bot URL Construction:**
- Risk: Telegram API URLs include the bot token in the request URL.
- Files: `push-telegram.py`, `lib.py`.
- Current mitigation: Tokens come from `_load_secret()` and are not hardcoded; default daily run skips Telegram via `PARKIO_SKIP_SEND=1`.
- Recommendations: Do not print `req.full_url` on Telegram failures; keep exception logging sanitized.

## Performance Bottlenecks

**LLM-Heavy Digest Build:**
- Problem: Digest generation depends on repeated LLM calls for scoring, summaries, semantic clustering, and quality review.
- Files: `lib.py`, `score-items.py`, `summarize.py`, `digest_events.py`, `ai-quality-check.py`.
- Cause: Network LLM calls plus optional DeepSeek thinking mode can dominate runtime.
- Improvement path: Keep `lib.DEEPSEEK_THINKING` disabled by default; use `tests/test_llm_fallback.py` to protect timeout/thinking behavior; cache only where correctness boundaries are explicit.

**Media Transcript Pipeline:**
- Problem: Video/podcast transcription can be slow or fail on download, cookie, duration, subtitle, or ASR steps.
- Files: `fetch-media-transcripts.py`, `polish-douyin.py`, `fix-asr-errors.py`, `tests/test_media.py`, `tests/test_alerts.py`.
- Cause: `yt-dlp`, cookies, Douyin adapter, local ASR, and LLM polish are all runtime dependencies.
- Improvement path: Keep retryable failed media records visible; preserve `tests/test_alerts.py` coverage so transient failures do not stick forever.

**Status Generation Complexity:**
- Problem: `generate-status.py` is over 1000 lines and reads multiple runtime state files.
- Files: `generate-status.py`, `source-health.json`, `media-queue.json`, `media-summaries.json`, `scoring-health.json`, `state.json`.
- Cause: Status page combines fetch state, scoring health, channel health, and dependency checks.
- Improvement path: Add focused tests for any new status section in `tests/test_health_dashboard.py` or a new `tests/test_status_*.py`.

## Fragile Areas

**Reader-Facing Product Quality:**
- Files: `summarize.py`, `digest_text.py`, `quality-check.py`, `tests/test_cleaning.py`, `tests/test_chinese_fallback.py`, `tests/test_titles.py`, `GOTCHAS.md`.
- Why fragile: The product must be a Chinese, value-first daily digest; raw English, metadata, source labels, AI refusal text, stale titles, and internal workflow artifacts are all known failure modes.
- Safe modification: Run the full test loop plus `PARKIO_BATCH_ID=<batch> PARKIO_SKIP_AI_QUALITY=1 python3 check-quality.py` after changing rendering, title, cleaning, or summary logic.
- Test coverage: Good deterministic regression coverage exists for known leaks; no snapshot test verifies a complete real daily Markdown/HTML pair.

**Score Bypass And Outage Degradation:**
- Files: `summarize.py`, `score-items.py`, `scoring-health.json`, `generate-status.py`, `tests/test_bypass.py`, `tests/test_alerts.py`.
- Why fragile: A scoring outage can assign low/zero scores; official, code, key people, saved, WeChat, and media sources must still surface.
- Safe modification: Keep `summarize.bypasses_score()` behavior locked by `tests/test_bypass.py`; keep scoring outages visible through `scoring-health.json`.
- Test coverage: Good for bypass groups; weaker for full end-to-end "scoring failed but digest still useful" behavior.

**Source Health Truthfulness:**
- Files: `channel-health.py`, `source-health.py`, `check-pipeline-health.py`, `generate-status.py`, `tests/test_channel_health.py`, `tests/test_source_health.py`.
- Why fragile: A fetch can run and still be broken; "0 new" must not hide DOWN or STALE upstream feeds.
- Safe modification: Preserve distinctions among `DOWN`, `STALE`, `QUIET`, `NEW`, `UNKNOWN`, and `failed`.
- Test coverage: Good for parser/classifier regressions; live service health still depends on logs and external feeds.

**X/Twitter Fetching And Auth:**
- Files: `fetch-twitter.py`, `fetch-twitter-saved.py`, `refresh-twitter-auth.py`, `twitter-auth.env`, `tests/test_thread_merge.py`, `tests/test_empty_x.py`.
- Why fragile: Local auth cookies expire; quotes/retweets/nested tweets and threads must be normalized correctly.
- Safe modification: Do not read or print `twitter-auth.env`; refresh auth only via `refresh-twitter-auth.py` from a logged-in desktop session; run thread and empty-X tests after parser changes.
- Test coverage: Covers thread merge and empty bodies; does not hit live X endpoints.

**Douyin Delivery State:**
- Files: `fetch-douyin.py`, `fetch-media-transcripts.py`, `media-queue.json`, `media-summaries.json`, `tests/test_douyin_delivery.py`, `tests/test_alerts.py`.
- Why fragile: Delivery, archival, transcription, and retry state are distinct; a late-first-seen video can be archived without appearing if these states are mixed.
- Safe modification: Keep `awemes_to_deliver()` keyed on delivered IDs and recency window, not just library archival state.
- Test coverage: Good for late-first-seen delivery; live coverage depends on cookies and Douyin adapter availability.

**Manual Links And WeChat Reliability:**
- Files: `fetch-manual-links.py`, `fetch-wechat-rss.py`, `fetch-wechat-exporter.py`, `GOTCHAS.md`, `README.md`.
- Why fragile: WeChat official feed access is mediated by WeWe RSS and may expire; manual links are the reliable fallback path.
- Safe modification: Keep `manual-links.md` as the operational fallback and make source health failures explicit.
- Test coverage: `tests/test_source_health.py` covers bridge false-green; there is no dedicated test for manual link state transitions.

## Scaling Limits

**Single-Machine Cron/Launchd Pipeline:**
- Current capacity: Designed for a daily local pipeline with `fetch-all.sh` every 4 hours and `push-digest.sh` once daily.
- Limit: Long fetches, local service outages, or auth expiry can block the daily run.
- Scaling path: Keep lock handling in `push-digest.sh`, add source-level timeouts when expanding fetchers, and surface failures through `check-pipeline-health.py`.

**State Files Grow In Repo Working Tree:**
- Current capacity: Runtime JSON files are present in the repo root but ignored by git.
- Files: `scores.json`, `state.json`, `tg-push-state.json`, `source-health.json`, `media-queue.json`, `media-summaries.json`, `x-saved-items.json`, `x-saved-source-candidates.json`, `x-saved-state.json`.
- Limit: Large JSON state files slow local inspection and can make accidental edits/noisy diffs more likely if ignore rules are broken.
- Scaling path: Keep runtime files ignored; prefer bounded reads and deterministic cleanup/compaction scripts if state size grows.

## Dependencies at Risk

**WeWe RSS / Colima / Docker:**
- Risk: Local bridge at `localhost:4000` can be down or feed accounts can freeze.
- Impact: WeChat public account sources silently stop updating unless health checks catch it.
- Migration plan: Keep WeWe RSS as primary, manual links as fallback, and add source-specific alerts when a high-value account is frozen.

**Twitter/X Auth:**
- Risk: `twitter-auth.env` cookies expire or become invalid.
- Impact: All tracked X accounts and saved X imports can fail.
- Migration plan: Refresh via `refresh-twitter-auth.py`; keep auth file local and ignored.

**DeepSeek / CLIProxy LLM Providers:**
- Risk: 429/5xx/SSL errors can interrupt scoring and summarization; 401/400 config errors must not be hidden.
- Impact: Digest quality drops or generation fails.
- Migration plan: Preserve `lib.llm_call()` failover semantics and `tests/test_llm_fallback.py`; keep `PARKIO_LLM_FALLBACK_PROVIDER` explicit.

**Content Toolkit / yt-dlp / Local ASR:**
- Risk: External download/transcription tooling changes, cookies expire, or duration limits skip media.
- Impact: Podcast, YouTube, and Douyin sections lose high-value videos.
- Migration plan: Keep media failure alerts and retries; document any replacement path in `README.md` and add tests around state transitions.

## Missing Critical Features

**Automated Full Artifact Regression:**
- Problem: Tests cover many pure functions but do not build a full synthetic batch and assert the final Markdown/HTML/PNG contract.
- Blocks: Confident refactors of `summarize.py`, `quality-check.py`, `finalize-local.py`, and `push-telegram.py`.

**Dedicated Manual Links Tests:**
- Problem: Manual links are operationally important but lack a focused regression file.
- Blocks: Safe changes to `fetch-manual-links.py` state transitions among Pending, Imported, and Failed.

**Dedicated Workflow Files Missing From Repo Listing:**
- Problem: `AGENTS.md` references `inbox-workflow.yaml`, `render-workflow-diagram.py`, and `/Users/wendy/park-io/inbox/validate-workflow.py`, but those workflow files were not present in the inspected root file list.
- Blocks: Local validation of the workflow diagram contract from this repo alone.

## Test Coverage Gaps

**End-To-End Daily Pipeline:**
- What's not tested: `open-batch.py` → `score.py` → `build-digest.py` → `check-quality.py` → `archive-items.py` → `finalize-local.py` as one synthetic run.
- Files: `push-digest.sh`, `open-batch.py`, `score.py`, `build-digest.py`, `archive-items.py`, `finalize-local.py`.
- Risk: Stage interfaces can drift while unit tests pass.
- Priority: High.

**Telegram Send Path:**
- What's not tested: `send-artifacts.py` and `push-telegram.py` delivery behavior with sanitized token handling and URL/content dedupe.
- Files: `send-artifacts.py`, `push-telegram.py`, `tg-push-state.json`.
- Risk: Telegram re-enable can resend duplicates or leak operational details.
- Priority: Medium.

**Complete HTML/PNG Parity:**
- What's not tested: PNG rendering from final HTML and visual parity with Markdown.
- Files: `html-to-long-image.py`, `summarize.py`, `quality-check.py`, `push-telegram.py`.
- Risk: Markdown passes but HTML/PNG is missing content, has excess whitespace, or diverges visually.
- Priority: Medium.

**Live Source Fetchers:**
- What's not tested: Real RSS, scrape, X, WeChat, Douyin, and media transcript calls.
- Files: `fetch-rss.py`, `fetch-scrape.py`, `fetch-twitter.py`, `fetch-twitter-saved.py`, `fetch-wechat-rss.py`, `fetch-douyin.py`, `fetch-media-transcripts.py`.
- Risk: Upstream markup/API/auth changes break production while offline tests pass.
- Priority: High.

**External Source Configuration:**
- What's not tested: Compatibility of `~/park-io/sources.md` with `digest_config.py`, `lib.load_sources()`, and all fetchers.
- Files: `digest_config.py`, `lib.py`, `source-health.py`, `fetch-all.sh`.
- Risk: A source row typo or pending RSS URL can remove content without code changes.
- Priority: High.

## Product-Quality Risks

**Reader Value Can Regress Into Internal Recap:**
- Risk: The daily digest can become an implementation/status recap instead of a Chinese reader-facing product.
- Files: `summarize.py`, `prompts/summarize-blogs.md`, `prompts/summarize-tweets.md`, `prompts/digest-intro.md`, `README.md`.
- Current mitigation: `quality-check.py` blocks many internal/meta leaks; memory and docs emphasize Chinese/value-first output.
- Recommendation: Review generated `~/park-io/inbox/sent/<date>.md` as the acceptance artifact after major prompt/rendering changes.

**Duplicate Or Stale Content In Daily Digest:**
- Risk: Cross-source semantic merge, title generation, and URL dedupe can duplicate the same update or reuse stale titles.
- Files: `digest_events.py`, `summarize.py`, `push-telegram.py`, `tests/test_thread_merge.py`, `tests/test_titles.py`.
- Current mitigation: Semantic clustering, thread merge tests, stale-template tests, and push marker dedupe.
- Recommendation: Keep high-value summary short and details in release-specific sections to avoid repeated bullets.

**Health Noise Or False Green:**
- Risk: Too much health detail in the reader body reduces product value; too little hides broken channels.
- Files: `channel-health.py`, `source-health.py`, `generate-status.py`, `summarize.py`, `tests/test_health_dashboard.py`.
- Current mitigation: Source health is treated as owner/status data; digest surface uses a compact health dashboard.
- Recommendation: Add/modify health details in status surfaces first, not the consumer body.

---

*Concerns audit: 2026-06-04*
