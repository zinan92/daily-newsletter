# Context: Phase 8 Media And WeChat Folderization

Phase 7 moved the lower-risk text/feed channels behind channel folders. Phase 8 handles the higher-risk ingestion paths:

- Douyin profile monitoring.
- WeChat RSS via WeWe.
- Manual WeChat links from `~/park-io/inbox/manual-links.md`.
- WeChat exporter bridge imports.
- Media transcript enrichment for YouTube, podcasts, and Douyin videos.

The root commands are still the public runtime surface. `fetch.py`, cron scripts, tests, and direct operator commands must keep using the same root filenames.

The important dependency is that manual links reuse the WeChat article parser. After folderization, that dependency should be module-to-module inside `ingestion/manual_links/`, while the root `fetch-wechat.py` wrapper remains import-compatible.

