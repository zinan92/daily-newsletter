# ingestion/web_scrape

Web scrape ingestion owns official web pages that are not reliable generic feeds.

## Current Root Entrypoint

- `fetch-scrape.py`

## Inputs

- Active scrape source rows from `~/park-io/_source management/sources.md`.
- Site-specific sitemap or article listing pages.

## Outputs

- Standard ingestion artifacts with `channel=web_scrape`.
- Compatibility output remains the existing unprocessed markdown files.

## Boundary

This folder owns selector/sitemap drift and scrape health. It does not own RSS, GitHub release parsing, or final digest grouping.
