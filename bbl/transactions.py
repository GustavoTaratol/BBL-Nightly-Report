#!/usr/bin/env python3
"""Track inferred BBL roster transactions from dated CBS roster snapshots.

CBS does not provide a public API for this league. A snapshot diff can prove
that ownership changed, but it cannot always prove whether the change was a
waiver pickup, a normal add/drop, or a trade. Events are therefore labelled
as inferred until a CBS transaction-history page is available.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_roster(path: Path) -> dict[str, str]:
    owners = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw or raw.startswith("#") or raw.startswith("#LOGO"):
            continue
        parts = raw.split("|")
        if len(parts) < 4:
            continue
        owner = parts[3]
        owners[parts[0]] = owner.removeprefix("TAKEN:") if owner.startswith("TAKEN:") else "Free agent"
    return owners


def classify(before: str, after: str) -> str:
    if before == "Free agent" and after != "Free agent":
        return "PICKUP_CANDIDATE"
    if before != "Free agent" and after == "Free agent":
        return "DROP_CANDIDATE"
    if before != "Free agent" and after != "Free agent" and before != after:
        return "TRADE_CANDIDATE"
    return "ROSTER_CHANGE"


def build_events(snapshot_dir: Path) -> list[dict]:
    snapshots = sorted(snapshot_dir.glob("*.txt"))
    events = []
    previous = None
    previous_date = None
    for snapshot in snapshots:
        current = read_roster(snapshot)
        if previous is not None:
            for player in sorted(set(previous) | set(current), key=str.casefold):
                before = previous.get(player, "Free agent")
                after = current.get(player, "Free agent")
                if before == after:
                    continue
                events.append({
                    "date": snapshot.stem,
                    "player": player,
                    "type": classify(before, after),
                    "from_manager": before if before != "Free agent" else None,
                    "to_manager": after if after != "Free agent" else None,
                    "previous_snapshot": previous_date,
                    "source": "roster_snapshot_diff",
                    "confirmed": False,
                })
        previous = current
        previous_date = snapshot.stem
    return events


def rebuild(snapshot_dir: Path, output: Path) -> int:
    events = build_events(snapshot_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(event, ensure_ascii=False) for event in events) + ("\n" if events else ""), encoding="utf-8")
    print(f"Transactions: {len(events)} inferred roster changes")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot_dir")
    parser.add_argument("output")
    args = parser.parse_args()
    raise SystemExit(rebuild(Path(args.snapshot_dir), Path(args.output)))
