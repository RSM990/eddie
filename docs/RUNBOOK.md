# eddie — Runbook (setup & run)

Everything needed to set up the environment and run the loaders **locally**, plus
the gotchas we already hit so you never have to rediscover them. For the *why*
behind any of this, see `CLAUDE.md`, `docs/current/CURRENT_STATUS.md`, and
`docs/decisions/DECISIONS.md` (esp. DEC-005). Secrets live in `.env` — this guide
never repeats them.

---

## TL;DR — a normal local run

```bash
# once per machine: venv + deps
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# each working session: activate, launch a real Chrome (for Cloudflare), point eddie at it
source venv/bin/activate
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir="$HOME/.eddie-chrome" &
export CHROME_DEBUGGER_ADDRESS=127.0.0.1:9222

# verify with a dry run (no DB writes), then run for real
python src/etl/main.py players --season 2025 --max-teams 1 --dry-run
python src/etl/main.py players --season 2025            # full league, commits
python src/etl/main.py draft   --season 2026            # rookie class, commits
```

`.env` is already set to `FETCH_MODE=browser`, so local runs use that attached
Chrome. **Commands COMMIT by default; add `--dry-run` to scrape + load then roll
back.** If a run reports a Cloudflare "Just a moment…" page, open the target URL
once in the Chrome window that launched (it solves the challenge, then re-run).

---

## 1. One-time setup

**Prerequisites**
- Python 3.9+ (the venv in-repo is 3.9).
- The local **v2 SQL Server** running and migrated (TheWAC `TheWAC_v2`, e.g. Azure SQL Edge at `localhost,1433`).
- **ODBC Driver 17 or 18 for SQL Server** installed (`odbcinst -q -d` to list; Driver 17 is what the local `.env` uses).
- **Google Chrome** installed (for local `browser` fetch mode).

**Install**
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

**Configure `.env`** (copy from `.env.example`, never commit it). Required keys:
- `DB_URL` — `mssql+pyodbc://eddie_etl:<pw>@localhost:1433/TheWAC_v2?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes`
  - ⚠️ **URL-encode special chars in the password** or SQLAlchemy mis-parses the host. e.g. `@`→`%40`, `!`→`%21`, `:`→`%3A`. (We hit exactly this.)
- `ID_NAMESPACE` — the fixed UUID for `uuid5` player Guids. **Never change it** (it re-IDs every future rookie).
- `FETCH_MODE=browser` — local; use the attached Chrome. (Default is `api` for cloud.)

**Create the scoped DB login** (once, as `sa`): edit the password placeholder in
`scripts/eddie_etl.sql`, then run it. It grants `eddie_etl` read/write on the four
shared tables only and denies league-scoped tables.
```bash
sqlcmd -S localhost,1433 -U sa -P '<sa-password>' -C -i scripts/eddie_etl.sql
```

---

## 2. The local v2 database

- eddie connects as **`eddie_etl`** (scoped), not `sa`. It can read/write only
  `Players`, `NFLTeams`, `PlayerStatLines`, `NFLSchedule`; any league-scoped write
  is denied by design.
- Quick connectivity + boundary check:
```bash
pytest tests/test_eddie_etl_boundary.py -q
```
  Green = connected as `eddie_etl`, shared tables writable, league tables denied.
  If it **skips**, the DB isn't reachable — start/migrate the local v2 DB.

---

## 3. Running tests

```bash
pytest            # from repo root; pytest.ini sets pythonpath=src + testpaths=tests
```
- DB-touching tests run against the local v2 DB and **always roll back** (the
  scoped login has no DELETE, so rollback — not cleanup — keeps data clean). No
  test rows are ever left behind.
