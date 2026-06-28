# ingestion/rss

RSS ingestion owns generic RSS/Atom sources that behave like ordinary article feeds.

## Current Root Entrypoint

- `fetch-rss.py`

## Inputs

- Active `platform=rss` source rows from `~/park-io/_source management/sources.md`.
- Feed URLs for official blogs, podcasts, YouTube feeds, and other RSS-compatible sources.

## Outputs

- Standard ingestion artifacts with `channel=rss`.
- Existing compatibility output remains `~/park-io/_inbox/unprocessed/<date>-<profile>.md` until later phases move writers.

## Boundary

RSS should not apply release-specific changelog logic or media transcript enrichment. Those move to `ingestion/release_feed/` and `enrichment/media/`.
