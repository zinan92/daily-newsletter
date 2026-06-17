#!/usr/bin/env python3
"""Stage 1: Fetch Raw.

Only fetches raw/source artifacts. Common source writers now emit
inbox/raw/<YYYY-MM-DD>/<profile>/*.json; a few source-specific legacy writers
may still emit compatibility artifacts until they are migrated. This stage does
not score, summarize, push, or move batch state.
"""
import sys
import os
import signal
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import ROOT, log

STAGES = [
    "fetch-manual-links.py",
    "fetch-rss.py",
    "fetch-twitter.py",
    "fetch-twitter-saved.py",
    "fetch-scrape.py",
    "fetch-wechat.py",
    "fetch-wechat-rss.py",
    "wewe-auth-monitor.py",
    "fetch-wechat-exporter.py",
    "fetch-douyin.py",
]
FETCHER_TIMEOUT_SECONDS = int(os.environ.get("PARKIO_FETCHER_TIMEOUT_SECONDS", "900"))


def run_fetcher(stage: str) -> int | None:
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / stage)],
        start_new_session=True,
    )
    try:
        return proc.wait(timeout=FETCHER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=5)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        return None


def main() -> int:
    log("fetch", f"START — {len(STAGES)} fetcher(s)")
    for stage in STAGES:
        log("fetch", f">>> {stage}")
        returncode = run_fetcher(stage)
        if returncode is None:
            log("fetch", f"!!! {stage} timeout after {FETCHER_TIMEOUT_SECONDS}s")
        elif returncode != 0:
            log("fetch", f"!!! {stage} exit={returncode}")
    log("fetch", ">>> source-health.py --record")
    result = subprocess.run([sys.executable, str(ROOT / "source-health.py"), "--record"])
    if result.returncode != 0:
        log("fetch", f"!!! source-health.py exit={result.returncode}")
    log("fetch", ">>> generate-status.py")
    result = subprocess.run([sys.executable, str(ROOT / "generate-status.py")])
    if result.returncode != 0:
        log("fetch", f"!!! generate-status.py exit={result.returncode}")
    log("fetch", "DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
