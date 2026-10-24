#!/usr/bin/env python3
"""BBL Report Agent: one deterministic entry point for all report jobs."""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("BBL_DATA_DIR", ROOT / "data")).resolve()
PYTHON = sys.executable


def log(message: str) -> None:
    line = f"{dt.datetime.now().astimezone().isoformat()} {message}"
    print(line, flush=True)
    path = DATA / "logs" / "agent.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def command(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    log("RUN " + " ".join(args))
    return subprocess.run(args, cwd=ROOT, text=True, check=check)


def nightly(args) -> None:
    from automation import run_once

    date = args.date or ((dt.datetime.now().date() - dt.timedelta(days=1)) if dt.datetime.now().hour < 12 else dt.datetime.now().date()).strftime("%Y%m%d")
    log(f"NIGHTLY start date={date}")
    run_once(date, args.poll_minutes, args.skip_rosters, args.no_publish)
    log(f"NIGHTLY complete date={date}")


def weekly(args, draft: bool) -> None:
    today = dt.datetime.now().date()
    if args.end_date:
        end = dt.datetime.strptime(args.end_date, "%Y%m%d").date()
    elif draft:
        end = today - dt.timedelta(days=1) if today.weekday() == 6 else today - dt.timedelta(days=(today.weekday() + 2) % 7)
    else:
        end = today - dt.timedelta(days=1) if today.weekday() == 0 else today
    start = end - dt.timedelta(days=6)
    prefix = "week-draft" if draft else "week"
    output = DATA / "reports" / f"{prefix}-{start:%Y%m%d}-{end:%Y%m%d}"
    log(f"WEEKLY {'draft' if draft else 'final'} start={start} end={end}")
    result = command([
        PYTHON, str(ROOT / "bbl/weekly_report.py"),
        "--end-date", end.strftime("%Y%m%d"),
        "--data-dir", str(DATA),
        "--output-dir", str(output),
    ], check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    if not draft and not args.no_publish:
        command([PYTHON, str(ROOT / "bbl/publish.py"), str(output)], check=False)
    log(f"WEEKLY {'draft' if draft else 'final'} complete output={output}")


def status(_args) -> None:
    completed = sorted((DATA / "completed").glob("*.ok")) if (DATA / "completed").exists() else []
    snapshots = sorted((DATA / "rosters" / "snapshots").glob("*.txt")) if (DATA / "rosters" / "snapshots").exists() else []
    history = DATA / "transactions" / "history.jsonl"
    print(f"BBL Report Agent")
    print(f"data: {DATA}")
    print(f"completed nightly reports: {len(completed)}")
    print(f"roster snapshots: {len(snapshots)}")
    print(f"transaction history: {history if history.exists() else 'not created yet'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="job", required=True)

    night = sub.add_parser("nightly", help="refresh data and generate one nightly report")
    night.add_argument("--date", help="YYYYMMDD; defaults to the current BBL night")
    night.add_argument("--poll-minutes", type=int, default=15)
    night.add_argument("--skip-rosters", action="store_true")
    night.add_argument("--no-publish", action="store_true")
    night.set_defaults(func=nightly)

    for name, draft in (("weekly-draft", True), ("weekly", False)):
        weekly_parser = sub.add_parser(name, help="generate the text-only weekly digest")
        weekly_parser.add_argument("--end-date", help="YYYYMMDD; overrides automatic period selection")
        weekly_parser.add_argument("--no-publish", action="store_true")
        weekly_parser.set_defaults(func=lambda args, draft=draft: weekly(args, draft))

    state = sub.add_parser("status", help="show agent state")
    state.set_defaults(func=status)
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except Exception as exc:
        log(f"ERROR {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
