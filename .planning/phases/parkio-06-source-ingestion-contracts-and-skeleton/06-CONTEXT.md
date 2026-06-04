# Phase 6: Source Ingestion Contracts And Skeleton - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning
**Source:** Owner-approved source-ingestion decomposition milestone

<domain>
## Phase Boundary

This phase establishes the decomposition contract before production code is moved. The owner wants the source-code side of the Daily Newsletter pipeline decomposed by runtime channel/source adapter, while the final reader-facing output remains unchanged.

This phase should create folder boundaries, contracts, and workflow spec scaffolding. It should not move heavy production logic yet.
</domain>

<decisions>
## Locked Owner Decisions

- Use a monorepo folder decomposition, not separate Git repositories.
- Keep existing root CLI/cron entrypoints as compatibility shims.
- Preserve the current daily Markdown, HTML, and PNG output.
- Treat n8n as a future runtime representation; this milestone produces workflow-as-code first.
- Put shared ingestion primitives in `ingestion/common/`.
- Put media post-processing in `enrichment/media/`, not under ingestion.
- Split by runtime channel: RSS, web scrape, release feed, X, YouTube/media, Douyin, WeChat RSS, and manual links.
</decisions>

<target_layout>
## Target Layout

```text
contracts/
ingestion/
  common/
  rss/
  web_scrape/
  release_feed/
  x/
  youtube/
  douyin/
  wechat_rss/
  manual_links/
enrichment/
  media/
  quoted_article/
aggregation/
  digest/
workflow/
```
</target_layout>

<scope_fence>
## Scope Fence

Allowed files: `.planning/*`, `contracts/*`, `ingestion/*`, `enrichment/*`, `aggregation/*`, `workflow/*`, `README.md`, `HANDOVER.md`, tests for contracts.

Avoid moving root production scripts in this phase. Root script moves belong to later folderization phases.
</scope_fence>

---
*Phase: parkio-06-source-ingestion-contracts-and-skeleton*
*Context gathered: 2026-06-04*
