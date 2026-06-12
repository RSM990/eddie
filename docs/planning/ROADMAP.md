# eddie — Roadmap

**Last Updated:** June 5, 2026

## Now

**Phase 4.75 — v2 Data Ingestion (Draft Unblock).** Retarget WAC loaders to the v2 shared schema; draft-critical rookie + roster loaders; scoped DB login; CLI + containerize + schedule. See `planning/CURRENT_SPRINT.md`.

## Next (aligned with TheWAC Phase 7 — Scoring + Season)

- Retarget box-score / weekly stat loader → v2 `PlayerStatLine`, **with individual IDP stat extraction** (team defense retired, TheWAC DEC-013).
- Retarget season-stats + projections loaders.
- Injury sync as a recurring scheduled job.

## Later

- Second consumer (sports-betting AI) gets its own `loaders/<consumer>/` namespace.
- Evaluate a paid sports-data API as an alternative/supplement to scraping (swappable behind extractors).
- Possible move from direct DB writes to a consumer ingestion API (TheWAC DEC-012 future update).
