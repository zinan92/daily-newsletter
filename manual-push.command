#!/bin/zsh
set -euo pipefail

cd /Users/wendy/work/input-to-park
export PARKIO_IGNORE_BLOCKING_DEPS=1
export PARKIO_SKIP_SEND="${PARKIO_SKIP_SEND:-1}"

echo "Daily Inbox manual push"
echo "Working directory: $PWD"
echo ""

echo ">>> fetch-all.sh"
./fetch-all.sh

echo ""
echo ">>> push-digest.sh"
./push-digest.sh

echo ""
echo "Manual push finished. Press Return to close this window."
read -r _
