# ingestion/x

X ingestion owns Twitter/X account and saved-post collection.

## Current Root Entrypoints

- `fetch-twitter.py`
- `fetch-twitter-saved.py`

## Inputs

- Active Twitter source rows from `~/park-io/_source management/sources.md`.
- X auth/session configuration outside git.

## Outputs

- Standard ingestion artifacts with `channel=x`.
- Items use `content_kind=post`.

## Channel-Specific Workflow

- Preserve thread/conversation identity.
- Preserve quote/link metadata as item metadata.
- Future quoted-article extraction belongs in `enrichment/quoted_article/`, not directly in the fetcher.

## Pacing

- X limits how many profile timelines one session can pull per short window (measured 2026-09-21: 33 of 44 succeed, the rest fail with `Failed to init ClientTransaction`).
- Each run pulls at most `PARKIO_TWITTER_MAX_PER_RUN` (default 30) accounts, least-recently-checked first (`checked_at` in state.json); the rest wait for the next hourly run.
- Two consecutive rate-limit errors end the run early instead of spending ~40s per remaining account.

## Boundary

X ingestion fetches and normalizes posts. It does not decide final digest sections or write reader-facing summaries.
