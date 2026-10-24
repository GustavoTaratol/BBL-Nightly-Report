#!/usr/bin/env python3
"""Create recoverable backups of BBL runtime state."""
from __future__ import annotations

import datetime as dt
import os
import shutil
from pathlib import Path


def backup_state(data: Path) -> Path:
    root = Path(os.environ.get("BBL_BACKUP_DIR", data / "backups"))
    target = root / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    target.mkdir(parents=True, exist_ok=False)
    for relative in (
        Path("rosters/current.txt"), Path("rosters/snapshots"),
        Path("boxscores"), Path("transactions/history.jsonl"),
        Path("completed"), Path("logs"),
    ):
        source = data / relative
        if not source.exists():
            continue
        destination = target / relative
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    print(f"Backup: {target}")
    return target
