#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Run setup-mac.command first."
  exit 1
fi
set -a
[ -f .env ] && . ./.env
set +a
.venv/bin/python bbl/cbs_browser.py --base-url "$BBL_CBS_BASE_URL" \
  --profile "${BBL_DATA_DIR:-./data}/browser/cbs-profile"
