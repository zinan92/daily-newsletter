# Phase 7: Core Channel Folderization - Context

**Gathered:** 2026-06-04
**Status:** Ready for execution
**Source:** Phase 6 contracts and wrapper compatibility audit

<domain>
## Phase Boundary

This phase moves the first set of core ingestion scripts into channel-owned folders while preserving the existing public CLI surface.

Core channels in scope:
- RSS: `fetch-rss.py` -> `ingestion/rss/run.py`
- Web scrape: `fetch-scrape.py` -> `ingestion/web_scrape/run.py`
- X timeline: `fetch-twitter.py` -> `ingestion/x/timeline.py`
- X saved items: `fetch-twitter-saved.py` -> `ingestion/x/saved.py`

Release feed remains a contract boundary in this phase because current release sources still route through generic RSS. Product-specific release parsing can move in a later implementation step.
</domain>

<compatibility>
## Compatibility Requirements

- Root scripts must remain callable by `fetch.py` and launchd.
- Root scripts must re-export functions used by `onboard-source.py`, `onboard-baseline.py`, `backfill-claude-blog-library.py`, and tests.
- Log basenames stay unchanged: `fetch-rss`, `fetch-scrape`, `fetch-twitter`, `fetch-twitter-saved`.
</compatibility>

---
*Phase: parkio-07-core-channel-folderization*
