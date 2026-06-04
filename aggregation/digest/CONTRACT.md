# aggregation/digest

Digest aggregation owns the final reader-facing product.

## Current Root Entrypoints

- `score.py`
- `score-items.py`
- `build-digest.py`
- `summarize.py`
- `check-quality.py`
- `quality-check.py`
- `ai-quality-check.py`
- `archive-items.py`
- `finalize-local.py`
- `html-to-long-image.py`

## Implementation

- `aggregation/digest/score_stage.py`
- `aggregation/digest/score_items.py`
- `aggregation/digest/build.py`
- `aggregation/digest/summarize.py`
- `aggregation/digest/check_stage.py`
- `aggregation/digest/quality.py`
- `aggregation/digest/ai_quality.py`
- `aggregation/digest/archive.py`
- `aggregation/digest/finalize_local.py`
- `aggregation/digest/html_to_long_image.py`

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
