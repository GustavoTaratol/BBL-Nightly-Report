#!/usr/bin/env python3
"""Summarize BBL agent health without contacting external services."""
from __future__ import annotations

import json
from pathlib import Path


def snapshot(data: Path) -> dict:
    completed = sorted((data / "completed").glob("*.ok")) if (data / "completed").exists() else []
    reports = sorted((data / "reports").glob("*/")) if (data / "reports").exists() else []
    transactions = data / "transactions" / "history.jsonl"
    events = transactions.read_text(encoding="utf-8").count("\n") if transactions.exists() else 0
    log = data / "logs" / "agent.log"
    last_log = log.read_text(encoding="utf-8").splitlines()[-1] if log.exists() and log.read_text(encoding="utf-8").splitlines() else ""
    return {
        "completed_nightly_reports": len(completed),
        "last_completed": completed[-1].stem if completed else None,
        "generated_report_directories": len(reports),
        "transaction_events": events,
        "last_agent_log": last_log,
        "backups": len(list((data / "backups").glob("*/"))) if (data / "backups").exists() else 0,
    }


def print_health(data: Path) -> None:
    print(json.dumps(snapshot(data), indent=2, ensure_ascii=False))
