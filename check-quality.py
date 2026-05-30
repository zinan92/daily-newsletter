#!/usr/bin/env python3
"""Stage 5: Check Quality."""
import subprocess
import sys

from lib import ROOT


if __name__ == "__main__":
    raise SystemExit(subprocess.run([sys.executable, str(ROOT / "quality-check.py")]).returncode)
