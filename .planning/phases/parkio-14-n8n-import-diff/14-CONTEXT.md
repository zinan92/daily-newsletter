# Context: Phase 14 n8n Import Diff

## Starting Point

Phase 13 exports the canonical executable workflow graph into
`workflow/n8n/daily-newsletter.workflow.json`.

The export is useful for visual review, but without import/diff there is no
closed loop. A visual edit in n8n could drift away from the canonical graph
without being detected.

## Boundary

- Canonical source remains `workflow/diagram/daily-newsletter.graph.json`.
- n8n workflow JSON remains an adapter artifact.
- Import/diff must not run production commands.
- Import/diff must not overwrite the canonical graph.

## Target

Add a deterministic command that imports the n8n-visible projection and reports
whether it differs from the canonical workflow graph.
