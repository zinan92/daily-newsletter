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
- `finalize-local.py` (legacy split-artifact compatibility)
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
- Source-health state.

## Outputs

- Intermediate brief/deep/product radar Markdown under `~/park-io/_inbox/processed/<YY-MM-DD>/`.
- One durable reader Markdown under `~/park-io/006_ai daily newsletter/<YY-MM-DD>.md`.
- No final reader HTML/PNG artifacts by default.

## Boundary

Aggregation does not fetch sources. It reads normalized upstream artifacts and produces the daily product.
