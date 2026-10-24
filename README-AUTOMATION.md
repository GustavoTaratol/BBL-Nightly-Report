# BBL Best & Worst — automation handoff

This repository is being prepared to run unattended on a TrueNAS system.

## Target daily flow

```text
CBS browser session → roster snapshot
ESPN public feed     → completed box scores
                    ↓
              scoring + rankings
                    ↓
        HTML / PNG / text / captions
                    ↓
       archive + optional social delivery
```

The ESPN side does not require an account or API key. CBS does not provide an
API for this league, so roster collection will use a persistent Playwright
browser profile. The CBS login remains on the machine running the collector;
credentials are not placed in this repository.

For this league, the configured CBS root is:

```text
https://bblbombasticbaketballleague.basketball.cbssports.com
```

The `/home` path is intentionally omitted because the collector navigates to
several CBS paths itself.

## Separate identities

The CBS account and the publishing account should be separate:

- **CBS service account:** a league member with permission to view all team
  rosters. It is used only by the browser collector.
- **Publishing bot/account:** an account or webhook belonging to the target
  group-chat platform. It is used only to deliver finished reports.

A CBS account cannot directly post into an unrelated group chat. The dummy CBS
account must be invited to this league and able to view the same pages as the
commissioner. For publishing, a supported bot or webhook is preferable to
automating a personal chat account.

Discord and Slack are the easiest destinations. WhatsApp, Facebook Messenger,
and some private group chats may not provide a supported bot interface; browser
automation there is fragile and may violate platform rules. In those cases the
system can still generate the complete image, caption, and text package for a
human or approved integration to send.

## Persistent data layout

The deployment should mount a persistent data directory with this structure:

```text
data/
  rosters/current.txt
  rosters/snapshots/YYYYMMDD-HHMMSS.txt
  boxscores/YYYYMMDD.txt
  reports/YYYYMMDD/
    Best & Worst.html
    Best & Worst.png
    Best & Worst - Full Table.html
    Best & Worst - Full Table.png
    Top 10 - Mobile Friendly.png
    Best & Worst - Text.txt
    caption.txt
    alt-text.txt
  browser/cbs-profile/
  logs/
```

The browser profile and generated data are runtime state. They must not be
committed or copied into public repositories.

## One-time setup on the host

1. Copy the repository and `.env.example` to the deployment directory.
2. Create a persistent `data` directory and make it writable by the service.
3. Start the CBS browser collector in interactive mode.
4. Log into CBS once and complete any MFA/CAPTCHA challenge.
5. Run a roster test and confirm that teams, owners, positions, and logos are
   found.
6. Run the offline demo and inspect every social export format.
7. Enable the scheduled nightly job.

## Local Mac setup

For this Mac deployment:

```text
1. Double-click setup-mac.command
2. Double-click login-cbs.command and sign into CBS in the visible browser
3. Double-click run-scheduled.command to test one complete run
4. Install the launchd plist after the test succeeds
```

The provided schedule is 11:30 PM every night in the Mac's local timezone.
The plist must be copied to `~/Library/LaunchAgents/` after replacing
`/REPLACE_WITH_REPO_PATH` with the absolute repository path.

The scheduler writes `data/completed/YYYYMMDD.ok` only after report generation
and publishing succeed. This prevents an hourly long-running process from
posting the same night repeatedly. Use `--force` when deliberately rebuilding
and republishing a date.

If the CBS session expires, the collector should stop with an actionable error
and preserve the last known roster snapshot. It must never silently replace a
good snapshot with an empty roster.

## Current status

- ESPN fetch and BBL scoring: existing and tested with sample data.
- HTML/text report generation: existing and tested with sample data.
- PNG rendering: existing; requires Playwright and Chromium.
- CBS roster collection: `bbl/cbs_rosters.py` now provides the persistent
  Playwright collector; it still needs a live logged-in CBS test.
- Scheduling, persistence, social delivery, and TrueNAS packaging: pending.

## Handoff rule

Claude or another maintainer may update selectors and deployment code, but must
keep these boundaries intact:

- No credentials in source files, logs, fixtures, or commits.
- No destructive cleanup of roster snapshots or reports by default.
- A failed CBS scrape must not erase the last successful roster.
- A report must not publish while ESPN games are still incomplete unless an
  explicit partial-report mode is selected.
