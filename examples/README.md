# Examples

These files are sanitized examples for public verification. They are not the
operator's private Park-IO vault and contain no keys, cookies, private account
data, or real delivery tokens.

- `daily-newsletter-demo.gif` shows the public verification path in motion.
- `daily-newsletter-demo-transcript.txt` records the sanitized command output
  used to render the GIF.
- `sample-daily-inbox.md` shows the reader-facing Markdown shape.
- `sample-run-report.json` shows the health/provenance facts shared by status,
  digest, and delivery review.
- `proof-run-2026-06-28.md` records the public verification commands used for
  this repository packaging pass.

Regenerate the GIF from real verification output:

```bash
python3 scripts/render_demo_gif.py
```

Render again from the committed transcript without rerunning tests:

```bash
python3 scripts/render_demo_gif.py --from-transcript
```

Full production runs still require local source configs, auth state, and LLM
credentials outside this repo.
