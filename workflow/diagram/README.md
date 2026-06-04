# Executable Workflow Diagram

This folder is the source of truth for the Daily Inbox runtime diagram.

The diagram is not a picture of the code. The diagram defines executable order:

- `nodes` define runtime units.
- `edges` define ordering.
- `command` is the shell adapter each command node can run later.
- `inputs` and `outputs` document the artifact contract.

The current runner is dry-run only. It proves graph semantics without touching production data.

## Commands

```bash
python3 scripts/workflow_graph_validate.py
python3 scripts/workflow_graph_dry_run.py
python3 scripts/workflow_graph_dry_run.py --json
```

## Safety

- This phase does not replace `fetch.py` or `push-digest.sh`.
- Production commands remain in root wrappers.
- Future command execution must require an explicit run mode.

