# ingestion/douyin

Douyin ingestion owns Douyin source discovery, delivery-state rules, and raw video item normalization.

## Current Root Entrypoint

- `fetch-douyin.py`

## Inputs

- Active `platform=douyin` source rows from `~/park-io/sources.md`.
- `content-toolkit` runtime dependency outside this repo.

## Outputs

- Standard ingestion artifacts with `channel=douyin`.
- Items use `content_kind=video`.

## Boundary

Douyin owns source discovery and late-first-seen delivery rules. Media transcript/summary/publishability belongs in `enrichment/media/`.
