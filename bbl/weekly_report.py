#!/usr/bin/env python3
"""Build a Monday-Sunday BBL analyst report from completed nightly data."""
from __future__ import annotations

import argparse
import datetime as dt
import html
import subprocess
import sys
import tempfile
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
        best, _worst, _manager, _stinker, totals, status = load(box, roster)
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
    md = [f"# BBL Weekly Analyst Report · {label}", "", f"**Manager of the Week:** {manager} — {manager_score} BBL pts", f"**Stinker of the Week:** {stinker} — {stinker_score} BBL pts", "", narrative, "", "## Weekly Top Performers", "", "| # | Player | Manager | Games | BBL pts | Peak night |", "|---:|---|---|---:|---:|---:|"]
    for i, (name, item) in enumerate(top, 1):
        md.append(f"| {i} | {name} | {owner_label(item)} | {item['games']} | {item['fp']} | {item['peak']} |")
    md += ["", "## Weekly Strugglers", "", "Players shown here played at least 2 games and 40 minutes.", "", "| # | Player | Manager | Games | Avg BBL pts | Total |", "|---:|---|---|---:|---:|---:|"]
    for i, (name, item) in enumerate(low[:10], 1):
        md.append(f"| {i} | {name} | {owner_label(item)} | {item['games']} | {item['fp'] / item['games']:.1f} | {item['fp']} |")
    md += ["", "## Analyst Notes", "", f"Best single-night peak: {short_day(best_night[0])}. Lowest individual outing: {short_day(worst_night[0])}.", "", "Roster ownership is assigned from the snapshot used for each night, so trades and waivers are reflected when snapshots are available."]
    (out / "Weekly Analyst Report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    caption = f"BBL Weekly Analyst Report · {label}\nManager of the Week: {manager}\nStinker of the Week: {stinker}"
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    html_rows = "".join(f"<tr><td>{i}</td><td>{html.escape(n)}</td><td>{html.escape(owner_label(x))}</td><td>{x['games']}</td><td>{x['fp']}</td><td>{x['peak']}</td></tr>" for i, (n, x) in enumerate(top, 1))
    low_rows = "".join(f"<tr><td>{i}</td><td>{html.escape(n)}</td><td>{html.escape(owner_label(x))}</td><td>{x['games']}</td><td>{x['fp'] / x['games']:.1f}</td><td>{x['fp']}</td></tr>" for i, (n, x) in enumerate(low[:10], 1))
    page = f'''<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#08111f;color:#e7edf7;font-family:Arial,sans-serif}}#card{{width:1080px;padding:42px 38px 32px;background:#0d1728}}h1{{font-size:52px;margin:0;color:#f5f7fb}}.sub{{color:#25c9ed;letter-spacing:5px;font-size:20px;margin:12px 0 24px}}.award{{border:2px solid #ff972f;border-radius:14px;padding:18px 24px;margin-bottom:18px}}.award b{{color:#ff972f;letter-spacing:3px}}.award strong{{display:block;font-size:34px;margin-top:7px}}.copy{{font-size:19px;line-height:1.45;color:#b9c7d9;margin:20px 0}}h2{{color:#28d0ed;letter-spacing:3px;font-size:22px;margin:25px 0 8px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px 10px;border-bottom:1px solid #203653;text-align:left}}th{{color:#91a2b9;text-transform:uppercase;letter-spacing:1px;font-size:13px}}td:first-child{{color:#ff972f;font-weight:700}}.low td:first-child{{color:#c879ff}}footer{{margin-top:22px;color:#71839b;text-align:center;font-size:13px}}</style></head><body><div id="card"><h1>BBL WEEKLY ANALYST REPORT</h1><div class="sub">{html.escape(label.upper())}</div><div class="award"><b>MANAGER OF THE WEEK</b><strong>{html.escape(manager)} · {manager_score} BBL PTS</strong><span>{html.escape(narrative)}</span></div><h2>WEEKLY TOP PERFORMERS</h2><table><tr><th>#</th><th>Player</th><th>Manager</th><th>Games</th><th>Total</th><th>Peak</th></tr>{html_rows}</table><h2>WEEKLY STRUGGLERS</h2><table class="low"><tr><th>#</th><th>Player</th><th>Manager</th><th>Games</th><th>Avg</th><th>Total</th></tr>{low_rows}</table><footer>BBL weekly totals · ownership follows each night's roster snapshot</footer></div></body></html>'''
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp) / "weekly.html"; source.write_text(page, encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "bbl/render.py"), str(source), str(out / "Weekly Analyst Report.png"), "#card", "1080", "1"], check=True)
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
