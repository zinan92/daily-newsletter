#!/usr/bin/env python3
"""Compatibility wrapper for Stage 4 ai_process."""
import sys

from stages.ai_process import run as _impl

globals().update(
    {
        name: value
        for name, value in vars(_impl).items()
        if not (name.startswith("__") and name.endswith("__"))
    }
)

sys.modules[__name__] = _impl
