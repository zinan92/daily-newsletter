#!/usr/bin/env bash
# Run the daily digest pipeline, then send the umbrella newsletter to Feishu.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

run_date="$(date '+%F')"
./push-digest.sh
python3 "$SCRIPT_DIR/send-feishu-digest.py" --date "$run_date"
