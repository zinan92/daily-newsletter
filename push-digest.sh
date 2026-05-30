#!/usr/bin/env bash
# push-digest.sh — Run the daily digest stages.
# Intended for a fixed daily launchd run after the 20:00 fetch window.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG="$SCRIPT_DIR/logs/push-digest.log"
FETCH_LOCK="$SCRIPT_DIR/logs/fetch.lock"
mkdir -p logs

ts() { date '+%F %T'; }

{
  echo ""
  echo "=========================================="
  echo "[$(ts)] push-digest START"
  echo "=========================================="
} >> "$LOG"

for i in {1..10}; do
  if [ ! -e "$FETCH_LOCK" ]; then
    break
  fi
  FETCH_PID="$(cat "$FETCH_LOCK" 2>/dev/null || true)"
  if [ -z "$FETCH_PID" ] || ! kill -0 "$FETCH_PID" 2>/dev/null; then
    rm -f "$FETCH_LOCK"
    break
  fi
  echo "[$(ts)] fetch still running pid=$FETCH_PID; wait $i/10" >> "$LOG"
  sleep 60
done

if [ -e "$FETCH_LOCK" ]; then
  echo "[$(ts)] fetch still running after 10 minutes; skip this digest" >> "$LOG"
  exit 0
fi

echo "[$(ts)] >>> open-batch.py" >> "$LOG"
BATCH_ID="$(python3 "$SCRIPT_DIR/open-batch.py" 2>> "$LOG" | tail -n 1)"
if [ -z "$BATCH_ID" ]; then
  echo "[$(ts)] no batch opened; nothing to process" >> "$LOG"
  echo "[$(ts)] push-digest DONE" >> "$LOG"
  exit 0
fi
export PARKIO_BATCH_ID="$BATCH_ID"
echo "[$(ts)] batch=$PARKIO_BATCH_ID" >> "$LOG"

for stage in score.py build-digest.py check-quality.py archive-items.py send-artifacts.py; do
  echo "[$(ts)] >>> $stage" >> "$LOG"
  python3 "$SCRIPT_DIR/$stage" >> "$LOG" 2>&1
  EXIT=$?
  if [ "$EXIT" -ne 0 ]; then
    echo "[$(ts)] !!! $stage exit=$EXIT" >> "$LOG"
    echo "[$(ts)] push-digest STOPPED at $stage" >> "$LOG"
    exit "$EXIT"
  fi
done

echo "[$(ts)] >>> generate-status.py" >> "$LOG"
python3 "$SCRIPT_DIR/generate-status.py" >> "$LOG" 2>&1
EXIT=$?
if [ "$EXIT" -ne 0 ]; then
  echo "[$(ts)] !!! generate-status.py exit=$EXIT" >> "$LOG"
fi

echo "[$(ts)] push-digest DONE" >> "$LOG"
