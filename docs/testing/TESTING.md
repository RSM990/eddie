# eddie — Testing

**Last Updated:** June 5, 2026 (starter — expand as the suite grows)

## Approach

- **pytest** for everything.
- Loaders touch a real database, so DB tests run against a **local v2 SQL Server** (TheWAC's `thewac-sqlserver` Azure SQL Edge container), migrated. Reflection/upsert behavior can't be faked with mocks.
- Extractor/transformer tests can run offline against saved source HTML fixtures (no live PFR calls in CI).

## What to cover

- Loader: idempotent upsert (re-run = no dupes), Guid determinism (`uuid5(ProReferenceKey)`), `NFLTeam.ExternalId` resolution, shared-fields-only (no league-scoped writes), IDP rookies loaded.
- Transformer: position normalization (incl. IDP), missing-field handling (e.g. DOB sentinel).
- Boundary: writes to league-scoped tables are denied under the `eddie_etl` login.

## Conventions

- Arrange/Act/Assert. Fixtures for source HTML. No live network in CI.
