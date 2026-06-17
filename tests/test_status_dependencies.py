"""Regression tests for owner status dependency checks.

Run: python3 tests/test_status_dependencies.py
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_generate_status():
    spec = importlib.util.spec_from_file_location("generate_status", ROOT / "generate-status.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_douyin_cookie_check_uses_canonical_secret_path():
    module = load_generate_status()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cookie = root / "_secrets" / "douyin-cookies.json"
        cookie.parent.mkdir()
        cookie.write_text("{}", encoding="utf-8")

        original_secret_path = module.parkio_secret_path
        original_check_command = module.check_command
        original_summarize = module.summarize
        original_media_failures = module.media_failures_for_date
        try:
            module.parkio_secret_path = lambda name: cookie if name == "douyin-cookies.json" else root / name
            module.check_command = lambda *args, **kwargs: (True, "ok")
            module.media_failures_for_date = lambda date: []
            module.summarize = type("FakeSummarize", (), {"_channel_health_states": staticmethod(lambda: {})})()

            rows = module.dependency_checks()
        finally:
            module.parkio_secret_path = original_secret_path
            module.check_command = original_check_command
            module.summarize = original_summarize
            module.media_failures_for_date = original_media_failures

    douyin = [row for row in rows if row["name"] == "抖音 Cookie"]
    assert douyin == [{"name": "抖音 Cookie", "status": "ok", "detail": "cookie 存在，最近抓取正常"}]


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)
