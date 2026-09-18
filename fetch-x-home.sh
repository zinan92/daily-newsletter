#!/usr/bin/env bash
# fetch-x-home.sh — Park's X home timeline, run by launchd at 08:00 and 20:00.
# Shares logs/fetch.lock with fetch-all.sh so the 08:30 digest waits for it.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
LOG="$SCRIPT_DIR/logs/fetch-x-home.log"
LOCK="$SCRIPT_DIR/logs/fetch.lock"
mkdir -p logs
ts() { date '+%F %T'; }

for i in {1..20}; do
  if [ ! -e "$LOCK" ]; then break; fi
  OLD_PID="$(cat "$LOCK" 2>/dev/null || true)"
  if [ -z "$OLD_PID" ] || ! kill -0 "$OLD_PID" 2>/dev/null; then rm -f "$LOCK"; break; fi
  echo "[$(ts)] fetch-all running pid=$OLD_PID; wait $i/20" >> "$LOG"
  sleep 30
done
if [ -e "$LOCK" ]; then
  echo "[$(ts)] lock still held after 10 minutes; skip this run" >> "$LOG"
  exit 0
fi
echo "$$" > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

echo "[$(ts)] fetch-x-home START" >> "$LOG"
python3 "$SCRIPT_DIR/fetch-twitter-home.py" >> "$LOG" 2>&1
echo "[$(ts)] fetch-x-home DONE exit=$?" >> "$LOG"
