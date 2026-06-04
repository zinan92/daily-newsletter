#!/usr/bin/env python3
"""Compatibility wrapper for aggregation/digest/finalize_local.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aggregation.digest import finalize_local as _impl

SENT_DIR = _impl.SENT_DIR
batch_artifact_paths = _impl.batch_artifact_paths
batch_label = _impl.batch_label
_finalize = _impl._finalize


def main() -> int:
    _impl.SENT_DIR = SENT_DIR
    _impl.batch_artifact_paths = batch_artifact_paths
    _impl.batch_label = batch_label
    return _impl.main()

if __name__ == "__main__":
    raise SystemExit(main())
