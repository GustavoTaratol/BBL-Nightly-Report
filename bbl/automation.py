#!/usr/bin/env python3
"""Unattended nightly BBL report runner for TrueNAS or another always-on host."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("BBL_DATA_DIR", ROOT / "data")).resolve()
ROSTERS = Path(os.environ.get("BBL_ROSTERS_FILE", DATA / "rosters/current.txt")).resolve()
PYTHON = sys.executable


def run(args, check=True):
    return subprocess.run(args, cwd=ROOT, text=True, check=check)


def date_for_now() -> str:
    now = dt.datetime.now()
    return (now.date() - dt.timedelta(days=1) if now.hour < 12 else now.date()).strftime("%Y%m%d")


def refresh_rosters() -> None:
    base_url = os.environ.get("BBL_CBS_BASE_URL")
    if not base_url:
        raise RuntimeError("BBL_CBS_BASE_URL is required for unattended operation")
    run([PYTHON, str(ROOT / "bbl/cbs_rosters.py"), "--base-url", base_url,
         "--profile", str(DATA / "browser/cbs-profile"), "--out", str(ROSTERS)])


def fetch_status(date: str) -> tuple[int, int, int]:
    box = DATA / "boxscores" / f"{date}.txt"
    box.parent.mkdir(parents=True, exist_ok=True)
    result = run([PYTHON, str(ROOT / "bbl/fetch_box.py"), date, str(box)], check=False)
    if result.returncode:
        raise RuntimeError("ESPN fetch failed")
    fields = box.read_text(encoding="utf-8").splitlines()[0].lstrip("#").split("|")
    return tuple(map(int, fields))


def generate(date: str) -> Path:
    box = DATA / "boxscores" / f"{date}.txt"
    report_dir = Path(os.environ.get("BBL_OUTPUT_DIR", DATA / "reports")) / date
    label = dt.datetime.strptime(date, "%Y%m%d").strftime("%a %b %-d")
    run([PYTHON, str(ROOT / "bbl/social_cards.py"), str(box), str(ROSTERS),
         str(report_dir), label])
    return report_dir


def run_once(date: str, poll_minutes: int, skip_rosters: bool, no_publish: bool) -> None:
    marker = DATA / "completed" / f"{date}.ok"
    if marker.exists():
        print(f"{date}: already completed; skipping")
        return
    if not skip_rosters:
        try:
            refresh_rosters()
        except Exception as exc:
            if ROSTERS.exists() and ROSTERS.stat().st_size > 100:
                print(f"CBS roster refresh unavailable; using last saved roster snapshot ({exc})", flush=True)
            else:
                raise
    if not ROSTERS.exists():
        raise RuntimeError(f"No roster snapshot exists at {ROSTERS}")

    while True:
        games, finished, live = fetch_status(date)
        print(f"{date}: {finished}/{games} games final; {live} in progress", flush=True)
        if games == 0:
            print("No games scheduled; nothing to generate")
            return
        if finished == games:
            break
        time.sleep(max(1, poll_minutes) * 60)

    report_dir = generate(date)
    caption = report_dir / "caption.txt"
    caption.write_text(f"BBL Nightly Report · {date}\nTop 10 Performances and Top 10 Worst Performances attached.", encoding="utf-8")
    alt = report_dir / "alt-text.txt"
    alt.write_text("Two dark navy BBL nightly report cards: Top 10 performances and Top 10 worst performances, each with manager awards and mentions.", encoding="utf-8")
    if not no_publish:
        run([PYTHON, str(ROOT / "bbl/publish.py"), str(report_dir)])
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(dt.datetime.now(dt.timezone.utc).isoformat() + "\n", encoding="utf-8")
    print(f"Completed report: {report_dir}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYYMMDD; defaults to the current BBL night")
    parser.add_argument("--once", action="store_true", help="run once and exit")
    parser.add_argument("--skip-rosters", action="store_true", help="use the last roster snapshot")
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--force", action="store_true", help="regenerate a completed date")
    parser.add_argument("--poll-minutes", type=int, default=15)
    args = parser.parse_args()
    date = args.date or date_for_now()
    if args.force:
        marker = DATA / "completed" / f"{date}.ok"
        marker.unlink(missing_ok=True)
    if args.once or args.date:
        run_once(date, args.poll_minutes, args.skip_rosters, args.no_publish)
        return 0
    while True:
        try:
            run_once(date_for_now(), args.poll_minutes, args.skip_rosters, args.no_publish)
        except Exception as exc:
            print(f"Automation run failed: {exc}", file=sys.stderr, flush=True)
        time.sleep(3600)


if __name__ == "__main__":
    raise SystemExit(main())
