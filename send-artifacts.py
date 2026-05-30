#!/usr/bin/env python3
"""Stage 6: Send Artifacts."""
import os
import subprocess
import sys

from lib import ROOT


if __name__ == "__main__":
    env = os.environ.copy()
    env["PARKIO_SKIP_QUALITY"] = "1"
    raise SystemExit(subprocess.run([sys.executable, str(ROOT / "push-telegram.py")], env=env).returncode)
