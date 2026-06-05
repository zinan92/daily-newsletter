#!/usr/bin/env python3
"""Stage 3: Score Items."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def main() -> int:
    score_items = Path(__file__).resolve().parent / "score_items.py"
    return subprocess.run([sys.executable, str(score_items)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
