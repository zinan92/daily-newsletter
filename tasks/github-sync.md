# GitHub Issues Sync Contract

This contract defines how repo-local task graph nodes can be mirrored to GitHub
Issues.

The local task graph remains canonical:

```text
tasks/daily-inbox-task-graph.json
```

GitHub Issues are an external queue and collaboration surface. They must never
be the only place where task state exists.

## Issue Identity

Each task maps to at most one issue.

Issue title format:

```text
[<TASK_ID>] <task title>
```

Example:

```text
[AG-002] Implement agent next-task command
```

The task id is the stable join key. If a title changes, the sync layer should
still match by task id.

## Labels

Every exported issue should include:

- `daily-inbox`
- `task-graph`
- `task:<TYPE>`
- `status:<STATUS>`

Optional labels:

- `ready` when all dependencies are `done` and status is `todo`.
- `blocked` when status is `blocked`.
- `claimed` when status is `claimed` or `in_progress`.

## Issue Body

The body must contain these sections in this order:

```markdown
## Task

- ID:
- Type:
- Status:
- Dependencies:
- Files:

## Success Criteria

...

## Test Commands

...

## Linter Commands

...

## Review Requirements

...

## Claim Protocol

...

## Source Of Truth

...
```

The source-of-truth section must say that edits should be reflected back into
`tasks/daily-inbox-task-graph.json`.

## Status Transitions

GitHub labels mirror local graph status:

| Local status | GitHub mirror |
|--------------|---------------|
| `todo` | open issue with `status:todo` |
| `claimed` | open issue with `status:claimed` |
| `in_progress` | open issue with `status:in_progress` |
| `blocked` | open issue with `status:blocked` |
| `done` | closed issue with `status:done` |

The local graph transition must happen first. GitHub sync follows it.

## Claim Handling

Agents should claim locally with:

```bash
python3 scripts/task_claim.py <TASK_ID> --agent <agent-id>
```

Then the GitHub issue can be updated with:

- `status:claimed`
- assignee or comment naming the agent
- claim timestamp copied from the local graph

If GitHub and the local graph disagree, the local graph wins.

## Completion Handling

Agents should complete locally with:

```bash
python3 scripts/task_complete.py <TASK_ID> --agent <agent-id> --commit <sha>
```

Then the GitHub issue can be updated with:

- `status:done`
- close state
- completion commit
- verification summary

Do not close an issue unless the local graph has `status: done`.

## Dry-Run Export Requirement

Before any live GitHub mutation exists, the exporter must render deterministic
issue payloads:

- title
- labels
- body
- close/open intent
- task id mapping

The dry run must not call GitHub.
