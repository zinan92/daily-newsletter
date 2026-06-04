#!/usr/bin/env python3
"""Finalize the local daily digest independent of Telegram delivery."""
import shutil
import sys

from lib import SENT_DIR, batch_artifact_paths, batch_label


def main() -> int:
    label = batch_label()
    panel, _html, _png = batch_artifact_paths()
    if not panel.exists():
        print(f"[finalize-local] missing processed markdown: {panel}", file=sys.stderr)
        return 1

    SENT_DIR.mkdir(parents=True, exist_ok=True)
    dst = SENT_DIR / f"{label}.md"
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    shutil.copy2(panel, tmp)
    tmp.replace(dst)
    print(f"[finalize-local] wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
