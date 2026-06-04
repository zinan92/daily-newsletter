# Context: Phase 15 Task Graph Operating System

## Starting Point

Phase 11 created the task graph foundation. Phases 12-14 added executable
workflow and n8n adapters. Remaining task graph items were agent claim protocol,
agent next task, auto-claim loop, GitHub issue dry-run sync, workflow graph
runner, operating docs, review checklist, cross-review, and final verification.

## Target

Finish all 24 task graph atomic units and prove the system is ready as a
repo-local operating layer for future agent-claimable work.

## Boundary

- Local task graph remains canonical.
- GitHub Issues export remains dry-run only.
- n8n remains an adapter artifact with import/diff drift detection.
- Workflow command execution remains dry-run by default and requires explicit
  selected-node confirmation for real execution.
