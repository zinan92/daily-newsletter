#!/usr/bin/env python3
"""Stage 3: Score Items."""
import subprocess
import sys

from lib import ROOT


if __name__ == "__main__":
    raise SystemExit(subprocess.run([sys.executable, str(ROOT / "score-items.py")]).returncode)
