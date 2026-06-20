from pathlib import Path
import os
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_push_digest_generates_product_radar_and_daily_bundle():
    text = (ROOT / "push-digest.sh").read_text(encoding="utf-8")
    assert "build-product-radar.py" in text
    assert "build-daily-bundle.py" in text
    assert "continue with degraded daily bundle" in text


def test_recoverable_source_auth_no_longer_blocks_by_default():
    text = (ROOT / "push-digest.sh").read_text(encoding="utf-8")
    assert "continue scheduled push with degraded source health" in text
    assert "PARKIO_PREFLIGHT_BLOCK" in text
    assert "skip scheduled push" in text


def _write_fake_python(bin_dir: Path) -> Path:
    path = bin_dir / "python3"
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
script="${1:-}"
case "$script" in
  */morning-preflight.py)
    if [ "${PREFLIGHT_MODE:-ok}" = "blocked" ]; then
      echo "blocked fixture"
      exit 2
    fi
    echo "ok fixture"
    exit 0
    ;;
  */stages/coarse_filter/run.py)
    echo "20260620"
    exit 0
    ;;
  */build-daily-bundle.py)
    printf '%s\\n' "$@" > "${RECORD_ARGS:?}"
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _run_push_digest_fixture(tmp_path: Path, *, preflight_mode: str = "ok") -> subprocess.CompletedProcess:
    script = tmp_path / "push-digest.sh"
    shutil.copy2(ROOT / "push-digest.sh", script)
    script.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_python(bin_dir)
    record_args = tmp_path / "bundle-args.txt"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "PARKIO_SKIP_SEND": "1",
            "PREFLIGHT_MODE": preflight_mode,
            "RECORD_ARGS": str(record_args),
        }
    )
    return subprocess.run(
        ["/bin/bash", str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_push_digest_happy_path_runs_with_empty_warning_array(tmp_path):
    result = _run_push_digest_fixture(tmp_path, preflight_mode="ok")

    assert result.returncode == 0, result.stderr
    args = (tmp_path / "bundle-args.txt").read_text(encoding="utf-8").splitlines()
    assert args == [str(tmp_path / "build-daily-bundle.py"), "--date", "2026-06-20"]


def test_push_digest_degraded_path_passes_warning_to_bundle(tmp_path):
    result = _run_push_digest_fixture(tmp_path, preflight_mode="blocked")

    assert result.returncode == 0, result.stderr
    args = (tmp_path / "bundle-args.txt").read_text(encoding="utf-8").splitlines()
    assert "--warning" in args
    assert "recoverable source auth/cookie problem; generated available-source digest anyway" in args
