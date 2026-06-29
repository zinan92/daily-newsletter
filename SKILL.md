---
name: daily-newsletter
description: Operate, verify, or improve a local-first Daily Inbox pipeline that turns source feeds, X, media, manual links, and saved items into Chinese Markdown/HTML/PNG artifacts plus Feishu delivery receipts. Use when a user asks to run, debug, review, package, or extend the daily-newsletter / Daily Inbox workflow.
---

# Daily Newsletter

Daily Newsletter is a local-first Daily Inbox operating pipeline. It fetches source material, normalizes it to one-item Markdown, lets AI perform event understanding/merge/selection/writing, finalizes Markdown/HTML/PNG artifacts, records source health, and optionally sends the complete digest to Feishu.

## When To Use

Use this skill when the user asks to:

- run or verify the daily AI newsletter pipeline;
- debug missing, late, or degraded source items;
- inspect Feishu delivery or local sent artifacts;
- change reader-facing Daily Inbox output;
- review pipeline health, workflow graph, task graph, or regression invariants;
- package this repository as a public agent skill.

Do not use this skill for unrelated newsletter copywriting, generic RSS advice, or live content scraping outside this repository.

## Inputs

- Repo root: the `daily-newsletter` checkout.
- Source registry: `$PARKIO_HOME/_source management/sources.md`.
- Runtime data: `$PARKIO_HOME/_inbox/{raw,unprocessed,processed}`.
- Sent artifacts: `$PARKIO_HOME/001_daily newsletter/ai/`.
- Secrets: env vars or `$PARKIO_HOME/_secrets/*`.
- Optional auth/runtime tools: X auth env, YouTube cookies, WeWe RSS, content-toolkit, Chrome, MLX Whisper.

Default `$PARKIO_HOME` is `~/park-io`.

## Workflow

1. Read `README.md`, `AGENTS.md`, and `GOTCHAS.md` before changing behavior.
2. Check git state and preserve uncommitted user changes.
3. For read-only diagnosis, start with generated artifacts and logs before rerunning production commands.
4. For public verification, run:

```bash
python3 -m pytest -q
python3 scripts/task_graph_validate.py
python3 scripts/workflow_graph_validate.py
python3 scripts/workflow_graph_dry_run.py
python3 scripts/n8n_import_diff.py
```

5. For a manual production run, use the staged path:

```bash
./fetch-all.sh
python3 stages/to_md/run.py
BATCH=$(python3 stages/coarse_filter/run.py | tail -1)
PARKIO_BATCH_ID=$BATCH python3 build-digest.py
PARKIO_BATCH_ID=$BATCH python3 stages/archive/run.py
PARKIO_BATCH_ID=$BATCH python3 finalize-local.py
python3 build-product-radar.py --date "$(date +%F)"
python3 build-daily-bundle.py --date "$(date +%F)"
python3 reader_quality.py --date "$(date +%F)"
python3 send-feishu-digest.py --date "$(date +%F)"
```

6. After any reader-facing or routing change, rerun tests and at least the workflow graph validator.

## Outputs

- `processed/<YY-MM-DD>/run-report.json`
- `processed/receipts/feishu/*.json`
- `sent/YY-MM-DD.{md,html,png}`
- `sent/deep-YY-MM-DD.{md,html,png}` when deep candidates exist
- `sent/product-radar-YY-MM-DD.{md,html,png}`
- `sent/daily-YY-MM-DD.{md,html,png}`
- `status.html` and source-health JSON for operator visibility

## Safety

- Never print or commit API keys, cookies, Feishu webhook secrets, Telegram tokens, or X auth values.
- Do not send Feishu or Telegram messages unless the user explicitly asks for delivery or the current task is a delivery verification.
- Do not hide source failures as "no updates"; use `channel-health.py`, `run-report.json`, and status artifacts.
- Do not create fake successful newsletters when AI JSON or final Markdown structure fails.
- Do not move content judgment from AI prompts into deterministic script thresholds, except for coarse garbage filtering.
- Do not rewrite HTML or PNG separately from Markdown; Markdown is the single reader-facing source.

## Regression Invariants

`GOTCHAS.md` is the source of truth. The most important invariants are:

- AI owns merge, score, classification, selection, and final writing.
- Structural AI output failures stop the run and write error artifacts.
- Deep reads must be traceable subsets of the brief universe.
- Product Radar is a separate product lane and is linked by the daily umbrella.
- Source Health stays in status/run-report/alerts, not inside the consumer digest body.
