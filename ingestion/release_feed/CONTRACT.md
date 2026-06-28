# ingestion/release_feed

Release feed ingestion owns product/code release sources, especially GitHub release and changelog-style feeds.

## Current Root Entrypoints

- Currently routed through `fetch-rss.py` and downstream source names such as `openai-codex-releases` and `claude-code-releases`.

## Inputs

- Release-oriented RSS/Atom/GitHub feed rows from `~/park-io/_source management/sources.md`.

## Outputs

- Standard ingestion artifacts with `channel=release_feed`.
- Items use `content_kind=release`.

## Boundary

Release feeds preserve version, package, CLI behavior, changelog bullets, breaking changes, and implementation details. They should not be collapsed by ordinary article/news heuristics.
