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

## Workflow diagram — Source Of Truth (v12 contract)

The human-facing workflow source is `/Users/wendy/park-io/_inbox/inbox-workflow.yaml`.
It is rendered by `/Users/wendy/work/input-to-park/workflow/diagram/render-workflow-diagram.py`.
The v12 model is **four independent paths**, each running entry → … → its own
Section sink:

1. Official / code → Section 1 (AI 官方与代码源)
2. X application layer → Section 2 (Twitter / X 应用层)
3. Media (Podcast / YouTube / 抖音) → Section 3
4. Saved + manual links + WeChat → Section 4 (我的收藏 / Manual Links)

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
- Before rendering HTML/PNG, run the validator:

```bash
python3 /Users/wendy/work/input-to-park/workflow/diagram/validate-workflow.py /Users/wendy/park-io/_inbox/inbox-workflow.yaml
```

- `render-workflow-diagram.py` must call the validator before writing
  HTML/PNG/JSON. If validation fails, do not render and do not claim the
  workflow is updated.
