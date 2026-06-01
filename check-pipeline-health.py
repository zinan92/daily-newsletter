#!/usr/bin/env python3
"""Daily pipeline health check (gotcha #21/#23).

Runs after the morning digest is expected to be sent (scheduled ~10:00, well
after the slow v4-pro run finishes ~09:10). Alerts the owner via Telegram when:
  1. today's digest was NOT sent (and push-digest is not still running), or
  2. a source FAILED to fetch today, or
  3. a source has not fetched successfully in 7 days (likely broken).

Silent success (fetched OK, no new items) is normal and does NOT alert.
"""
import re
import sys
from datetime import datetime

from lib import PARKIO, ROOT, send_telegram, today

PUSH_LOG = ROOT / "logs" / "push-digest.log"


def digest_sent_today() -> bool:
    sent = PARKIO / "inbox" / "sent" / f"{today()[2:]}.md"
    sent_full = PARKIO / "inbox" / "sent" / f"{today()}.md"
    return sent.exists() or sent_full.exists()


def push_still_running(max_age_min: int = 90) -> bool:
    """True only if a push-digest run started recently (< max_age_min) and has
    no DONE yet — i.e. the slow v4-pro run is genuinely still in progress. An
    old START with no DONE means it hung/crashed, which SHOULD alert."""
    if not PUSH_LOG.exists():
        return False
    lines = PUSH_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    last_start_idx = last_start_ts = None
    for i, line in enumerate(lines):
        if "push-digest START" in line:
            last_start_idx, last_start_ts = i, _line_ts(line)
    if last_start_idx is None:
        return False
    done_after = any("push-digest DONE" in l for l in lines[last_start_idx:])
    if done_after:
        return False
    if last_start_ts is None:
        return False
    age_min = (datetime.now() - last_start_ts).total_seconds() / 60
    return 0 <= age_min < max_age_min


def _line_ts(line: str):
    m = re.search(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", line)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def broken_sources() -> list[str]:
    """Sources that failed today or haven't succeeded in 7 days."""
    import summarize  # imported lazily; heavy module

    scores = summarize.load_scores()
    sources, _ = summarize.read_today_items(today(), scores)
    problems = []
    for row in summarize.source_health(sources, today()):
        name = row.get("name", "?")
        if row.get("status") == "failed":
            problems.append(f"{name}（今日抓取失败）")
        elif row.get("success_total_7d", 0) >= 3 and row.get("success_ok_7d", 0) == 0:
            problems.append(f"{name}（7 天未成功抓取，可能已坏）")
    return problems


def main() -> int:
    problems: list[str] = []

    if not digest_sent_today():
        if push_still_running():
            print("[health] digest not yet sent but push-digest is running — no alert")
        else:
            problems.append("今日简报未发送（push-digest 未完成或失败）")

    try:
        problems.extend(broken_sources())
    except Exception as exc:  # never let source-health crash the check
        print(f"[health] source check skipped: {type(exc).__name__}: {exc}", file=sys.stderr)

    if not problems:
        print(f"[health] OK {today()} — digest sent, no broken sources")
        return 0

    alert = "⚠️ Park-IO 管道告警 " + today() + "\n\n" + "\n".join(f"• {p}" for p in problems)
    sent = send_telegram(alert)
    print(f"[health] {len(problems)} problem(s); telegram alert {'sent' if sent else 'FAILED to send'}")
    for p in problems:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
