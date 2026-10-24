#!/bin/bash
set -e
cd "$(dirname "$0")"
set -a
[ -f .env ] && . ./.env
set +a
mkdir -p "${BBL_DATA_DIR:-./data}/logs"
exec .venv/bin/python bbl/automation.py --once --poll-minutes 15 >>"${BBL_DATA_DIR:-./data}/logs/automation.log" 2>&1
