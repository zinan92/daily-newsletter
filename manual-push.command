#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
export PARKIO_IGNORE_BLOCKING_DEPS=1
export PARKIO_SKIP_SEND="${PARKIO_SKIP_SEND:-1}"

echo "Daily Inbox manual push"
echo "Working directory: $PWD"
echo ""

echo ">>> fetch-all.sh"
./fetch-all.sh

echo ""
echo ">>> push-feishu-digest.sh"
./push-feishu-digest.sh

echo ""
echo "Manual push finished. Press Return to close this window."
read -r _
