# n8n Adapter

The executable workflow graph remains canonical:

```text
workflow/diagram/daily-newsletter.graph.json
```

This folder contains generated or adapter-specific n8n artifacts. Do not edit generated n8n JSON as the source of truth unless the import layer is also updated and reviewed.

## Export

```bash
python3 scripts/n8n_export.py --dry-run
python3 scripts/n8n_export.py --output workflow/n8n/daily-newsletter.workflow.json
```

## Import / Diff

```bash
python3 scripts/n8n_import_diff.py
python3 scripts/n8n_import_diff.py --workflow workflow/n8n/daily-newsletter.workflow.json --json
```

The import command reconstructs the n8n-visible graph projection and compares
it with the canonical graph. It does not overwrite `workflow/diagram/*.graph.json`.

## Contract

- `workflow/diagram/*.graph.json` defines nodes, edges, commands, inputs, and outputs.
- `scripts/n8n_export.py` maps graph nodes into n8n nodes.
- `scripts/n8n_import_diff.py` imports n8n node metadata and visual connections for drift checks.
- Command-like graph nodes become n8n Execute Command nodes.
- Trigger graph nodes become n8n Manual Trigger nodes by default, with graph metadata preserved.
- Graph edges become n8n `connections`.

## Safety

- Exporting does not run production commands.
- Import/diff does not run production commands.
- Importing into n8n should be tested manually before enabling schedules.
- Production still runs through root scripts until a separate cutover milestone.
