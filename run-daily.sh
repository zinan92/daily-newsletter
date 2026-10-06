#!/usr/bin/env bash
# run-daily.sh — one command for a self-hosted daily.
#
#   fetch every source this machine can reach → AI writes the daily →
#   (optional) send it to Feishu → print where the Markdown is.
#
# Settings come from .env (copy .env.example). Check what will work first with
# `python3 doctor.py`. Schedule it once a day with cron or launchd (README).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
. "$SCRIPT_DIR/scripts/load-env.sh"
mkdir -p logs

# cron / launchd start with a bare PATH and no activated venv. Use the repo's
# .venv when there is one, so every stage runs on the Python the README set up.
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  export PATH="$SCRIPT_DIR/.venv/bin:$PATH"
  export PARKIO_PYTHON="${PARKIO_PYTHON:-$SCRIPT_DIR/.venv/bin/python}"
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  echo "✗ 需要 Python 3.11+。按 README 第 1 步在仓库里建 .venv，或设置 PATH。"
  exit 1
fi

ts() { date '+%F %T'; }

echo "[$(ts)] 1/3 检查环境"
if ! python3 doctor.py > logs/doctor.log 2>&1; then
  cat logs/doctor.log
  exit 1
fi

echo "[$(ts)] 2/3 抓取来源（几分钟；详细日志 logs/fetch-all.log）"
./fetch-all.sh

echo "[$(ts)] 3/3 AI 理解、合并、挑选、写日报（十几分钟到半小时；详细日志 logs/push-digest.log）"
if ! ./push-digest.sh; then
  echo "[$(ts)] ✗ 日报没生成。最后几行日志："
  tail -n 25 logs/push-digest.log
  exit 1
fi

PARKIO_HOME_DIR="$(python3 -c 'import lib; print(lib.PARKIO)')"
DAILY="$PARKIO_HOME_DIR/006_ai daily newsletter/$(date '+%y-%m-%d').md"
if [ ! -f "$DAILY" ]; then
  echo "[$(ts)] ✗ 没找到今天的日报 $DAILY。最后几行日志："
  tail -n 25 logs/push-digest.log
  exit 1
fi

if [ -n "${FEISHU_WEBHOOK_URL:-}" ] && [ -n "${FEISHU_WEBHOOK_SECRET:-}" ]; then
  python3 send-feishu-digest.py --date "$(date '+%F')" || echo "[$(ts)] ! 飞书没发出去，日报文件还在"
fi

echo "[$(ts)] ✓ 今天的日报：$DAILY"
