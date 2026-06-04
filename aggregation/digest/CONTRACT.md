# aggregation/digest

Digest aggregation owns the final reader-facing product.

## Current Root Entrypoints

- `score.py`
- `score-items.py`
- `build-digest.py`
- `summarize.py`
- `quality-check.py`
- `archive-items.py`
- `finalize-local.py`

## Inputs

- Standardized ingestion artifacts.
- Enrichment artifacts.
- Scores and source-health state.

## Outputs

- Final Markdown digest.
- HTML derived from Markdown.
- PNG derived from HTML.
- Local sent artifact family under `~/park-io/inbox/sent/`.

## Boundary

Aggregation does not fetch sources. It reads normalized upstream artifacts and produces the daily product.
