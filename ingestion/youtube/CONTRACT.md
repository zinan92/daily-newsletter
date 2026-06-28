# ingestion/youtube

YouTube ingestion owns video feed discovery and metadata normalization.

## Current Root Entrypoints

- Currently generic YouTube RSS discovery is routed through `fetch-rss.py`.
- Transcript and summary work is in `fetch-media-transcripts.py`.

## Inputs

- YouTube RSS/feed source rows from `~/park-io/_source management/sources.md`.
- YouTube cookie/runtime dependencies outside git when media download is needed.

## Outputs

- Standard ingestion artifacts with `channel=youtube`.
- Items use `content_kind=video`.

## Boundary

YouTube ingestion discovers candidate media. Download, transcript cleanup, deep summary, and publishability are owned by `enrichment/media/`.
