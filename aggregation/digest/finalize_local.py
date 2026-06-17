#!/usr/bin/env python3
"""Finalize the local daily digest independent of Telegram delivery.

The owner reads the digest locally (no Telegram), so we save the Markdown,
HTML, and PNG to sent/. The HTML is copied from the processed artifact to
preserve computed dashboard details that are not encoded in Markdown.
"""
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import SENT_DIR, batch_artifact_paths, batch_label, deep_artifact_paths
def _finalize(src, dst) -> None:
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    shutil.copy2(src, tmp)
    tmp.replace(dst)


def _rewrite_html_for_sent(html_text: str) -> str:
    """Adjust paths when moving HTML from inbox/processed/<date>/ to inbox/sent/."""
    return html_text.replace("../../../_contact/", "../../_contact/")


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
    html_dst = SENT_DIR / f"{label}.html"
    if html.exists():
        html_dst.write_text(_rewrite_html_for_sent(html.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"[finalize-local] wrote {html_dst}")
    else:
        print(f"[finalize-local] WARN missing processed html: {html}", file=sys.stderr)
    if png.exists():
        png_dst = SENT_DIR / f"{label}.png"
        _finalize(png, png_dst)
        print(f"[finalize-local] wrote {png_dst}")
    else:
        print(f"[finalize-local] WARN missing processed png: {png}", file=sys.stderr)
    deep_md, deep_html, deep_png = deep_artifact_paths()
    if deep_md.exists():
        deep_md_dst = SENT_DIR / f"deep-{label}.md"
        _finalize(deep_md, deep_md_dst)
        print(f"[finalize-local] wrote {deep_md_dst}")
        if deep_html.exists():
            deep_html_dst = SENT_DIR / f"deep-{label}.html"
            deep_html_dst.write_text(_rewrite_html_for_sent(deep_html.read_text(encoding="utf-8")), encoding="utf-8")
            print(f"[finalize-local] wrote {deep_html_dst}")
        else:
            print(f"[finalize-local] WARN missing processed deep html: {deep_html}", file=sys.stderr)
        if deep_png.exists():
            deep_png_dst = SENT_DIR / f"deep-{label}.png"
            _finalize(deep_png, deep_png_dst)
            print(f"[finalize-local] wrote {deep_png_dst}")
        else:
            print(f"[finalize-local] WARN missing processed deep png: {deep_png}", file=sys.stderr)
    else:
        for stale in (SENT_DIR / f"deep-{label}.md", SENT_DIR / f"deep-{label}.html", SENT_DIR / f"deep-{label}.png"):
            if stale.exists():
                stale.unlink()
        print("[finalize-local] no deep-read artifact for this batch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
