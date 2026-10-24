#!/usr/bin/env python3
"""Export CBS BBL rosters using a persistent Playwright browser profile.

This replaces the manual bookmarklet for unattended deployments. The first
run should be headed so the league owner can sign in once:

  python3 bbl/cbs_rosters.py --base-url https://YOUR-LEAGUE.basketball.cbssports.com \
      --profile data/browser/cbs-profile --out data/rosters/current.txt --headed

Later runs can be headless. CBS credentials are handled by the browser and
are never read or stored by this script.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


TEAM_RE = re.compile(r"/teams/(\d+)")
PLAYER_RE = re.compile(r"^(.+?)\s+([CFG](?:,[CFG])*)\s+•\s+(\w+)$")


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def page_text_rows(page):
    rows = []
    for row in page.locator("tr").all():
        cells = [clean(x) for x in row.locator("th,td").all_inner_texts()]
        if cells:
            rows.append(cells)
    return rows


def find_player(cells):
    # CBS has moved the player cell between columns over time. Search the
    # joined row first, then individual cells, matching the bookmarklet's
    # player/position/team convention.
    candidates = [" | ".join(cells)] + list(cells)
    for value in candidates:
        match = PLAYER_RE.search(value)
        if match:
            return match.groups()
    return None


def collect(base_url: str, profile: Path, out: Path, headed: bool) -> int:
    base_url = base_url.rstrip("/")
    if not re.match(r"^https://[^/]+\.basketball\.cbssports\.com$", base_url):
        raise SystemExit("--base-url must be the HTTPS CBS league hostname")

    profile.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        chrome_process = None
        keep_browser_open = False
        if not headed:
            try:
                # Prefer the already-open dedicated Chrome session. This
                # avoids profile locking and preserves the user's login.
                browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
                context = browser.contexts[0]
                keep_browser_open = True
            except Exception:
                context = None
        else:
            context = None
        if context is None and headed:
            # Launch a dedicated, ordinary Chrome window and attach through
            # CDP. Google is more likely to reject Playwright's automated
            # sign-in window than a normal Chrome session.
            chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            chrome_process = subprocess.Popen([
                chrome,
                "--remote-debugging-port=9222",
                f"--user-data-dir={profile}",
                base_url + "/standings/overall",
            ])
            browser = None
            for _ in range(30):
                try:
                    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
                    break
                except Exception:
                    time.sleep(1)
            if browser is None:
                chrome_process.terminate()
                raise RuntimeError("Could not attach to the dedicated Chrome login window")
            context = browser.contexts[0]
        elif context is None:
            context = pw.chromium.launch_persistent_context(
                str(profile),
                headless=True,
                channel="chrome",
                viewport={"width": 1440, "height": 1000},
            )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            try:
                page.goto(base_url + "/standings/overall", wait_until="domcontentloaded", timeout=45_000)
            except PlaywrightError:
                # CBS may redirect through its login service and abort the
                # original navigation while the final page is still usable.
                pass
            page.wait_for_timeout(1_000)

            teams = {}
            for link in page.locator('a[href*="/teams/"]').all():
                href = link.get_attribute("href") or ""
                match = TEAM_RE.search(href)
                name = clean(link.inner_text())
                if match and name:
                    teams.setdefault(match.group(1), name)
            if not teams and headed:
                print("CBS login required in the browser window. Complete login, then press Enter here.", flush=True)
                input()
                try:
                    page.goto(base_url + "/standings/overall", wait_until="domcontentloaded", timeout=45_000)
                except PlaywrightError:
                    pass
                page.wait_for_timeout(1_000)
                for link in page.locator('a[href*="/teams/"]').all():
                    href = link.get_attribute("href") or ""
                    match = TEAM_RE.search(href)
                    name = clean(link.inner_text())
                    if match and name:
                        teams.setdefault(match.group(1), name)
            if not teams:
                raise RuntimeError("No CBS teams found; the session may be logged out or the page layout changed")

            owners = {}
            logos = {}
            for team_id, team_name in teams.items():
                page.goto(base_url + "/teams/" + team_id, wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_timeout(300)
                for image in page.locator("img").all():
                    src = image.get_attribute("src") or ""
                    if f"/team_logo/{team_id}-" in src:
                        logos[team_name] = src.split("?", 1)[0]
                        break
                for cells in page_text_rows(page):
                    found = find_player(cells)
                    if found:
                        name, positions, nba_team = found
                        owners.setdefault(name, (team_name, positions, nba_team))

            players = {}
            for position in ("G", "F", "C"):
                url = (base_url + "/stats/stats-main/all:" + position
                       + "/restofseason:p/standard/projections?print_rows=9999")
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_timeout(500)
                for cells in page_text_rows(page):
                    found = find_player(cells)
                    if found:
                        name, positions, nba_team = found
                        players.setdefault(name, (nba_team, positions))

            # Rostered players missing from projections still need their CBS
            # eligibility, for example injured or newly added players.
            for name, (team_name, positions, nba_team) in owners.items():
                players.setdefault(name, (nba_team, positions))

            if not players:
                raise RuntimeError("CBS pages loaded but no players were extracted")

            now = dt.datetime.now(dt.timezone.utc).isoformat()
            lines = [f"# BBL rosters exported {now} from {base_url}"]
            for name, (nba_team, positions) in sorted(players.items(), key=lambda x: x[0].casefold()):
                owner = "FA"
                if name in owners:
                    owner = "TAKEN:" + owners[name][0]
                lines.append("|".join((name, nba_team, positions, owner)))
            lines.extend(f"#LOGO|{team}|{url}" for team, url in sorted(logos.items()))
            text = "\n".join(lines) + "\n"

            # Atomic replacement: an unsuccessful or interrupted run cannot
            # destroy the last known-good roster file.
            fd, temp_name = tempfile.mkstemp(prefix=".bbl-rosters-", dir=str(out.parent), text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(text)
                os.replace(temp_name, out)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            print(f"CBS: saved {len(players)} players, {len(owners)} rostered, {len(teams)} teams")
            return 0
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"CBS page timed out: {exc}") from exc
        finally:
            if not keep_browser_open:
                context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("BBL_CBS_BASE_URL"),
                        help="CBS league URL, e.g. https://league.basketball.cbssports.com")
    parser.add_argument("--profile", default="data/browser/cbs-profile")
    parser.add_argument("--out", default="data/rosters/current.txt")
    parser.add_argument("--headed", action="store_true", help="show the browser for first-time login")
    args = parser.parse_args()
    if not args.base_url:
        parser.error("--base-url or BBL_CBS_BASE_URL is required")
    try:
        return collect(args.base_url, Path(args.profile), Path(args.out), args.headed)
    except Exception as exc:
        print(f"CBS roster export failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
