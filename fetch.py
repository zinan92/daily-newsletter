#!/usr/bin/env python3
"""Stage 1: Fetch Raw.

Only ingests raw data into inbox/unprocessed/<YY-MM-DD-profile>.md. It does not score,
summarize, push, or move batch state.
"""
import sys
import subprocess

from lib import ROOT, log

STAGES = [
    "fetch-manual-links.py",
    "fetch-rss.py",
    "fetch-twitter.py",
    "fetch-twitter-saved.py",
    "fetch-scrape.py",
    "fetch-wechat.py",
    "fetch-wechat-rss.py",
    "fetch-wechat-exporter.py",
    "fetch-douyin.py",
    "fetch-media-transcripts.py",
]


def main() -> int:
    log("fetch", f"START — {len(STAGES)} fetcher(s)")
    for stage in STAGES:
        log("fetch", f">>> {stage}")
        result = subprocess.run([sys.executable, str(ROOT / stage)])
        if result.returncode != 0:
            log("fetch", f"!!! {stage} exit={result.returncode}")
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
