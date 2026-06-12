# eddie — Current Status

**Last Updated:** June 11, 2026

## Where we are

**Phase 4.75 — eddie → v2 Data Ingestion: draft-critical scope COMPLETE** (see `planning/CURRENT_SPRINT.md`). The WAC rookie/draft and roster/player-refresh loaders now write the **v2** schema (Guid PKs) under the scoped `eddie_etl` login, driven by a real subcommand CLI. Runs locally today; Azure deployment is deferred. 47 pytest tests green.

## What works today

- **CLI:** `python src/etl/main.py draft|players --season YYYY` (or `PYTHONPATH=src python -m etl.main …`). Commits by default; `--dry-run` rolls back.
- **Draft loader (Sprint 2):** rookies upserted into v2 `Players` with deterministic `uuid5` Guid PKs, int→Guid team resolution, IDP `DefensivePosition`, shared-fields-only, idempotent. Reset-rookie-flags + load is atomic. Live 2026 class loaded.
- **Roster / player refresh (Sprint 3):** per-team clear+upsert of team/position/jersey/injury; players off all rosters get `NFLTeamId` NULL (unrostered). Never writes `Retired`.
- **Scoped write boundary (Sprint 1):** `eddie_etl` reads/writes the four shared tables, denied on league-scoped tables — enforced at the DB and tested.
- **Fetch strategy (Sprint 4b / DEC-005):** Cloudflare-gated PFR fetched via `get_pfr_fetcher(settings)` — scraping API (`fetch_mode=api`, default, cloud) or real/attached Chrome (`fetch_mode=browser`, local). cloudscraper/headless no longer pass the challenge.
- **Container:** browser-free `Dockerfile` (API mode + msodbcsql18) ready for Azure.

## What's deferred (not Phase 4.75)

- **Azure deployment** — `Dockerfile` + DEC-005 ready; vendor signup + Container Apps Job (cron, secrets via env) is later. Local browser mode covers the interim.
- **Phase 7 loaders** — box-score / season-stat / projection / **injury** (dedicated injury sync, separate from roster name-tag parsing). Still on the old cloudscraper path; need the `get_pfr_fetcher` retarget when picked up.
- **Retirement-detection loader** — separate PFR signal (players-index bold link = active vs not + career end dates) plus manual TheWAC admin override; never inferred from roster absence. Blocked on `Player.Retired` (DEC-014).

## Known follow-ups

- Cross-repo: `Player.Retired` (DEC-014) must land in TheWAC before any retirement population.
- Before Azure deploy: pick a scraping vendor and live-validate `fetch_mode=api` (provider param names confirmed on the first real call).
- Once api mode is proven end-to-end, drop Selenium / undetected-chromedriver.
- Rotate the legacy committed credentials in the old `TheWAC_Data` scraper (separate repo).
