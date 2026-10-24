#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "BBL Nightly Report — Mac setup"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip playwright
.venv/bin/python -m playwright install chromium
mkdir -p data/{browser/cbs-profile,rosters,boxscores,reports,completed,logs}
if [ ! -f .env ]; then cp .env.example .env; fi
chmod +x run-scheduled.command login-cbs.command
echo
echo "Setup complete. Next: double-click login-cbs.command and sign into CBS."
read -r -p "Press Enter to close..."
