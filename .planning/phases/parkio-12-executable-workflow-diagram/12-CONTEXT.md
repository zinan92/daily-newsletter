# Context: Phase 12 Executable Workflow Diagram Foundation

Phase 11 created the task graph that agents can use to claim implementation work. Phase 12 creates the runtime workflow graph: the diagram that defines Daily Inbox execution order.

This phase proves diagram-as-source-of-truth at the smallest useful level:

- graph nodes carry command adapters and artifact contracts;
- graph edges determine execution order;
- dry-run reads the graph and prints order without running production commands;
- tests prove changing an edge changes execution order.

This phase does not replace `fetch.py` or `push-digest.sh`.

