#!/usr/bin/env python3
"""Fail-closed validation for BBL inputs before a report is published."""
from __future__ import annotations

from pathlib import Path


def validate_box(path: Path, require_final: bool = True) -> tuple[int, int, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("#"):
        raise ValueError(f"Invalid ESPN boxscore header: {path}")
    try:
        games, finished, live = map(int, lines[0][1:].split("|"))
    except ValueError as exc:
        raise ValueError(f"Invalid ESPN game status: {path}") from exc
    if require_final and games and finished != games:
        raise ValueError(f"ESPN data is incomplete: {finished}/{games} games final")
    names = []
    for line in lines[1:]:
        fields = line.split("|")
        if len(fields) < 17:
            raise ValueError(f"Malformed player row in {path}: {line[:80]}")
        names.append(fields[0])
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Duplicate players in {path}: {', '.join(duplicates[:5])}")
    if finished and not names:
        raise ValueError(f"No player rows found for completed games: {path}")
    return games, finished, live


def validate_roster(path: Path) -> None:
    if not path.exists() or path.stat().st_size < 100:
        raise ValueError(f"Roster file is missing or unexpectedly small: {path}")
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            names.append(line.split("|", 1)[0])
    if len(names) < 10:
        raise ValueError(f"Roster file contains too few players: {path}")
    if len(names) != len(set(names)):
        raise ValueError(f"Roster file contains duplicate players: {path}")
