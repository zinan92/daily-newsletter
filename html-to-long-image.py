#!/usr/bin/env python3
"""Compatibility wrapper for aggregation/digest/html_to_long_image.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aggregation.digest.html_to_long_image import *  # noqa: F401,F403

if __name__ == "__main__":
    raise SystemExit(main())

