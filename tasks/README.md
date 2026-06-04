# Executable Task Graph

This folder is the repo-local source of truth for agent-claimable atomic work.

The graph answers four questions:

- What atomic units exist?
- Which dependencies block each unit?
- Which units are ready for an idle agent to claim?
- Which execution threads can run in parallel?

## Commands

```bash
python3 scripts/task_graph_validate.py
python3 scripts/task_graph_ready.py
python3 scripts/task_graph_threads.py
python3 scripts/task_claim.py TG-001 --agent codex
python3 scripts/task_complete.py TG-001 --agent codex --commit <sha>
```

## Agent Claim Protocol

Agents should follow `tasks/agent-claim-protocol.md` before claiming work.

The short version:

1. Validate the graph.
2. List ready tasks.
3. Claim exactly one ready task.
4. Complete its success criteria, tests, lint, and review requirements.
5. Record completion with a real commit sha.

## Status Contract

- `todo`: not claimed yet.
- `claimed`: assigned to an agent.
- `in_progress`: actively being worked.
- `blocked`: cannot proceed until an external condition changes.
- `done`: completed and verified.

## Claim Rule

A task is ready when all dependencies are `done`, and its own status is `todo`.

GitHub Issues sync and n8n visual workflow integration are intentionally future layers. The local graph stays canonical until those layers are proven.
