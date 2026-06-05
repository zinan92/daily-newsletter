#!/usr/bin/env python3
"""Stage 4: Build Digest."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import ROOT, batch_artifact_paths


def main() -> int:
    summarize = Path(__file__).resolve().parent / "summarize.py"
    result = subprocess.run([sys.executable, str(summarize)])
    if result.returncode != 0:
        return result.returncode
    _, html_path, png_path = batch_artifact_paths()
    if html_path.exists():
        screenshot = subprocess.run(
            [
                sys.executable,
                str(ROOT / "html-to-long-image.py"),
                str(html_path),
                str(png_path),
                "--width",
                "1200",
            ]
        )
        if screenshot.returncode != 0:
            print(
                f"[build-digest] warning: long image render failed; continuing with markdown/html: {png_path}",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
