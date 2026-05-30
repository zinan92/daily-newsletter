# input-to-park Agent Rules

## Workflow Source Of Truth

When editing any workflow YAML, workflow diagram, or renderer in this project:

- Treat the workflow as a closed system.
- The only nodes allowed to have no incoming edge are explicit `role: entry` nodes.
- Final newsletter sections are not independent entry points.
- Section 1/2/3/4 are `artifact_component` entries under a final artifact assembly node, not top-level workflow nodes.
- Final output artifacts must be generated from upstream process, decision, or artifact nodes.
- Workflow YAML must distinguish these roles:
  - `entry`
  - `process`
  - `decision`
  - `artifact`
  - `artifact_component` only inside an artifact node's `components`
- Before rendering HTML/PNG, run the workflow validator:

```bash
python3 /Users/wendy/park-io/inbox/validate-workflow.py /Users/wendy/park-io/inbox/inbox-workflow.yaml
```

- `render-workflow-diagram.py` must call the validator before writing HTML/PNG/JSON.
- If validation fails, do not render and do not claim the workflow is updated.
