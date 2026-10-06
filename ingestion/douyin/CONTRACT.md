# ingestion/douyin

Douyin ingestion owns Douyin source discovery, delivery-state rules, and raw video item normalization.

## Current Root Entrypoint

- `fetch-douyin.py`

## Implementation

- `ingestion/douyin/run.py`

## Inputs

- Active `platform=douyin` source rows from `~/park-io/_source management/sources.md`.
- `vendor/content_downloader` (in this repo; deps in `requirements-full.txt`) plus `$PARKIO_HOME/_secrets/douyin-cookies.json`.

## Outputs

- Standard ingestion artifacts with `channel=douyin`.
- Items use `content_kind=video`.

## Boundary

Douyin owns source discovery and late-first-seen delivery rules. Media transcript/summary/publishability belongs in `enrichment/media/`.
