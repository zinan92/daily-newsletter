#!/usr/bin/env bash
# push-digest.sh — Run the daily digest stages.
# Intended for the fixed daily launchd run after the morning fetch window.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG="$SCRIPT_DIR/logs/push-digest.log"
FETCH_LOCK="$SCRIPT_DIR/logs/fetch.lock"
mkdir -p logs

ts() { date '+%F %T'; }
run_date_from_batch() {
  local batch="$1"
  local head="${batch:0:8}"
  if [[ "$head" =~ ^[0-9]{8}$ ]]; then
    echo "${head:0:4}-${head:4:2}-${head:6:2}"
  else
    date '+%F'
  fi
}

{
  echo ""
  echo "=========================================="
  echo "[$(ts)] push-digest START"
  echo "=========================================="
} >> "$LOG"

for i in {1..60}; do
  if [ ! -e "$FETCH_LOCK" ]; then
    break
  fi
  FETCH_PID="$(cat "$FETCH_LOCK" 2>/dev/null || true)"
  if [ -z "$FETCH_PID" ] || ! kill -0 "$FETCH_PID" 2>/dev/null; then
    rm -f "$FETCH_LOCK"
    break
  fi
  echo "[$(ts)] fetch still running pid=$FETCH_PID; wait $i/60" >> "$LOG"
  sleep 60
done

if [ -e "$FETCH_LOCK" ]; then
  echo "[$(ts)] fetch still running after 60 minutes; skip this digest" >> "$LOG"
  exit 0
fi

PREFLIGHT_WARNINGS=()
if [ "${PARKIO_IGNORE_BLOCKING_DEPS:-0}" != "1" ]; then
  echo "[$(ts)] >>> morning-preflight.py" >> "$LOG"
  PREFLIGHT_OUTPUT="$(python3 "$SCRIPT_DIR/morning-preflight.py" 2>&1)"
  EXIT=$?
  printf '%s\n' "$PREFLIGHT_OUTPUT" >> "$LOG"
  if [ "$EXIT" -eq 2 ]; then
    echo "[$(ts)] recoverable source auth/cookie problem; continue scheduled push with degraded source health" >> "$LOG"
    python3 "$SCRIPT_DIR/generate-status.py" >> "$LOG" 2>&1 || true
    PREFLIGHT_WARNINGS+=("recoverable source auth/cookie problem; generated available-source digest anyway")
    if [ "${PARKIO_PREFLIGHT_BLOCK:-0}" = "1" ]; then
      echo "[$(ts)] PARKIO_PREFLIGHT_BLOCK=1; skip scheduled push" >> "$LOG"
      exit 0
    fi
  elif [ "$EXIT" -ne 0 ]; then
    echo "[$(ts)] !!! morning-preflight.py exit=$EXIT" >> "$LOG"
    exit "$EXIT"
  fi
fi

echo "[$(ts)] >>> stages/to_md/run.py" >> "$LOG"
python3 "$SCRIPT_DIR/stages/to_md/run.py" >> "$LOG" 2>&1
EXIT=$?
if [ "$EXIT" -ne 0 ]; then
  echo "[$(ts)] !!! stages/to_md/run.py exit=$EXIT" >> "$LOG"
  exit "$EXIT"
fi

echo "[$(ts)] >>> stages/coarse_filter/run.py" >> "$LOG"
BATCH_ID="$(python3 "$SCRIPT_DIR/stages/coarse_filter/run.py" 2>> "$LOG" | tail -n 1)"
if [ -z "$BATCH_ID" ]; then
  echo "[$(ts)] no batch opened; nothing to process" >> "$LOG"
  echo "[$(ts)] push-digest DONE" >> "$LOG"
  exit 0
fi
export PARKIO_BATCH_ID="$BATCH_ID"
RUN_DATE="$(run_date_from_batch "$PARKIO_BATCH_ID")"
echo "[$(ts)] batch=$PARKIO_BATCH_ID" >> "$LOG"
echo "[$(ts)] run_date=$RUN_DATE" >> "$LOG"

PARKIO_SKIP_SEND="${PARKIO_SKIP_SEND:-1}"
STAGES=(build-digest.py stages/archive/run.py finalize-local.py)
if [ "$PARKIO_SKIP_SEND" = "1" ]; then
  echo "[$(ts)] PARKIO_SKIP_SEND=1; skip Telegram send-artifacts.py; local sent already finalized" >> "$LOG"
else
  STAGES+=(send-artifacts.py)
fi

for stage in "${STAGES[@]}"; do
  echo "[$(ts)] >>> $stage" >> "$LOG"
  python3 "$SCRIPT_DIR/$stage" >> "$LOG" 2>&1
  EXIT=$?
  if [ "$EXIT" -ne 0 ]; then
    echo "[$(ts)] !!! $stage exit=$EXIT" >> "$LOG"
    echo "[$(ts)] push-digest STOPPED at $stage" >> "$LOG"
    exit "$EXIT"
  fi
done

echo "[$(ts)] >>> build-product-radar.py" >> "$LOG"
python3 "$SCRIPT_DIR/build-product-radar.py" --date "$RUN_DATE" >> "$LOG" 2>&1
EXIT=$?
if [ "$EXIT" -ne 0 ]; then
  echo "[$(ts)] !!! build-product-radar.py exit=$EXIT; continue with degraded daily bundle" >> "$LOG"
  PREFLIGHT_WARNINGS+=("Product Radar 生成失败：build-product-radar.py exit=$EXIT")
fi

echo "[$(ts)] >>> build-daily-bundle.py" >> "$LOG"
BUNDLE_ARGS=(--date "$RUN_DATE")
for warning in ${PREFLIGHT_WARNINGS[@]+"${PREFLIGHT_WARNINGS[@]}"}; do
  BUNDLE_ARGS+=(--warning "$warning")
done
python3 "$SCRIPT_DIR/build-daily-bundle.py" "${BUNDLE_ARGS[@]}" >> "$LOG" 2>&1
EXIT=$?
if [ "$EXIT" -ne 0 ]; then
  echo "[$(ts)] !!! build-daily-bundle.py exit=$EXIT" >> "$LOG"
  echo "[$(ts)] push-digest STOPPED at build-daily-bundle.py" >> "$LOG"
  exit "$EXIT"
fi

echo "[$(ts)] >>> reader-quality.py" >> "$LOG"
python3 "$SCRIPT_DIR/reader_quality.py" --date "$RUN_DATE" >> "$LOG" 2>&1
EXIT=$?
if [ "$EXIT" -ne 0 ]; then
  echo "[$(ts)] !!! reader-quality.py exit=$EXIT" >> "$LOG"
  echo "[$(ts)] push-digest STOPPED at reader-quality.py" >> "$LOG"
  exit "$EXIT"
fi

echo "[$(ts)] >>> generate-status.py" >> "$LOG"
python3 "$SCRIPT_DIR/generate-status.py" >> "$LOG" 2>&1
EXIT=$?
if [ "$EXIT" -ne 0 ]; then
  echo "[$(ts)] !!! generate-status.py exit=$EXIT" >> "$LOG"
fi

echo "[$(ts)] push-digest DONE" >> "$LOG"
