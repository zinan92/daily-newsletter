#!/usr/bin/env python3
"""Stage 5: Check Quality."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def main() -> int:
    quality = Path(__file__).resolve().parent / "quality.py"
    return subprocess.run([sys.executable, str(quality)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
