# ingestion/manual_links

Manual link ingestion owns owner-provided URLs.

## Current Root Entrypoints

- `fetch-manual-links.py`
- `fetch-wechat.py` for seeded/manual WeChat article handling

## Inputs

- Manual link files under `~/park-io/`.
- Seed URLs in `~/park-io/sources.md`.

## Outputs

- Standard ingestion artifacts with `channel=manual_links`.
- Items use `content_kind=manual_link` or `article`.

## Boundary

Manual ingestion preserves owner intent and should bypass ordinary source score filtering where appropriate. It does not own automated WeWe RSS fetching.
