#!/usr/bin/env python3
"""Keep the dedicated CBS Chrome profile open for interactive login."""
from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("BBL_CBS_BASE_URL"), required=False)
    parser.add_argument("--profile", default="data/browser/cbs-profile")
    parser.add_argument("--port", type=int, default=9222)
    args = parser.parse_args()
    if not args.base_url:
        parser.error("--base-url or BBL_CBS_BASE_URL is required")
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    profile = Path(args.profile).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([
        chrome,
        f"--remote-debugging-port={args.port}",
        f"--user-data-dir={profile}",
        args.base_url.rstrip("/") + "/home",
    ])
    print("Dedicated CBS Chrome is open. Log in once and leave this window open.", flush=True)
    try:
        while proc.poll() is None:
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nClosing the dedicated CBS browser.", flush=True)
        proc.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
