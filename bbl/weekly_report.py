#!/usr/bin/env python3
"""Build a Monday-Sunday BBL analyst report from completed nightly data."""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

from social_cards import load

ROOT = Path(__file__).resolve().parent.parent


def days_for(end_date: str):
    end = dt.datetime.strptime(end_date, "%Y%m%d").date()
    start = end - dt.timedelta(days=6)
    return start, end, [start + dt.timedelta(days=i) for i in range(7)]


def collect(end_date: str, data: Path):
    start, end, days = days_for(end_date)
    players = defaultdict(lambda: {"fp": 0, "minutes": 0, "games": 0, "owners": defaultdict(int), "peak": -10**9})
    managers = defaultdict(lambda: {"fp": 0, "players": 0, "days": 0})
    daily = []
    missing = []
    for day in days:
        key = day.strftime("%Y%m%d")
        box = data / "boxscores" / f"{key}.txt"
        roster = data / "rosters" / "snapshots" / f"{key}.txt"
        if not roster.exists():
            roster = data / "rosters" / "current.txt"
        if not box.exists() or not roster.exists():
            missing.append(key)
            continue
        best, _worst, _manager, _stinker, _stinker_player, totals, status = load(box, roster)
        daily.append((key, best, totals, status))
        for owner, score in totals.items():
            managers[owner]["fp"] += score
            managers[owner]["days"] += 1
        for player in best:
            item = players[player["n"]]
            item["fp"] += player["fp"]
            item["minutes"] += player["m"]
            item["games"] += 1
            item["peak"] = max(item["peak"], player["fp"])
            if player["owner"] != "Free agent":
                item["owners"][player["owner"]] += player["fp"]
                managers[player["owner"]]["players"] += 1
    return start, end, daily, players, managers, missing


def owner_label(item):
    if not item["owners"]:
        return "Free agent"
    return max(item["owners"], key=item["owners"].get)


def short_day(value: str) -> str:
    return dt.datetime.strptime(value, "%Y%m%d").strftime("%b %-d")


def weekly_story(daily, players, managers, top, low, manager, stinker):
    """Write a text-first, sports-column narrative from the available box scores."""
    appearances = [(key, p) for key, best, _totals, _status in daily for p in best]
    leader_days = sorted(
        ((key, totals.get(manager, 0)) for key, _best, totals, _status in daily),
        key=lambda item: item[1], reverse=True,
    )
    top_player, top_item = top[0]
    peak_day, peak_player_data = max(appearances, key=lambda item: item[1]["fp"])
    peak_player = peak_player_data["n"]
    low_player, low_item = low[0] if low else (None, None)
    leader_day = leader_days[0]
    leader_roster = [name for name, item in top if owner_label(item) == manager][:3]
    leader_roster_text = ", ".join(leader_roster) if leader_roster else "a broad group of contributors"
    category_leaders = {
        "scoring": max(appearances, key=lambda item: item[1]["pts"])[1],
        "rebounding": max(appearances, key=lambda item: item[1]["reb"])[1],
        "playmaking": max(appearances, key=lambda item: item[1]["ast"])[1],
        "defense": max(appearances, key=lambda item: item[1]["stl"] + item[1]["blk"])[1],
    }
    scoring = category_leaders["scoring"]
    rebounding = category_leaders["rebounding"]
    playmaking = category_leaders["playmaking"]
    defense = category_leaders["defense"]
    low_line = (
        f"{low_player} was the lowest qualified weekly scorer, averaging "
        f"{low_item['fp'] / low_item['games']:.1f} BBL points across {low_item['games']} games."
        if low_player else "No player met the minimum qualification for the weekly struggler list."
    )
    def statline(p):
        def noun(value, singular, plural=None):
            return f"{value} {singular if value == 1 else (plural or singular + 's')}"
        return ", ".join([
            noun(p['pts'], 'point'), noun(p['reb'], 'rebound'), noun(p['ast'], 'assist'),
            noun(p['stl'], 'steal'), noun(p['blk'], 'block'),
        ])
    return [
        "## Around the League",
        "",
        f"### {manager} Takes Control",
        "",
        f"{manager} finished atop the manager leaderboard with {managers[manager]['fp']} BBL points. "
        f"The decisive burst came on {short_day(leader_day[0])}, when the roster produced {leader_day[1]} points. "
        f"{leader_roster_text} supplied the biggest pieces of the week-long push, giving {manager} both volume and top-end production.",
        "",
        f"### {top_player} Wins the Player Race",
        "",
        f"{top_player} was the week's most productive player, totaling {top_item['fp']} BBL points over "
        f"{top_item['games']} games with a peak of {top_item['peak']}. The night's highest individual score belonged to "
        f"{peak_player}, whose {peak_player_data['fp']} BBL-point performance on {short_day(peak_day)} came with "
        f"{statline(peak_player_data)}.",
        "",
        "### The Box Score Tells the Story",
        "",
        f"The scoring crown for a single night went to {scoring['n']} with {scoring['pts']} points. "
        f"{rebounding['n']} owned the glass with {rebounding['reb']} rebounds, while {playmaking['n']} created the most offense with "
        f"{playmaking['ast']} assists. On the defensive end, {defense['n']} led the available field with "
        f"{defense['stl']} steals and {defense['blk']} blocks.",
        "",
        "### A Rough Week at the Bottom",
        "",
        f"{low_line} {stinker} finished last among the managers in the current sample with {managers[stinker]['fp']} BBL points. "
        "That is the kind of week where a few cold player lines can pull an entire roster out of the race, especially when the top managers are stacking 60- and 70-point performances.",
        "",
        "### The Week in One Sentence",
        "",
        f"{manager} won the manager race, {top_player} led the weekly player standings, and the league's highest ceiling came from {peak_player} on {short_day(peak_day)}. "
        "The rankings below show who turned that production into a full week of value—and who never found a rhythm.",
        "",
    ]


