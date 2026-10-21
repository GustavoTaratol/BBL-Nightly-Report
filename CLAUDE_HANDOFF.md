# Claude handoff notes

## Project intent

This is a daily fantasy basketball report generator for a CBS BBL league. It
uses ESPN box scores, CBS ownership/position data, BBL scoring, and image
rendering to produce reports and social-friendly exports.

## Important constraint

CBS has declined to provide an API. The intended unattended integration is a
persistent Playwright browser profile that reads the same CBS pages currently
read by `rosters/export_rosters.js`. Do not ask for or hard-code a CBS password.

## Safe implementation order

1. Port the bookmarklet extraction logic into a Playwright collector.
2. Add roster validation and last-known-good snapshot handling.
3. Add a scheduler that polls ESPN until every scheduled game is final.
4. Refactor output paths so all artifacts go under `data/reports/<date>/`.
5. Add social templates and caption/alt-text files.
6. Package the service for TrueNAS SCALE/container deployment.
7. Add delivery integrations only after local output is verified.

## Verification requirements

Every change should be tested with:

```bash
python3 tests/test_fetch_box.py
python3 bbl/run.py --demo --no-open
```

When browser automation is changed, also test:

- logged-in CBS session;
- expired session;
- zero teams found;
- partial page/network failure;
- successful scrape followed by failed scrape;
- roster names with accents, apostrophes, hyphens, and suffixes.
