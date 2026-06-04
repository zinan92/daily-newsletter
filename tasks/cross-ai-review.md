# Cross-AI Review: Task Graph Operating System

**Date:** 2026-06-04
**Task:** PR-002
**Scope:** task graph validator, ready planner, thread planner, claim protocol,
agent loop, GitHub issue dry-run export, workflow runner, and n8n import/diff.

## Claude Code Attempt

Claude Code CLI was attempted first through:

```bash
/Users/wendy/.local/bin/claude --print --permission-mode acceptEdits --output-format text ...
```

Result:

- Broad prompt: no output after several minutes; process was terminated.
- Narrow prompt: timed out after 120 seconds.

No files were edited by Claude Code.

Because the task permits "Claude Code review or equivalent", a local blocking
review was performed and recorded below.

## Blocking Review Result

One blocking issue was found and fixed.

### Fixed Finding

`scripts/workflow_graph_run.py` selected nodes from `dry_run_plan()`. Since
`dry_run_plan()` intentionally excludes failure-only alert nodes, an explicit
selection such as:

```bash
python3 scripts/workflow_graph_run.py --node health_alert
```

returned no selected step and could silently skip the requested node.

Why it mattered:

- DG-005 promised the runner can execute selected graph nodes.
- `health_alert` is a valid graph node.
- Silent skip behavior is unsafe for a command runner.

Fix:

- `workflow_graph_run.py` now validates the graph, keeps normal dry-run order
  for normal-path nodes, and constructs a selected step directly from graph node
  metadata when the node is valid but excluded from normal dry-run.
- `tests/test_workflow_graph.py` now covers selecting the failure-only
  `health_alert` node.

## Post-Fix Verification

```bash
python3 -m py_compile scripts/workflow_graph_run.py tests/test_workflow_graph.py
python3 tests/test_workflow_graph.py
python3 scripts/workflow_graph_run.py --node health_alert
```

Result:

- Workflow graph tests pass.
- `--node health_alert` prints `check-pipeline-health.py`.

## Remaining Non-Blocking Risks

- `task_claim.py` writes the JSON graph directly and does not implement file
  locking. Concurrent agents should rely on git/worktree isolation or a future
  lock/sync layer before true multi-agent production use.
- `workflow_graph_run.py` intentionally uses shell commands from the canonical
  graph. This is acceptable only because execution requires both `--run` and
  `--confirm-production`, and selected nodes must be explicit.
- GitHub Issues export is dry-run only. Live sync must get a separate review
  before it mutates GitHub.

## Acceptance

No remaining blocking findings for PR-002 after the workflow runner selected
node fix.