def build(end_date: str, data: Path, output: Path) -> int:
    start, end, daily, players, managers, missing = collect(end_date, data)
    if missing:
        print("Weekly report waiting for: " + ", ".join(missing), file=sys.stderr)
        return 2
    if not daily:
        print("No completed nightly data for the period", file=sys.stderr)
        return 2

    top = sorted(players.items(), key=lambda kv: (-kv[1]["fp"], -kv[1]["peak"], -kv[1]["minutes"]))[:10]
    qualified = [(name, item) for name, item in players.items() if item["games"] >= 2 and item["minutes"] >= 40]
    low = sorted(qualified, key=lambda kv: (kv[1]["fp"] / kv[1]["games"], kv[1]["fp"], -kv[1]["minutes"]))[:10]
    manager = max(managers, key=lambda n: (managers[n]["fp"], managers[n]["days"]))
    stinker = min(managers, key=lambda n: (managers[n]["fp"], -managers[n]["days"]))
    best_night = max(daily, key=lambda x: max((p["fp"] for p in x[1]), default=-10**9))
    worst_night = min(daily, key=lambda x: min((p["fp"] for p in x[1]), default=10**9))
    label = f"{start.strftime('%b %-d')}–{end.strftime('%b %-d, %Y')}"
    out = Path(output); out.mkdir(parents=True, exist_ok=True)
    manager_score = managers[manager]["fp"]
    stinker_score = managers[stinker]["fp"]
    narrative = (
        f"{manager} led the week with {manager_score} BBL points, combining the strongest total output "
        f"across the seven-night period. {stinker} finished at {stinker_score} points and takes the "
        f"Stinker of the Week award. The week's biggest single-night performance came on {short_day(best_night[0])}, "
        f"while the lowest individual outing came on {short_day(worst_night[0])}."
    )
    md = [f"# BBL Weekly Analyst Report · {label}", "", f"**Manager of the Week:** {manager} — {manager_score} BBL pts", f"**Stinker of the Week:** {stinker} — {stinker_score} BBL pts", "", narrative, ""]
    md += weekly_story(daily, players, managers, top, low, manager, stinker)
    md += ["## Weekly Top Performers", "", "| # | Player | Manager | Games | BBL pts | Peak night |", "|---:|---|---|---:|---:|---:|"]
    for i, (name, item) in enumerate(top, 1):
        md.append(f"| {i} | {name} | {owner_label(item)} | {item['games']} | {item['fp']} | {item['peak']} |")
    md += ["", "## Weekly Strugglers", "", "Players shown here played at least 2 games and 40 minutes.", "", "| # | Player | Manager | Games | Avg BBL pts | Total |", "|---:|---|---|---:|---:|---:|"]
    for i, (name, item) in enumerate(low[:10], 1):
        md.append(f"| {i} | {name} | {owner_label(item)} | {item['games']} | {item['fp'] / item['games']:.1f} | {item['fp']} |")
    md += ["", "## Analyst Notes", "", f"Best single-night peak: {short_day(best_night[0])}. Lowest individual outing: {short_day(worst_night[0])}.", "", "Roster ownership is assigned from the snapshot used for each night, so trades and waivers are reflected when snapshots are available."]
    (out / "Weekly Analyst Report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    # Keep the weekly product deliberately text-first: it is meant to be
    # pasted into the league chat, not consumed as another image card.
    (out / "caption.txt").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Weekly report: {out}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", required=True, help="YYYYMMDD; normally Sunday")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    start, end, _ = days_for(args.end_date)
    output = Path(args.output_dir) if args.output_dir else Path(args.data_dir) / "reports" / f"week-{start:%Y%m%d}-{end:%Y%m%d}"
    raise SystemExit(build(args.end_date, Path(args.data_dir), output))
