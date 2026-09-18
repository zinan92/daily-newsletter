#!/usr/bin/env python3
"""Compatibility wrapper for ingestion/x/home.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.x.home import main

if __name__ == "__main__":
    raise SystemExit(main())
