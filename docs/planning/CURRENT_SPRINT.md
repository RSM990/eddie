# Current Sprint: Phase 4.75 — eddie → v2 Data Ingestion (Draft Unblock)

**Status:** 🟢 Draft-critical scope complete (Sprints 1–4), runs locally. Deferred: Azure deploy + Phase 7.
**Last Updated:** June 11, 2026

This is eddie's working copy of the Phase 4.75 plan. The canonical planning record lives in TheWAC (`docs/planning/CURRENT_SPRINT.md`); this copy is what Claude Code executes against inside eddie. See `docs/technical/V2_SCHEMA_CONTRACT.md` for the table spec and `docs/decisions/DECISIONS.md` for the architecture decisions.

---

## Goal

Retarget eddie's WAC loaders from the v1 schema to the v2 schema, and make ingestion scheduled/hands-off. By the end: current rookies + an accurate current player universe populate v2 `Player` (so TheWAC's draft pool is real), eddie writes only the shared tables via a scoped DB login, and it runs from a real CLI in a container on a schedule.

**Scope now (draft-critical):** rookie/draft loader + roster/player-refresh loader.
**Deferred to Phase 7:** box-score/season-stat/projection/injury loaders, incl. net-new individual IDP box-score stats (team defense retired — TheWAC DEC-013).

---

## Locked decisions

1. eddie stays Python, standalone, generalized (serves TheWAC + future betting AI). Not ported to .NET.
2. Direct writes to v2 shared tables via a dedicated scoped login now; ingestion API is a future update.
3. New `Player` Guids: `uuid5(NAMESPACE, ProReferenceKey)`; dedupe/upsert on `ProReferenceKey`.
4. Shared fields only — never `TradingBlock`/`WeeksLeftOnIR`/`WACStatus`/`TeamId`/`Contract`.
5. NFL team mapping via `NFLTeam.ExternalId` (or `Abbreviation`) lookup — no migration-hash replication.
6. Reuse extractors/transformers as-is. ~~Standardize HTTP on `cloudscraper`.~~ **Superseded by DEC-005:** cloudscraper no longer passes PFR's Cloudflare challenge — fetch via `get_pfr_fetcher` (`api` default / `browser` local).

---

## Sprint 1 — v2 targeting + scoped write boundary

Point eddie at the v2 DB (SQL Server / Azure SQL); update loader reflection to v2 table names. Create a `eddie_etl` SQL login with write access limited to `Player`, `NFLTeam`, `NFLSchedule`, `PlayerStatLine` (no league-scoped access). Add the `uuid5` namespace setting to config. Confirm `.env` is gitignored.

**Done when:** eddie connects under `eddie_etl`, can write `Player`, and is denied on league-scoped tables.

## Sprint 2 — Player loader retarget (DRAFT-CRITICAL)

Rewrite `loaders/wac/player_loader.py` to upsert v2 `Player`: Guid via `uuid5(namespace, ProReferenceKey)`, dedupe on `ProReferenceKey`, map int `nfl_team_id` → `NFLTeam` Guid, shared fields only, set `DefensivePosition` for IDP. Reuse `extractors/pfr/draft.py` + `transformers/nfl_draft.py`. Retarget `reset_rookie_flags`.

**Tests:** rookies inserted as Guid PKs; deterministic Guids; idempotent re-run; IDP rookies present; no league-scoped writes.
**Manual:** run current rookie class; verify defensive rookies + team resolution.

## Sprint 3 — Roster / player-refresh loader retarget

Retarget the roster path to refresh v2 `Player` (team/position/injury/jersey, IDP `DefensivePosition`; null `NFLTeamId` when unrostered). Per-team clear+upsert is atomic.

**HTTP:** standardize on the browser path, *not* cloudscraper — PFR's Cloudflare managed challenge 403s requests/cloudscraper, so the roster extractor goes through `etl/utils/selenium_client.py` (`SeleniumFetcher`, attach to a real Chrome via `CHROME_DEBUGGER_ADDRESS`), same as the draft path.

