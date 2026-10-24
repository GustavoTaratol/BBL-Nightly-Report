#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Run setup-mac.command first."
  read -r -p "Press Enter to close..."
  exit 1
fi
set -a
[ -f .env ] && . ./.env
set +a
.venv/bin/python bbl/cbs_rosters.py --headed --base-url "$BBL_CBS_BASE_URL" \
  --profile "${BBL_DATA_DIR:-./data}/browser/cbs-profile" \
  --out "${BBL_DATA_DIR:-./data}/rosters/current.txt"
echo
echo "CBS roster saved. You can now test run-scheduled.command."
read -r -p "Press Enter to close..."
