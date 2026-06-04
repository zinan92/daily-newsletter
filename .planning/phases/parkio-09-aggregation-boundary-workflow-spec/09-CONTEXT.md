# Context: Phase 9 Aggregation Boundary And Workflow Spec

Phases 6-8 separated source ingestion and media enrichment. The remaining production path still has root-level aggregation code: scoring, digest building, quality gates, archiving, and local finalization.

Phase 9 moves the implementation into `aggregation/digest/` while preserving root commands used by `push-digest.sh`, tests, and operator habits.

High-risk compatibility points:

- Tests and local tools import `summarize` from the root module name.
- `build-digest.py` shells out to `summarize.py` and `html-to-long-image.py`.
- `check-quality.py` shells out to `quality-check.py`; `quality-check.py` shells out to `ai-quality-check.py`.
- `tests/test_finalize_local.py` loads `finalize-local.py` by path.

Root wrappers must preserve those names.

