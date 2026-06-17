#!/usr/bin/env python3
"""Compatibility wrapper for Stage 5 archive."""
import sys

from stages.archive import run as _impl

globals().update(
    {
        name: value
        for name, value in vars(_impl).items()
        if not (name.startswith("__") and name.endswith("__"))
    }
)

sys.modules[__name__] = _impl
