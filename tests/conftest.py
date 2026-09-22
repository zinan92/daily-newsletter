"""Shared test setup.

The LLM circuit breaker is process-level state (added 2026-09-22 so a provider
that hangs is skipped for the rest of a run instead of costing the full timeout
on every call). Tests that deliberately fail a provider would otherwise leave it
tripped for every test that runs after them, so reset it around each test.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lib


@pytest.fixture(autouse=True)
def _reset_llm_breaker():
    lib.reset_llm_breaker()
    yield
    lib.reset_llm_breaker()
