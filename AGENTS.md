# input-to-park Agent Rules

## Pipeline invariants

`GOTCHAS.md` is the source of truth for behavioral invariants. Before editing
`summarize.py`, `digest_events.py`, `quality-check.py`, `fetch-twitter.py`,
`score-items.py`, `push-telegram.py`, or `fetch-wechat.py`, check the change
against `GOTCHAS.md` and run the tests:

```bash
for t in tests/test_*.py; do python3 "$t"; done
```

This repo is under git. Commit working states; never leave it un-versioned.

## Workflow diagram — source of truth

The repo-local runtime source of truth is
`workflow/diagram/daily-newsletter.graph.json`; validate it with
`python3 scripts/workflow_graph_validate.py`. The legacy reader-facing Inbox
workflow map can still be rendered with `workflow/diagram/render-workflow-diagram.py`
when an external vault provides its own YAML input, but repo-local graph files
are canonical for this repository.

The runtime model is **five physical stages**:

1. Fetch raw source data.
2. Normalize raw artifacts to one-item Markdown.
3. Coarse-filter obvious junk without editorial judgment.
4. Run AI understanding, merge, selection, and writing.
5. Archive, finalize local artifacts, record status, and send Feishu delivery.

Rules when editing the YAML, renderer, or validator:

- Treat the workflow as a closed system.
- The only nodes allowed to have no incoming edge are explicit `role: entry`
  nodes. Every other node must be reachable from an entry.
- **Each Section is its own top-level node** with `role: artifact` and
  `type: sink`, fed by its own path. Sections are NOT `artifact_component`s
  bundled under a single assembly node (that was the pre-v12 model — do not
  reintroduce it).
- Final output artifacts must be generated from upstream process/decision/
  artifact nodes.
- `role` (validation topology) and `type` (visual handler class) are distinct:
  - `role` ∈ `{entry, process, decision, artifact}` — enforced by the validator.
  - `type` ∈ `{entry, human, script, local_model, ai, sink, state, output}` —
    drives colour and tells the reader *who handles the node*.
- Routing is deterministic (source → profile → section). AI never decides
  routing; AI acts only *inside* nodes (scoring, summaries, QC). Mark a node's
  handler honestly via `type`, and for `type: ai` note the prompt location.
- Before rendering the legacy HTML/PNG workflow map, run the validator with the
  explicit input path:

```bash
python3 workflow/diagram/validate-workflow.py path/to/inbox-workflow.yaml
```

- `render-workflow-diagram.py` must call the validator before writing
  HTML/PNG/JSON. If validation fails, do not render and do not claim the
  workflow is updated.
