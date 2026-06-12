# eddie — Vision

**Last Updated:** June 5, 2026

## What eddie is

eddie is a standalone, generalized sports-data ETL. It extracts data from sports sources (today: Pro Football Reference), normalizes it, and loads it into downstream consumers. It is deliberately **not** tied to any one consumer's domain.

## Why it exists

Sports data is general-purpose infrastructure, not a feature of one app. The same NFL player, stat, and schedule data can power very different products:

- **TheWAC** — a fantasy-football league platform (the current consumer).
- A future **sports-betting AI** — a separate product that needs the same underlying data.

Building scraping/ingestion once, cleanly, and feeding multiple consumers beats re-implementing it inside each app. eddie is that shared workhorse.

## Principles

1. **Consumer-agnostic core.** Extractors and transformers know about *sources and sports data*, not about any consumer's schema or business rules. Consumer-specific concerns live only in `loaders/<consumer>/`.
2. **Clean boundaries.** eddie writes a consumer's *shared* data and nothing else. It never reaches into a consumer's domain/business tables. For TheWAC this is enforced by a scoped DB login.
3. **Hands-off operation.** The goal is scheduled, containerized ingestion that runs and is forgotten — not a script run manually on a laptop.
4. **Resilient + idempotent.** Parsing tolerates source changes where it can; every load can be re-run safely.
5. **Swappable sources.** Scraping is the current source; a paid sports-data API could replace or supplement it without consumers noticing.

## Success looks like

- New rookies, player updates, stats, and schedules flow into consumers automatically on a schedule.
- Adding a new consumer means adding a `loaders/<consumer>/` namespace — not touching extractors/transformers.
- No manual runs, no committed secrets, no Windows/Parallels dependency.
