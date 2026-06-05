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

Legacy reader-facing Inbox workflow map:

```bash
python3 workflow/diagram/validate-workflow.py /Users/wendy/park-io/inbox/inbox-workflow.yaml
python3 workflow/diagram/render-workflow-diagram.py \
  --input /Users/wendy/park-io/inbox/inbox-workflow.yaml \
  --html /Users/wendy/park-io/inbox/inbox-workflow.html \
  --png /Users/wendy/park-io/inbox/inbox-workflow.png \
  --json /Users/wendy/park-io/inbox/inbox-workflow.json
```

The scripts live here because `park-io` is an Obsidian-facing vault. Do not put
Python utilities back under `/Users/wendy/park-io/inbox/`.

## Safety

- This phase does not replace `fetch.py` or `push-digest.sh`.
- Production commands remain in root wrappers.
- Future command execution must require an explicit run mode.
