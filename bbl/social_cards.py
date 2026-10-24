#!/usr/bin/env python3
"""Build the two deterministic group-chat cards for one completed night."""
from __future__ import annotations

import base64
import html
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT / "assets" / "bbl-bombastic-logo.jpg"


def logo_data_uri():
    if not LOGO_PATH.exists():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")


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
        photo = f[17] if len(f) > 17 and f[17].startswith(("https://", "http://")) else ""
        fallback = {"PG":"G", "SG":"G", "G":"G", "SF":"F", "PF":"F", "F":"F", "C":"C"}
        eligible = set(positions.get(name, "" ).split(",")) or {fallback.get(espn_pos, "")}
        bonus = {"G": reb, "F": ast, "C": tpm}
        choices = [(bonus[slot], slot) for slot in "GFC" if slot in eligible]
        slot_bonus, slot = max(choices) if choices else (0, "")
        players.append({"n": name, "t": team, "m": mins, "pts": pts, "fgm": fgm, "fga": fga,
                        "reb": reb, "ast": ast, "to": to, "stl": stl, "blk": blk,
                        "base": base, "fp": base + slot_bonus, "slot": slot, "bonus": slot_bonus,
                        "owner": owner.get(name, "Free agent"), "status": status.get(name, "FREE_AGENT"), "photo": photo})
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
    row_parts = []
    for i, p in enumerate(rows, 1):
        def stat_cell(value, label, hot=False, cold=False):
            state = " hot" if hot else " cold" if cold else ""
            return f'<div class="stat{state}"><span>{value}</span><small>{label}</small></div>'

        photo = '<div class="headshot placeholder"></div>'
        if p.get("photo"):
            photo = f'<img class="headshot" src="{html.escape(p["photo"], quote=True)}" alt="" />'
        hot = not worst
        cold = worst
        fg_hot = hot and p["fgm"] >= 10
        reb_hot = hot and p["reb"] >= 12
        ast_hot = hot and p["ast"] >= 8
        fg_cold = cold and (p["fgm"] <= 2 or p["fga"] >= 20 and p["fgm"] <= 5)
        reb_cold = cold and p["reb"] <= 2
        ast_cold = cold and p["ast"] <= 1
        row_parts.append(
            f'<div class="row"><div class="rank"><span>{i:02}</span><small>RANK</small></div><div class="who">{photo}'
            f'<div class="identity"><b>{html.escape(p["n"])}</b><span class="team">{html.escape(p["t"])}</span></div>'
            f'<div class="details"><small>{html.escape(p["owner"])}</small><em>{html.escape(p["slot"] or "—")} SLOT · BASE {p["base"]} · {p["m"]} MIN</em></div></div>'
            f'<div class="score">{fpt(p["fp"])}<small>BBL PTS</small></div>'
            + stat_cell(f'{p["fgm"]}–{p["fga"]}', "FG", fg_hot, fg_cold)
            + stat_cell(p["reb"], "REB", reb_hot, reb_cold)
            + stat_cell(p["ast"], "AST", ast_hot, ast_cold)
            + '</div>'
        )
    rows_html = "".join(row_parts)
    mention_html = "".join(
        f'<div class="mention"><b>{i}</b><span>{html.escape(p["n"])} <i>{html.escape(p["t"])}</i> · {html.escape(p["owner"])}</span><strong>{fpt(p["fp"])}</strong></div>'
        for i, p in enumerate(mentions, len(rows) + 1)
    )
    logo = logo_data_uri()
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}body{{margin:0;background:#050b16;color:#edf7ff;font-family:Arial,sans-serif}}
#card{{width:1080px;min-height:1350px;padding:24px 34px 22px;background:#08111f;background-image:radial-gradient(circle at 50% 50%,transparent 0 112px,rgba(38,194,235,.055) 114px,transparent 117px),linear-gradient(90deg,transparent 49.6%,rgba(38,194,235,.045) 49.8%,transparent 50.2%),linear-gradient(45deg,transparent 49.7%,rgba(38,194,235,.035) 49.9%,transparent 50.1%);background-size:360px 360px;border:1px solid #183b59}}
.brand{{height:118px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #1c4968;margin-bottom:11px}}.feed{{color:#527a96;font:700 13px monospace;letter-spacing:2px}}.brand img{{width:112px;height:112px;object-fit:cover;border-radius:20px;border:2px solid #21d7ff;box-shadow:0 0 30px rgba(33,215,255,.7)}}
h1{{font-size:48px;line-height:.9;margin:0;color:#f4f7fb;letter-spacing:-2px;text-transform:uppercase}}h1 em{{color:{accent};font-style:normal;text-shadow:0 0 18px {accent}55}}
.sub{{font:700 12px monospace;letter-spacing:4px;color:#25c9ed;margin:9px 0 15px;text-align:left;text-transform:uppercase}}
.award{{position:relative;border:1px solid {accent};border-left:4px solid {accent};padding:11px 17px;margin-bottom:13px;background:linear-gradient(100deg,#10243b,#0c1728);box-shadow:0 0 18px {accent}22;overflow:hidden}}.award:after{{content:"";position:absolute;right:-60px;top:-70px;width:220px;height:220px;border:1px solid {accent}55;transform:rotate(45deg)}}
.label{{font:700 11px monospace;letter-spacing:3px;color:{accent};text-transform:uppercase}}.award h2{{font-size:30px;letter-spacing:1px;margin:4px 0 1px}}.award p{{font:13px monospace;margin:0;color:#a6c0d2}}
.cols,.row{{display:grid;grid-template-columns:50px 1fr 128px 96px 82px 82px;gap:8px;align-items:center}}.cols{{padding:0 12px 4px;color:#4e7894;font:700 10px monospace;letter-spacing:2px;text-transform:uppercase}}
.row{{background:rgba(14,31,53,.94);border:1px solid #1b3c5b;border-left:3px solid {accent}cc;border-radius:4px;padding:5px 10px;margin:4px 0;box-shadow:inset 0 0 18px rgba(30,170,230,.05)}}.row:hover{{border-color:{accent}}}.rank{{font:700 18px monospace;color:{accent};text-align:center;border-right:1px solid #244965;padding-right:7px}}.rank small{{display:block;font:7px monospace;color:#52758d;letter-spacing:1px;margin-top:2px}}
.who{{display:grid;grid-template-columns:60px minmax(170px,1fr) 210px;gap:10px;align-items:center;min-width:0}}.who b{{display:block;font-size:20px;letter-spacing:-.4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.headshot{{width:58px;height:58px;object-fit:cover;border-radius:50%;background:#1d3150;border:1px solid {accent}99;box-shadow:0 0 12px {accent}33}}.headshot.placeholder{{background:linear-gradient(135deg,#162c47,#0a1627)}}.who .team{{display:inline-block;color:#07111e;background:{accent};border-radius:2px;padding:1px 5px;font:700 10px monospace;margin-top:3px}}.details{{min-width:0;border-left:1px solid #244965;padding-left:10px}}.details small{{display:block;color:#b4ccda;font:13px monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.details em{{display:block;color:#52758d;font:9px monospace;font-style:normal;margin-top:4px;letter-spacing:.3px;white-space:nowrap}}
.score{{color:{accent};font:800 31px monospace;text-align:center;text-shadow:0 0 15px {accent}55}}.score small,.stat small{{display:block;font:8px monospace;color:#7394aa;letter-spacing:1px}}.stat{{position:relative;z-index:1;background:#132b47;border:1px solid #1d4564;border-radius:3px;text-align:center;padding:5px 2px;font:700 16px monospace;overflow:visible;isolation:isolate}}.stat.hot{{border:2px solid #ffad32;box-shadow:0 0 5px #ffb000,0 0 15px #ff4b1f99;color:#fff8dd;background:linear-gradient(180deg,#5b2417,#261925)}}.stat.hot:before{{content:"";position:absolute;z-index:-1;left:-8px;right:-8px;top:-15px;bottom:-9px;background:linear-gradient(150deg,#ffd45a 0 10%,transparent 11% 22%,#ff7a18 23% 35%,transparent 36% 49%,#ff3219 50% 64%,transparent 65% 78%,#ff9b20 79% 90%,transparent 91%);clip-path:polygon(0 100%,3% 54%,16% 68%,18% 20%,29% 52%,42% 0,53% 49%,66% 14%,75% 53%,89% 5%,94% 59%,100% 35%,100% 100%);filter:drop-shadow(0 0 8px #ff4b1f);pointer-events:none}}.stat.hot:after{{content:"";position:absolute;inset:2px;border:1px solid #ffd36b99;background:linear-gradient(180deg,transparent,#ff5a1a33);pointer-events:none}}.stat.cold{{border:2px solid #b9fbff;box-shadow:0 0 6px #b9fbff,0 0 18px #28cfff99;color:#edffff;background:linear-gradient(135deg,#d8ffff 0 4%,#3caed2 6% 12%,#153b5b 13% 82%,#0a223b 83%)}}.stat.cold:before{{content:"";position:absolute;z-index:-1;inset:-7px;background:linear-gradient(135deg,#dfffff,#55e9ff 20%,#135b88 48%,#a9f8ff 72%,#1b719c);clip-path:polygon(0 8%,18% 15%,28% 0,43% 13%,59% 3%,74% 17%,100% 7%,88% 31%,100% 50%,87% 66%,100% 93%,76% 84%,63% 100%,48% 87%,28% 100%,19% 85%,0 94%,11% 69%,0 51%,12% 32%);filter:drop-shadow(0 0 7px #46eaff);pointer-events:none}}.stat.cold:after{{content:"";position:absolute;inset:2px;background:linear-gradient(125deg,transparent 27%,#e7ffff99 28% 31%,transparent 32% 56%,#bdfaff77 57% 60%,transparent 61%);pointer-events:none}}.stat span{{position:relative;z-index:1}}.stat small{{position:relative;z-index:1}}.stat:not(.hot):not(.cold) span{{color:#e9f4fb}}.stat:not(.hot):not(.cold){{color:#fff}}
.section{{border:1px solid #1c6682;border-radius:4px;margin-top:13px;padding:9px;background:rgba(5,17,31,.72)}}.section h3{{color:#28d0ed;font:700 15px monospace;letter-spacing:3px;margin:0 0 6px}}.mention{{display:grid;grid-template-columns:38px 1fr 60px;align-items:center;border-top:1px solid #17354e;padding:5px 4px;color:#a8c0d1;font:12px monospace}}.mention b{{color:#5e839a}}.mention i{{font-style:normal;color:#66869a}}.mention strong{{color:{accent};text-align:right;font:700 17px monospace}}
footer{{margin-top:13px;text-align:center;color:#52758d;font:9px monospace;letter-spacing:1px}}
.stat.hot{{border:1px solid #ff7d35;box-shadow:0 0 8px #ff712255;color:#fff4da;background:linear-gradient(180deg,#20243a,#301d25 55%,#4d211d)}}.stat.hot:before{{content:"";position:absolute;z-index:-1;inset:-13px -10px -10px;background:radial-gradient(ellipse at 50% 100%,#ffbd3b 0,#ff5b20 24%,#d82724 45%,transparent 72%);filter:blur(10px);opacity:.8;clip-path:none;border-radius:45% 45% 28% 28% / 70% 70% 25% 25%;transform:scaleY(1.15)}}.stat.hot:after{{content:"";position:absolute;z-index:0;inset:2px;border:1px solid #ffbd5b66;background:linear-gradient(180deg,transparent 35%,#ff542211);clip-path:none;pointer-events:none}}
.stat.cold{{border:1px solid #8cefff;box-shadow:0 0 8px #59dfff44;color:#eaffff;background:linear-gradient(135deg,#173a5a,#102b47 55%,#0c1c35)}}.stat.cold:before{{content:"";position:absolute;z-index:-1;inset:-9px;background:radial-gradient(ellipse at 50% 50%,#bdfaff 0,#48d8f5 24%,#1680b0 49%,transparent 75%);filter:blur(9px);opacity:.38;clip-path:none;border-radius:12px}}.stat.cold:after{{content:"";position:absolute;z-index:0;inset:2px;border:1px solid #c9fbff66;background:linear-gradient(135deg,#dfffff0d,transparent 45%,#55ddff12);clip-path:none;pointer-events:none}}
</style></head><body><div id="card"><div class="brand"><span class="feed">BBL // LIVE DATA FEED</span>{f'<img src="{logo}" alt="BBL Bombastic Basketball League" />' if logo else ''}</div><h1><em>{"TOP 10 WORST" if worst else "TOP 10"}</em> PERFORMANCE{"S" if not worst else "S"}</h1><div class="sub">BBL // NIGHTLY REPORT · {html.escape(subtitle)}</div>
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
