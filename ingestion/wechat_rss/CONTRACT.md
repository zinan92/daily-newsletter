# ingestion/wechat_rss

WeChat RSS ingestion owns WeWe RSS bridge-backed public-account articles.

## Current Root Entrypoint

- `fetch-wechat-rss.py`
- `fetch-wechat-exporter.py` for external collector bridge imports

## Implementation

- `ingestion/wechat_rss/run.py`
- `ingestion/wechat_rss/exporter.py`

## Inputs

- Active WeChat source rows whose notes contain `rss_url <url>`.
- `wewe-rss` at `localhost:4000`.
- Optional exporter files under `PARKIO_WECHAT_EXPORT_DIR`.

## Outputs

- Standard ingestion artifacts with `channel=wechat_rss`.
- Items use `content_kind=article`.

## Boundary

This folder owns automated WeChat imports: WeWe feed fetching, feed freshness, exporter bridge imports, and pending RSS setup visibility. Manual one-off WeChat links belong in `ingestion/manual_links/`.
