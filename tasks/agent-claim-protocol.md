# Agent Claim Protocol

This protocol defines how idle agents claim and complete atomic tasks from the
repo-local task graph.

The local task graph is canonical:

```text
tasks/daily-inbox-task-graph.json
```

GitHub Issues, n8n diagrams, and chat threads can mirror the graph, but they do
not replace it until a later milestone explicitly proves that sync layer.

## Idle Agent Loop

An idle agent should use this loop:

1. Sync or inspect the current repo state.
2. Run `python3 scripts/task_graph_validate.py`.
3. Run `python3 scripts/task_graph_ready.py`.
4. Pick exactly one ready task.
5. Claim it with `python3 scripts/task_claim.py <TASK_ID> --agent <agent-id>`.
6. Re-run validation after the claim.
7. Execute only the claimed task's bounded scope.
8. Run that task's `linter_commands` and `test_commands`.
9. Perform the task's `review_requirements`.
10. Complete it with `python3 scripts/task_complete.py <TASK_ID> --agent <agent-id> --commit pending`.
11. Commit the implementation.
12. Replace `pending` with the real commit sha in the task history.
13. Commit the task ledger update.
14. Push when the branch is intended to be shared.

## Claim Eligibility

A task is claimable only when:

- Its status is `todo`.
- Every dependency is `done`.
- `task_graph_validate.py` passes.
- The agent can complete the listed files, success criteria, tests, and review
  requirements without asking the owner for additional product decisions.

## Deterministic Selection

When multiple tasks are ready, pick the task that advances the critical path:

1. Tasks that unlock dependent implementation work.
2. Tasks required by final verification.
3. Contract tasks before implementation tasks that depend on them.
4. Lower lexical task id as a tie-breaker.

An agent must not claim multiple tasks just to reserve them. Parallel work is
allowed only when separate agents claim separate ready tasks.

## Claim Conflict Handling

The graph write is the conflict boundary.

- If `task_claim.py` succeeds, the agent owns that task.
- If `task_claim.py` fails because the task is not ready or no longer `todo`,
  the agent must not edit files for that task.
- If another agent has already claimed the task, choose a different ready task.
- If a task is claimed but abandoned, do not overwrite the claim silently; mark
  it blocked or ask the owner only after confirming there is no active worker.

## Completion Proof

A completed task must leave enough evidence for the next agent to trust it:

- `status` is `done`.
- `completed_by`, `completed_at`, and `commit` are present.
- The task history contains a completion event with the same commit.
- The listed linter and test commands have been run.
- Review requirements are satisfied or documented with an explicit non-blocking
  rationale.
- Any generated artifacts are regenerated from their canonical source.

Use `--commit pending` only before the implementation commit exists. Replace it
with the real commit sha before considering the task ledger final.

## Review Proof

Review evidence can be one of:

- A deterministic test that covers the requirement.
- A local script output that proves the invariant.
- A cross-AI review transcript or summary for review tasks.
- A concise handover note that names remaining non-blocking risk.

Review proof must be specific to the task. Passing a broad test suite is not
enough if the task asks for a contract, conflict behavior, or sync semantics.

## Safety Rules

- Never run production commands from a claim loop unless the task explicitly
  requires runtime execution and the command is listed in the task.
- Never treat GitHub Issues or n8n JSON as canonical while this protocol says
  the local graph is canonical.
- Never mark a task complete before its own success criteria, tests, lint, and
  review requirements have been checked.
- Never silently skip a failing source, failing test, or failing validator.
