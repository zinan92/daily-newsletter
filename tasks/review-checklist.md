# Execution Thread Review Checklist

Use this checklist before marking any task or execution thread complete.

An execution thread is complete only when every task in the thread has evidence
for success, tests, lint, review, commit, and handover.

## 1. Scope Check

- The claimed task id matches the files changed.
- The implementation stays inside the task's declared files or a documented
  adjacent file needed to satisfy the task.
- No unrelated refactor or generated churn is mixed in.
- The local task graph remains canonical.

## 2. Success Criteria

For each success criterion in `tasks/daily-inbox-task-graph.json`:

- Name the file, command, or generated artifact proving it.
- Treat indirect evidence as insufficient.
- If a criterion cannot be proven, do not mark the task complete.

## 3. Test Requirements

- Run every command listed in `test_commands`.
- Add focused tests when the task changes behavior.
- For contract/docs tasks, run the graph validator and any command that consumes
  the documented contract.
- Record any skipped test with a concrete non-blocking reason.

## 4. Linter Requirements

- Run every command listed in `linter_commands`.
- At minimum, Python scripts added or changed must pass `py_compile`.
- Generated JSON must be regenerated from its canonical source and parseable.

## 5. Review Requirements

- Satisfy every listed `review_requirements` entry.
- For safety-sensitive code, verify default behavior is non-mutating.
- For sync layers, verify the local graph remains the source of truth.
- For command runners, verify production execution requires explicit opt-in.
- For cross-AI review tasks, preserve a concise review summary in repo docs.

## 6. Commit Requirements

- Commit implementation and evidence-bearing docs/tests.
- Complete the task with `--commit pending` only before the real commit exists.
- Replace `pending` with the actual commit sha in the task graph.
- Commit the task graph ledger update.
- Push if the branch is meant to be shared or used by another agent.

## 7. Handover Requirements

Handover must include:

- What changed.
- How to run or verify it.
- Any remaining risks.
- The next ready task list if work continues.

Do not treat chat memory as handover. Durable handover belongs in repo files.
