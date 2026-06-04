# ingestion/x

X ingestion owns Twitter/X account and saved-post collection.

## Current Root Entrypoints

- `fetch-twitter.py`
- `fetch-twitter-saved.py`

## Inputs

- Active Twitter source rows from `~/park-io/sources.md`.
- X auth/session configuration outside git.

## Outputs

- Standard ingestion artifacts with `channel=x`.
- Items use `content_kind=post`.

## Channel-Specific Workflow

- Preserve thread/conversation identity.
- Preserve quote/link metadata as item metadata.
- Future quoted-article extraction belongs in `enrichment/quoted_article/`, not directly in the fetcher.

## Boundary

X ingestion fetches and normalizes posts. It does not decide final digest sections or write reader-facing summaries.
