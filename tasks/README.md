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
python3 scripts/task_next.py
python3 scripts/task_agent_loop.py --agent codex
python3 scripts/task_graph_github_export.py --task AG-002 --json
python3 scripts/task_graph_threads.py
python3 scripts/task_claim.py TG-001 --agent codex
python3 scripts/task_complete.py TG-001 --agent codex --commit <sha>
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

GitHub Issues sync and n8n visual workflow integration are intentionally future layers. The local graph stays canonical until those layers are proven.
