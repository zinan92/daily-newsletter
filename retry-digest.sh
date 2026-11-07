#!/usr/bin/env bash
# retry-digest.sh — make sure today's AI daily exists and reached Feishu.
#
# Runs at 09:30 and 11:00 (launchd com.wendy.parkio-retry). Replaces the
# park-morning 09:40 self-heal, which was archived on 2026-09-27 when the AI
# daily became a standalone product again. Safe to run any number of times:
#   - daily file present  -> only (re)try the Feishu send; send-feishu-digest.py
#                            skips when today already has a successful receipt
#   - pipeline running    -> leave it alone; push-feishu-digest.sh sends when done
#   - batch opened, died  -> resume that batch (checkpoints make this cheap)
#   - nothing today       -> run the full pipeline
#
# The website only publishes on its own at 09:30 (launchd com.wendy.park-newsletter),
# so a daily that lands later would never reach the site or the feed. Whenever
# today's daily exists this also runs the site's publish script, which pushes
# only when the content changed and waits its turn if the 09:30 run is active.
# PARKIO_PUBLISH_SCRIPT overrides the path; a clone without that script skips it.

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
LOG="$SCRIPT_DIR/logs/push-digest.log"
mkdir -p logs
ts() { date '+%F %T'; }

RUN_DATE="$(date '+%F')"
SHORT="$(date '+%y-%m-%d')"
BID="$(date '+%Y%m%d')"
DAILY="$(python3 -c 'import lib; print(lib.SENT_DIR)' 2>/dev/null)/$SHORT.md"
BATCH_DIR="$(python3 -c 'import lib; print(lib.PROCESSED_DIR)' 2>/dev/null)/$SHORT"
PUBLISH_SCRIPT="${PARKIO_PUBLISH_SCRIPT:-$HOME/work/park-ai-intel/scripts/refresh-newsletter.sh}"

echo "[$(ts)] retry-digest check date=$RUN_DATE" >> "$LOG"
if pgrep -f "push-digest.sh|build-digest.py" >/dev/null; then
  echo "[$(ts)] retry-digest: pipeline still running; leave it" >> "$LOG"
  exit 0
fi
if [ ! -f "$DAILY" ]; then
  if [ -d "$BATCH_DIR" ]; then
    echo "[$(ts)] retry-digest: $SHORT.md missing, resuming batch $BID" >> "$LOG"
    PARKIO_RESUME_BATCH="$BID" /bin/bash "$SCRIPT_DIR/push-digest.sh"
  else
    echo "[$(ts)] retry-digest: $SHORT.md missing and no batch; full run" >> "$LOG"
    /bin/bash "$SCRIPT_DIR/push-digest.sh"
  fi
fi
if [ -f "$DAILY" ]; then
  python3 "$SCRIPT_DIR/send-feishu-digest.py" --date "$RUN_DATE" >> "$LOG" 2>&1
  echo "[$(ts)] retry-digest: feishu exit=$?" >> "$LOG"
  if [ -f "$PUBLISH_SCRIPT" ]; then
    /bin/bash "$PUBLISH_SCRIPT" >> "$LOG" 2>&1
    echo "[$(ts)] retry-digest: publish exit=$?" >> "$LOG"
  else
    echo "[$(ts)] retry-digest: publish skipped, no $PUBLISH_SCRIPT" >> "$LOG"
  fi
else
  echo "[$(ts)] retry-digest: still no daily after retry" >> "$LOG"
  exit 1
fi
