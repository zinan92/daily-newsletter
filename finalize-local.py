#!/usr/bin/env python3
"""Finalize the local daily digest independent of Telegram delivery.

The owner reads the digest locally (no Telegram), so we save BOTH the Markdown
and the HTML to the sent/ folder. Both derive from the same Markdown source.
"""
import shutil
import sys

from lib import SENT_DIR, batch_artifact_paths, batch_label


def _finalize(src, dst) -> None:
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    shutil.copy2(src, tmp)
    tmp.replace(dst)


def main() -> int:
    label = batch_label()
    panel, html, png = batch_artifact_paths()
    if not panel.exists():
        print(f"[finalize-local] missing processed markdown: {panel}", file=sys.stderr)
        return 1

    SENT_DIR.mkdir(parents=True, exist_ok=True)
    md_dst = SENT_DIR / f"{label}.md"
    _finalize(panel, md_dst)
    print(f"[finalize-local] wrote {md_dst}")
    if html.exists():
        html_dst = SENT_DIR / f"{label}.html"
        _finalize(html, html_dst)
        print(f"[finalize-local] wrote {html_dst}")
    else:
        print(f"[finalize-local] WARN missing processed html: {html}", file=sys.stderr)
    if png.exists():
        png_dst = SENT_DIR / f"{label}.png"
        _finalize(png, png_dst)
        print(f"[finalize-local] wrote {png_dst}")
    else:
        print(f"[finalize-local] WARN missing processed png: {png}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
