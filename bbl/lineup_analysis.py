#!/usr/bin/env python3
"""Analyze active, reserve, missed-score, and worst-lineup candidates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from social_cards import load


def analyze(box: Path, roster: Path) -> dict:
    best, _worst, _manager, _stinker, _player, _totals, status = load(box, roster)
    managers = {}
    for player in best:
        owner = player["owner"]
        if owner == "Free agent":
            continue
        item = managers.setdefault(owner, {"active_points": 0, "reserve_points": 0, "active": [], "reserve": []})
        if player["status"] == "ACTIVE":
            item["active_points"] += player["fp"]
            item["active"].append(player)
        elif player["status"] == "RESERVE":
            item["reserve_points"] += player["fp"]
            item["reserve"].append(player)
    results = {}
    for owner, item in managers.items():
        active = sorted(item["active"], key=lambda p: p["fp"])
        reserve = sorted(item["reserve"], key=lambda p: p["fp"], reverse=True)
        results[owner] = {
            "active_points": item["active_points"],
            "reserve_points": item["reserve_points"],
            "best_unused": {"name": reserve[0]["n"], "fp": reserve[0]["fp"]} if reserve else None,
            "worst_started": {"name": active[0]["n"], "fp": active[0]["fp"]} if active else None,
        }
    return {"status": {"games": status[0], "finished": status[1], "live": status[2]}, "managers": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("box")
    parser.add_argument("roster")
    parser.add_argument("output")
    args = parser.parse_args()
    result = analyze(Path(args.box), Path(args.roster))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Lineup analysis: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
