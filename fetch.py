#!/usr/bin/env python3
"""Compatibility wrapper for Stage 1 fetch."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stages.fetch.run import *  # noqa: F401,F403

if __name__ == "__main__":
    raise SystemExit(main())
