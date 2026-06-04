# Daily Newsletter Contracts

This directory is the durable contract layer for the source-ingestion decomposition.

The refactor rule is:

1. Channel ingestion owns fetching and source-specific normalization.
2. Enrichment owns cross-channel post-processing, such as transcripts or quoted article extraction.
3. Aggregation owns the reader-facing digest.
4. Root scripts remain compatibility shims until every moved path is verified.

The current public product does not change: the daily run still produces local Markdown, HTML, and PNG artifacts.

## Standard Artifact

Every ingestion channel eventually emits an artifact matching `ingestion-artifact.schema.json`.

Required top-level fields:

- `schema_version`: contract version, currently `1`.
- `channel`: runtime channel such as `rss`, `x`, `wechat_rss`, or `douyin`.
- `source`: source identity and config-derived metadata.
- `run`: batch/run metadata.
- `items`: normalized candidate items for downstream scoring/enrichment/aggregation.
- `health`: source health for the run.
- `errors`: structured errors that should surface rather than silently degrade.

The artifact is intentionally channel-neutral. Channel-specific details belong under `item.metadata` or `source.metadata`, never in reader-facing `content`.
