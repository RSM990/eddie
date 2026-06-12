# CLAUDE.md — eddie

**eddie** is a standalone, generalized sports-data ETL. It scrapes Pro Football Reference (and other sources over time) and loads normalized data into downstream consumers. Today the consumer is **TheWAC** (a fantasy-football platform); the design intent is to also serve a future sports-betting AI, so eddie is deliberately *not* coupled to any one consumer's domain.

## Start here

1. Read `docs/planning/CURRENT_SPRINT.md` — the active work.
2. Read `docs/current/CURRENT_STATUS.md` — where things stand.
3. For anything touching the database, read `docs/technical/V2_SCHEMA_CONTRACT.md` — the authoritative spec for the tables eddie writes.
4. `docs/DOC_NAVIGATION.md` maps the rest.

## Architecture

Classic ETL, one stage per concern:

```
src/etl/extractors/   # fetch + parse raw source HTML → pydantic models (PFR under pfr/)
src/etl/transformers/ # normalize/clean extractor output → loader-ready models
src/etl/loaders/      # write to a consumer DB (per-consumer namespace, e.g. loaders/wac/)
src/models/           # pydantic contracts shared across stages (schemas.py, stats.py)
src/etl/config.py     # pydantic-settings; all config via env/.env
```

Extractors and transformers are **consumer-agnostic**. Consumer-specific mapping (table names, ID strategy, schema) lives only in `loaders/<consumer>/`.

## Hard rules (do not violate)

- **eddie writes shared sports data only.** For TheWAC that means the four shared tables: `Players`, `NFLTeams`, `PlayerStatLines`, and `NFLSchedule` (note: the first three are plural, `NFLSchedule` is singular). eddie must **never** write league-scoped tables (`LeaguePlayer`, `Contract`, `Team`, etc.). This is enforced at the DB by the scoped `eddie_etl` login — if a write is denied, that's the boundary working, not a bug to route around.
- **IDs:** resolve existing `Player` rows by `ProReferenceKey` (natural key) and reuse their Guid. For genuinely new players (rookies), generate `uuid5(NAMESPACE, ProReferenceKey)` so re-runs are idempotent. Never invent random Guids for players.
- **NFL team mapping:** map a scraped team to its v2 Guid by looking up `NFLTeam.ExternalId` (the v1 int) or `NFLTeam.Abbreviation`. Do not reproduce the migration's hashing.
- **Shared fields only on `Player`:** `Position`, `DefensivePosition`, injury fields, bio, `NFLTeamId`, `Rookie`, and `Retired` (pending the TheWAC migration). Never write `TradingBlock`/`WeeksLeftOnIR`/`WACStatus` — they don't exist on shared `Player`.
- **HTTP:** PFR is Cloudflare-gated (managed JS challenge) — `cloudscraper`/headless no longer pass it. Fetch through `get_pfr_fetcher(settings)`, which honors `fetch_mode`: `api` (scraping API, default/cloud) or `browser` (real/attached Chrome, local). New PFR extractors must use the factory, not a naive `requests`/`cloudscraper` client. Respect the rate limiter (≈18 req/min). See DEC-005.
- **Secrets:** connection strings and credentials live in `.env` (gitignored), never in source.
- **Idempotency:** every loader upserts. Running a load twice produces the same result, no duplicates.

## Running

```
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# configure .env (db_url, namespace, etc.)
# PFR is Cloudflare-gated: launch Chrome with --remote-debugging-port=9222 and
# export CHROME_DEBUGGER_ADDRESS=127.0.0.1:9222 first (see etl/utils/selenium_client.py).
PYTHONPATH=src python -m etl.main draft --season 2026     # load a rookie class
PYTHONPATH=src python -m etl.main players --season 2025    # refresh the player universe
#   add --dry-run to scrape + load then roll back (verify without writing)
#   (or run directly without the env var: python src/etl/main.py draft --season 2026)
pytest                                            # tests run against a local v2 DB
```

(The CLI subcommand form replaces the legacy boolean-toggle `main.py`. Commands commit by default; `--dry-run` rolls back. `draft`/`players` are wired now; `games`/`stats`/`injuries` come in Phase 7.)

**Full setup, exact run commands (incl. the local Chrome-attach step), and troubleshooting: `docs/RUNBOOK.md`.**

## Conventions

- Python 3.x, type hints throughout, pydantic models for stage contracts.
- `ruff` + `black` for lint/format.
- pytest; DB-touching tests run against a local v2 database (reflection can't be faked).
- One source per extractor module; keep parsing resilient (avoid brittle positional indices where a labeled lookup works).

## Cross-repo note

eddie writes the tables TheWAC reads. The contract between them is the **schema**, captured in `docs/technical/V2_SCHEMA_CONTRACT.md`. If a TheWAC schema change affects a shared table (e.g. adding `Player.Retired`), update that doc and the relevant loader together.
