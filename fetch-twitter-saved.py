#!/usr/bin/env python3
"""Compatibility wrapper for ingestion/x/saved.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.x.saved import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
