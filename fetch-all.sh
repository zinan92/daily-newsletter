#!/usr/bin/env bash
# fetch-all.sh — Run the Fetch Raw stage only.
# Cron-callable every 4 hours. Processing and pushing happen in push-digest.sh.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DOWNLOAD_CAPABILITY="${PARKIO_DOWNLOAD_CAPABILITY:-$HOME/content-toolkit/capabilities/download}"
if [ -d "$DOWNLOAD_CAPABILITY" ]; then
  export PYTHONPATH="$DOWNLOAD_CAPABILITY${PYTHONPATH:+:$PYTHONPATH}"
fi

choose_python() {
  local candidate
  if [ -n "${PARKIO_PYTHON:-}" ] && [ -x "$PARKIO_PYTHON" ]; then
    echo "$PARKIO_PYTHON"
    return
  fi
  for candidate in /usr/local/bin/python3 /opt/homebrew/bin/python3 "$DOWNLOAD_CAPABILITY/.venv/bin/python" python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
      then
        echo "$candidate"
        return
      fi
    fi
  done
  echo "python3"
}

PYTHON_BIN="$(choose_python)"

LOG="$SCRIPT_DIR/logs/fetch-all.log"
LOCK="$SCRIPT_DIR/logs/fetch.lock"
mkdir -p logs

ts() { date '+%F %T'; }

if [ -e "$LOCK" ]; then
  OLD_PID="$(cat "$LOCK" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "[$(ts)] fetch already running pid=$OLD_PID" >> "$LOG"
    exit 0
  fi
fi
echo "$$" > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

{
  echo ""
  echo "=========================================="
  echo "[$(ts)] fetch-all START"
  echo "[$(ts)] python=$("$PYTHON_BIN" -c 'import sys; print(sys.executable + " " + sys.version.split()[0])' 2>&1)"
  echo "=========================================="
} >> "$LOG"

for stage in stages/fetch/run.py; do
  echo "[$(ts)] >>> $stage" >> "$LOG"
  "$PYTHON_BIN" "$SCRIPT_DIR/$stage" >> "$LOG" 2>&1
  EXIT=$?
  if [ "$EXIT" -ne 0 ]; then
    echo "[$(ts)] !!! $stage exit=$EXIT" >> "$LOG"
  fi
done

echo "[$(ts)] fetch-all DONE" >> "$LOG"
