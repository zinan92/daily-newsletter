#!/usr/bin/env python3
"""Compatibility wrapper for aggregation/digest/summarize.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aggregation.digest import summarize as _impl

globals().update(
    {
        name: value
        for name, value in vars(_impl).items()
        if not (name.startswith("__") and name.endswith("__"))
    }
)

if __name__ == "__main__":
    raise SystemExit(_impl.main())

sys.modules[__name__] = _impl