- If the DB is down, DB tests **skip** (don't fail); pure-logic tests still run.
- No PFR/network is hit by the suite.

---

## 4. Local runs — `browser` mode (the working path)

PFR is behind a Cloudflare **managed JS challenge**. `requests`/`cloudscraper`
get 403, plain headless Selenium is detected, and `undetected-chromedriver`
crashes on current Chrome. **The path that works is attaching to a real Chrome
you launch yourself:**

```bash
# 1) launch a dedicated Chrome with remote debugging (own profile dir, keep it open)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir="$HOME/.eddie-chrome" &

# 2) tell eddie to attach to it
export CHROME_DEBUGGER_ADDRESS=127.0.0.1:9222
```
Then run any CLI command (Section 5). The first PFR navigation may show
"Just a moment…"; the real browser clears it and the `cf_clearance` cookie is
reused for the rest of the run. If a command fails on the challenge, open the
URL once manually in that Chrome window and re-run.

> Without `CHROME_DEBUGGER_ADDRESS`, browser mode falls back to
> undetected-chromedriver, which currently crashes on new Chrome — so **always
> set it** for local runs.

---

## 5. CLI reference

Run either way (identical):
```bash
python src/etl/main.py <command> [flags]          # no env var needed
PYTHONPATH=src python -m etl.main <command> [flags]
```

**`draft` — load a rookie class** (resets all rookie flags, then loads, in one
transaction):
```bash
python src/etl/main.py draft --season 2026
python src/etl/main.py draft --season 2026 --dry-run      # verify, no writes
python src/etl/main.py draft --season 2026 --limit 32     # only first 32 picks (smoke)
```

**`players` — refresh the player universe from team rosters** (per-team
clear+upsert; players off all rosters get `NFLTeamId` NULL):
```bash
python src/etl/main.py players --season 2025
python src/etl/main.py players --season 2025 --dry-run
python src/etl/main.py players --season 2025 --max-teams 1   # one team (smoke)
python src/etl/main.py players --season 2025 --teams 9,17,22 # specific team ids (1-32)
```

Flags: `--dry-run` rolls back instead of committing; `--limit N` (draft) and
`--max-teams N` / `--teams …` (players) scope a smoke run. **No flag = commit.**

Use the season whose data you want as "current" (e.g. 2025 rosters if the new
season's aren't posted yet; the draft year for `draft`). Re-runs are idempotent
(same Guids), so running again after PFR fills in data just updates rows.

---

## 6. Diagnostics (when a scrape misbehaves)

```bash
PYTHONPATH=src python scripts/diag_pfr.py --season 2026       # try several HTTP methods, print status codes
PYTHONPATH=src python scripts/diag_selenium.py --season 2026  # render in Chrome, report challenge vs real page
```
`diag_selenium.py` saves the rendered HTML to `/tmp/pfr_draft.html` and tells you
whether you're seeing a Cloudflare challenge, an IP block, or the real page.

---

## 7. `api` mode (future / Azure)

For unattended/cloud runs, switch to the scraping API (no browser needed):
```bash
# in .env (or as env/secrets in the container)
FETCH_MODE=api
SCRAPER_PROVIDER=scraperapi        # or zenrows | scrapingbee
SCRAPER_API_KEY=<your key>
```
Validate before relying on it:
```bash
FETCH_MODE=api python src/etl/main.py players --season 2025 --max-teams 1 --dry-run
```
The container image (`Dockerfile`) is browser-free, defaults to `api`, and bundles
`msodbcsql18` (use `ODBC Driver 18` in the container's `DB_URL`). Provider request
shapes live in `etl/utils/scraper_client.py::_build_request` — if a param name is
off on the first real call, it's a one-line fix there.

---

## 8. Troubleshooting (things we already hit)

| Symptom | Cause / fix |
|---|---|
| `403 Forbidden` on every PFR URL incl. homepage | IP-level Cloudflare block. Try a different network (phone hotspot) or wait; or use `browser` mode with attached Chrome. |
| `Just a moment…` / 0 tables found | Cloudflare challenge not cleared. In `browser` mode, ensure Chrome was launched with `--remote-debugging-port` and `CHROME_DEBUGGER_ADDRESS` is exported; open the URL once in that window. |
| `NoSuchWindowException` / `target window already closed` | undetected-chromedriver vs new Chrome. Use attach mode (set `CHROME_DEBUGGER_ADDRESS`), don't rely on uc. |
| SQLAlchemy parses a wrong host from `DB_URL` | Unencoded special char in the password. URL-encode it (`@`→`%40`, `!`→`%21`, …). |
| `pyodbc` can't find the driver | Driver name in `DB_URL` must match an installed driver (`odbcinst -q -d`). Local = 17, container = 18. |
| Boundary/loader tests **skip** | Local v2 DB not reachable — start/migrate it. |
| `scraper_api_key is required` | `FETCH_MODE=api` without a key. Set `SCRAPER_API_KEY`, or use `FETCH_MODE=browser` locally. |
| DOB shows `1900-01-01`, blank height/college | PFR hadn't populated the player page yet (sentinel/empty). Not a bug; a later idempotent re-run backfills it. |

---

## 9. Safety notes

- eddie **only** writes the four shared tables, enforced by the `eddie_etl` login.
  A denied write is the boundary working — don't route around it.
- `draft` and `players` **commit by default**; use `--dry-run` to preview.
- `draft` resets all rookie flags and loads the new class **atomically** (one
  transaction) — a mid-run failure can't strand the prior class wiped.
- eddie **never** writes `Player.Retired` (retirement is a separate signal; see
  `docs/current/CURRENT_STATUS.md` and the retirement-detection memory).
