#!/usr/bin/env python3
"""Build the two deterministic group-chat cards for one completed night."""
from __future__ import annotations

import html
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def fpt(value):
    return f"−{abs(value)}" if value < 0 else str(value)


def load(box_path, roster_path):
    lines = Path(box_path).read_text(encoding="utf-8").strip().splitlines()
    header = lines[0].lstrip("#").split("|")
    ngames, ndone, nlive = map(int, header)
    owner, positions, status = {}, {}, {}
    for line in Path(roster_path).read_text(encoding="utf-8").splitlines():
        fields = line.split("|")
        if len(fields) >= 3 and not fields[0].startswith("#"):
            positions[fields[0]] = fields[2]
        if len(fields) >= 4 and fields[3].startswith("TAKEN:"):
            owner[fields[0]] = fields[3][6:]
            status[fields[0]] = fields[4] if len(fields) >= 5 else "ACTIVE"
    players = []
    for line in lines[1:]:
        f = line.split("|")
        try:
            name, team = f[0], f[1]
            vals = [int(float(x or 0)) for x in f[2:16]]
            mins, pts, fgm, fga, tpm, tpa, ftm, fta, reb, ast, to, stl, blk, pf = vals
        except (ValueError, IndexError):
            continue
        base = pts + 2 * fgm - fga + ftm - fta + reb + 2 * ast + 4 * stl + 4 * blk - 2 * to - pf
        espn_pos = f[16].upper() if len(f) > 16 else ""
        fallback = {"PG":"G", "SG":"G", "G":"G", "SF":"F", "PF":"F", "F":"F", "C":"C"}
        eligible = set(positions.get(name, "" ).split(",")) or {fallback.get(espn_pos, "")}
        bonus = {"G": reb, "F": ast, "C": tpm}
        choices = [(bonus[slot], slot) for slot in "GFC" if slot in eligible]
        slot_bonus, slot = max(choices) if choices else (0, "")
        players.append({"n": name, "t": team, "m": mins, "pts": pts, "fgm": fgm, "fga": fga,
                        "reb": reb, "ast": ast, "to": to, "stl": stl, "blk": blk,
                        "base": base, "fp": base + slot_bonus, "slot": slot, "bonus": slot_bonus,
                        "owner": owner.get(name, "Free agent"), "status": status.get(name, "FREE_AGENT")})
    best = sorted(players, key=lambda p: (-p["fp"], -p["base"], p["m"]))
    worst = sorted((p for p in players if p["m"] >= 20), key=lambda p: (p["fp"], p["base"], -p["m"]))
    totals = {}
    counts = {}
    for p in players:
        if p["owner"] != "Free agent" and p["status"] == "ACTIVE":
            totals[p["owner"]] = totals.get(p["owner"], 0) + p["fp"]
            counts[p["owner"]] = counts.get(p["owner"], 0) + 1
    manager = max(totals, key=lambda n: (totals[n], counts[n])) if totals else "—"
    # Stinker is a manager award, so only a player actually started by a
    # manager and appearing in the displayed Worst 10 can qualify.
    stinker_candidates = [p for p in worst[:10] if p["owner"] != "Free agent" and p["status"] == "ACTIVE"]
    stinker_player = stinker_candidates[0] if stinker_candidates else None
    stinker = stinker_player["owner"] if stinker_player else None
    return best, worst, manager, stinker, stinker_player, totals, (ngames, ndone, nlive)


