#!/usr/bin/env python3
"""Compatibility wrapper for aggregation/digest/ai_quality.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aggregation.digest.ai_quality import *  # noqa: F401,F403

if __name__ == "__main__":
    raise SystemExit(main())

