# ingestion/wechat_rss

WeChat RSS ingestion owns WeWe RSS bridge-backed public-account articles.

## Current Root Entrypoint

- `fetch-wechat-rss.py`

## Inputs

- Active WeChat source rows whose notes contain `rss_url <url>`.
- `wewe-rss` at `localhost:4000`.

## Outputs

- Standard ingestion artifacts with `channel=wechat_rss`.
- Items use `content_kind=article`.

## Boundary

This folder owns WeWe feed fetching, feed freshness, and pending RSS setup visibility. Manual one-off WeChat links belong in `ingestion/manual_links/`.