def card_html(title, accent, subtitle, award_label, award_name, award_summary, rows, mentions, worst=False):
    rows_html = "".join(
        f'<div class="row"><div class="rank">{i}</div><div class="who"><b>{html.escape(p["n"])}</b>'
        f'<span class="team">{html.escape(p["t"])}</span><small>{html.escape(p["owner"])}</small>'
        f'<em class="meta">{html.escape(p["slot"] or "—")} slot · base {p["base"]} · {p["m"]} min</em></div>'
        f'<div class="score">{fpt(p["fp"])}<small>BBL PTS</small></div>'
        f'<div class="stat">{p["fgm"]}–{p["fga"]}<small>FG</small></div>'
        f'<div class="stat">{p["reb"]}<small>REB</small></div><div class="stat">{p["ast"]}<small>AST</small></div></div>'
        for i, p in enumerate(rows, 1)
    )
    mention_html = "".join(
        f'<div class="mention"><b>{i}</b><span>{html.escape(p["n"])} <i>{html.escape(p["t"])}</i> · {html.escape(p["owner"])}</span><strong>{fpt(p["fp"])}</strong></div>'
        for i, p in enumerate(mentions, len(rows) + 1)
    )
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}body{{margin:0;background:#08111f;color:#e7edf7;font-family:Arial,sans-serif}}
#card{{width:1080px;padding:42px 38px 30px;background:#0d1728}}
h1{{font-size:62px;line-height:.95;margin:0;color:#f4f7fb;letter-spacing:-2px;text-transform:uppercase}}h1 em{{color:{accent};font-style:normal}}
.sub{{font-size:22px;letter-spacing:6px;color:#25c9ed;margin:16px 0 28px;text-align:center}}
.award{{border:2px solid {accent};border-radius:16px;padding:20px 26px;margin-bottom:22px;background:#101e32}}
.label{{font-size:17px;letter-spacing:4px;color:{accent};font-weight:700;text-transform:uppercase}}.award h2{{font-size:42px;margin:8px 0 3px}}.award p{{font-size:23px;margin:0;color:#b9c7d9}}
.cols,.row{{display:grid;grid-template-columns:54px 1fr 150px 100px 90px 90px;gap:12px;align-items:center}}.cols{{padding:0 14px 8px;color:#91a2b9;font-size:15px;letter-spacing:2px;text-transform:uppercase}}
.row{{background:#122139;border:1px solid #203653;border-radius:12px;padding:11px 14px;margin:8px 0}}.rank{{font-size:26px;color:{accent};font-weight:700;text-align:center}}
.who b{{display:block;font-size:25px}}.who .team{{display:inline-block;color:#08111f;background:{accent};border-radius:4px;padding:2px 6px;font-size:13px;font-weight:700;margin-top:5px}}.who small{{display:block;color:#9caec3;font-size:16px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.who .meta{{display:block;color:#71839b;font-size:12px;font-style:normal;margin-top:4px;letter-spacing:.4px}}
.score{{color:{accent};font-size:42px;font-weight:800;text-align:center}}.score small,.stat small{{display:block;font-size:11px;color:#9caec3;letter-spacing:1px}}.stat{{background:#172a45;border-radius:7px;text-align:center;padding:8px 3px;font-size:21px;font-weight:700}}
.section{{border:1px solid #1f4763;border-radius:14px;margin-top:24px;padding:15px}}.section h3{{color:#28d0ed;letter-spacing:3px;margin:0 0 10px;font-size:21px}}.mention{{display:grid;grid-template-columns:44px 1fr 70px;align-items:center;border-top:1px solid #203653;padding:9px 4px;color:#a8b7c9;font-size:17px}}.mention b{{color:#667991}}.mention i{{font-style:normal;color:#71839b}}.mention strong{{color:{accent};text-align:right;font-size:22px}}
footer{{margin-top:22px;text-align:center;color:#687b93;font-size:13px;letter-spacing:1px}}
</style></head><body><div id="card"><h1><em>{"TOP 10 WORST" if worst else "TOP 10"}</em> PERFORMANCE{"S" if not worst else "S"}</h1><div class="sub">BBL NIGHTLY REPORT · {html.escape(subtitle)}</div>
<div class="award"><div class="label">{html.escape(award_label)}</div><h2>{html.escape(award_name)}</h2><p>{html.escape(award_summary)}</p></div>
<div class="cols"><span>#</span><span>PLAYER · MANAGER</span><span>BBL PTS</span><span>FG</span><span>REB</span><span>AST</span></div>{rows_html}
<div class="section"><h3>{"DISHONORABLE" if worst else "HONORABLE"} MENTIONS</h3>{mention_html}</div><footer>BBL points · active lineup players count toward manager awards · reserves are tracked separately</footer></div></body></html>'''


def render(source, target):
    subprocess.run([sys.executable, str(ROOT / "bbl/render.py"), str(source), str(target), "#card", "1080", "1"], check=True)


def build(box, roster, out, label):
    best, worst, manager, stinker, stinker_player, totals, status = load(box, roster)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        top_html = temp / "top.html"; worst_html = temp / "worst.html"
        top_mentions = best[10:13]
        worst_mentions = worst[10:13]
        top10 = best[:10]
        worst10 = worst[:10]
        top_html.write_text(card_html("", "#ff972f", label, "Manager of the Night", manager,
                                      f"active lineup: {totals[manager]} BBL pts · {sum(1 for p in top10 if p['owner'] == manager)} in Top 10",
                                      top10, top_mentions), encoding="utf-8")
        if stinker_player:
            stinker_name = stinker
            stinker_summary = f"started {stinker_player['n']} · {stinker_player['fp']} BBL pts"
        else:
            stinker_name = "No Stinker for Tonight"
            stinker_summary = "No manager started a player in the Worst 10."
        worst_html.write_text(card_html("", "#c879ff", label, "Stinker of the Night", stinker_name,
                                        stinker_summary, worst10, worst_mentions, True), encoding="utf-8")
        render(top_html, out / "Top 10 Performances.png")
        render(worst_html, out / "Top 10 Worst Performances.png")
    return manager, stinker


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("Usage: social_cards.py BOX ROSTERS OUTPUT_DIR DATE_LABEL")
    build(*sys.argv[1:])
