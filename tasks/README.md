# Executable Task Graph Operating Model

This folder is the repo-local source of truth for agent-claimable atomic work.

The graph answers four questions:

- What atomic units exist?
- Which dependencies block each unit?
- Which units are ready for an idle agent to claim?
- Which execution threads can run in parallel?

## Commands

Operator view:

```bash
python3 scripts/task_graph_validate.py
python3 scripts/task_graph_ready.py
python3 scripts/task_next.py
python3 scripts/task_agent_loop.py --agent codex
python3 scripts/task_graph_github_export.py --task AG-002 --json
python3 scripts/task_graph_threads.py
```

Claim and completion:

```bash
python3 scripts/task_claim.py TG-001 --agent codex
python3 scripts/task_complete.py TG-001 --agent codex --commit <sha>
```

Workflow diagram adapters:

```bash
python3 scripts/workflow_graph_validate.py
python3 scripts/workflow_graph_dry_run.py
python3 scripts/workflow_graph_run.py
python3 scripts/n8n_export.py --dry-run
python3 scripts/n8n_import_diff.py
```

## Agent Claim Protocol

Agents should follow `tasks/agent-claim-protocol.md` before claiming work.
Completed execution threads should be checked against
`tasks/review-checklist.md`.

The short version:

1. Validate the graph.
2. List ready tasks.
3. Use `task_next.py` when one agent needs a deterministic recommendation.
4. Use `task_agent_loop.py --agent <name>` to preview an idle-agent claim loop.
5. Add `--claim` only when you want the loop to persist a claim.
6. Complete its success criteria, tests, lint, and review requirements.
7. Record completion with a real commit sha.

## Status Contract

- `todo`: not claimed yet.
- `claimed`: assigned to an agent.
- `in_progress`: actively being worked.
- `blocked`: cannot proceed until an external condition changes.
- `done`: completed and verified.

## Claim Rule

A task is ready when all dependencies are `done`, and its own status is `todo`.

## Owner Workflow

Use this loop when driving the project:

1. Run `task_graph_ready.py` to see all claimable tasks.
2. Run `task_next.py` if one agent needs a deterministic next task.
3. Run `task_agent_loop.py --agent <name>` to preview what an idle agent would
   claim.
4. Claim one task.
5. Work only inside that task's boundary.
6. Run its linter, tests, and review requirements.
7. Complete the task with a commit sha.
8. Re-run `task_graph_ready.py`.

## Mirror Layers

GitHub Issues and n8n are mirror layers:

- `task_graph_github_export.py` renders GitHub Issue payloads without calling
  GitHub.
- `n8n_export.py` renders visual workflow JSON.
- `n8n_import_diff.py` checks n8n visual drift against the canonical graph.

The local graph stays canonical until a later milestone explicitly changes that
contract.