**Retired — do NOT write from the roster path.** Retirement is never inferred from roster absence (a missing player is just unrostered). It's a separate signal: PFR players-index link styling (bold = active, non-bold = retired) corroborated by career end dates, plus a manual TheWAC admin override. That detection is a **separate future loader**, gated on `Player.Retired` landing (DEC-014) — which still does not exist as of Sprint 3.

**Status (done):** roster extractor → `SeleniumFetcher`; `PlayerLoader.load`/`clear_team` already v2 (Sprint 2); the `players` subcommand (per-team clear+upsert) runs it; tests in `tests/test_roster_refresh.py` (clear_team null, unrostered null, upsert team/position/injury, injury-tag parsing, no-Retired). Live full-league run is the manual step (needs attached Chrome).

## Sprint 4 — CLI cleanup + scheduling / containerization

**Sprint 4a — CLI cleanup (done).** `main.py` is now a subcommand CLI: `draft` and `players` (run via `PYTHONPATH=src python -m etl.main <cmd>` or `python src/etl/main.py <cmd>`; commit by default, `--dry-run` to roll back). The draft command resets rookie flags + loads in a **single transaction** (the Sprint-2 carry-forward, now resolved). The Sprint-2/3 stopgap scripts (`smoke_draft.py`, `refresh_players.py`) were folded in and removed; `scripts/diag_*.py` remain for diagnostics. `games`/`stats`/`injuries` subcommands are deferred to Phase 7. Tests in `tests/test_cli.py`.

**Sprint 4b — scheduling / containerization.**

**Decision (DEC-005):** fetch via a **scraping API** on Azure, **real browser** locally. `fetch_mode` (`api`|`browser`) + `scraper_*` config select the path; extractors call `get_pfr_fetcher(settings)`. Rationale: the real blocker is IP reputation (datacenter IPs get Cloudflare-challenged regardless of browser), and a scraping API solves IP + browser + arms-race while shipping a browser-free container.

**Built:** `etl/utils/scraper_client.py` (ScraperAPI/ZenRows/ScrapingBee request shapes, `wait_for` selector), `etl/utils/fetcher.py` factory, config (`fetch_mode`/`scraper_*`), extractors/transformer repointed at the factory, browser-free `Dockerfile` (incl. msodbcsql18 for Azure SQL), `.env.example` updated, tests in `tests/test_scraper_client.py`. Local `.env` set to `FETCH_MODE=browser`.

**Remaining (needs user):** pick + sign up for a vendor, set `SCRAPER_PROVIDER`/`SCRAPER_API_KEY`, validate a live `--dry-run` in `api` mode, then stand up the Azure Container Apps Job (cron schedule, secrets as env). Once api mode is proven, Selenium/uc can be dropped entirely.

---

## Cross-repo dependency

`Player.Retired` (TheWAC migration, DEC-014) must land before Sprint 3 can populate it. Sprint 2 (rookies) has no cross-repo dependency.

## Open items / verify

- Confirm SQL Server ODBC driver (`msodbcsql18`) on the dev Mac; `db_url` = `mssql+pyodbc://…`.
- Local v2 DB (TheWAC `thewac-sqlserver` Azure SQL Edge), migrated, running, for reflection + tests.
- Confirm whether `roster.py` truly needs Selenium. **Finding (Sprint 2):** PFR now fronts the draft pages with a Cloudflare *managed JS challenge* — `requests`/`cloudscraper` get 403 and headless/undetected-chromedriver get stuck/crash (Chrome 149). The working path is attaching Selenium to a user-launched real Chrome (`CHROME_DEBUGGER_ADDRESS`, see `etl/utils/selenium_client.py`). So Sprint 3's "drop Selenium if no page truly needs it" can't be universal — at least the draft path needs a real browser; revisit standardizing on a single browser-based PFR client (and a container-friendly story, e.g. xvfb / a residential proxy / a challenge-solver service).
