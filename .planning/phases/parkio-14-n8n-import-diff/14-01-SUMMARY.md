# Summary: 14-01 n8n Import Diff

**Completed:** 2026-06-04
**Plan:** `.planning/phases/parkio-14-n8n-import-diff/14-01-PLAN.md`
**Status:** Complete

## What Changed

- Added `scripts/n8n_import_diff.py`.
- Updated `scripts/n8n_export.py` to preserve graph edge metadata in generated n8n JSON.
- Regenerated `workflow/n8n/daily-newsletter.workflow.json`.
- Added `tests/test_n8n_import_diff.py`.
- Updated n8n adapter documentation and planning state.

## Verification

```bash
python3 -m py_compile scripts/n8n_export.py scripts/n8n_import_diff.py tests/test_n8n_export.py tests/test_n8n_import_diff.py
python3 scripts/n8n_export.py --output workflow/n8n/daily-newsletter.workflow.json
python3 scripts/n8n_import_diff.py
python3 tests/test_n8n_import_diff.py
python3 tests/test_n8n_export.py
```

Results:
- Generated n8n workflow matches the canonical graph projection.
- Round-trip import validates as a workflow graph.
- Removing a visual connection reports the missing edge.
- Adding a visual connection reports the extra edge.

## Acceptance

- N8N-03 satisfied.

## Next

Continue with agent claim protocol, GitHub Issues sync, diagram command runner,
or task graph operating docs.

---
*Summary created: 2026-06-04*
