# eddie — Architecture

**Last Updated:** June 5, 2026

See `decisions/DECISIONS.md` for the rationale.

## ETL pipeline

```
source (PFR, …) → extractor → transformer → loader → consumer DB
```

- **Extractors** (`src/etl/extractors/`, PFR under `pfr/`): fetch + parse source HTML into pydantic models. Own the HTTP concern (fetch via `get_pfr_fetcher` + rate limiting; see HTTP below). Consumer-agnostic.
- **Transformers** (`src/etl/transformers/`): normalize/clean extractor output into loader-ready models (e.g. position normalization, IDP handling). Consumer-agnostic.
- **Loaders** (`src/etl/loaders/<consumer>/`): map normalized models to a consumer's schema and upsert. The *only* place consumer-specific knowledge lives. TheWAC's loaders are under `loaders/wac/`.
- **Models** (`src/models/`): pydantic contracts shared across stages (`schemas.py`, `stats.py`).
- **Config** (`src/etl/config.py`): pydantic-settings; env/.env only.

## Boundaries

- Extractors/transformers must not import consumer schema or business rules.
- Loaders write a consumer's **shared** data only. For TheWAC, enforced by the scoped `eddie_etl` DB login.
- IDs resolved by natural key (`ProReferenceKey`, `NFLTeam.ExternalId`); new players get `uuid5(namespace, ProReferenceKey)`.

## HTTP

PFR is Cloudflare-gated (managed JS challenge) — `cloudscraper`/headless no longer pass it. All PFR fetches go through `get_pfr_fetcher(settings)` (`etl/utils/fetcher.py`), which honors `fetch_mode`: `api` (scraping API — default, cloud) or `browser` (real/attached Chrome — local), both behind a `get_soup(url, wait_for_id)` interface, with a shared rate limiter (≈18 req/min). See DEC-005.

## Scheduling (target)

Each load is a CLI subcommand; the recurring runner is a container on a schedule (Azure Container Apps Job or scheduled GitHub Action), not a manual invocation.
