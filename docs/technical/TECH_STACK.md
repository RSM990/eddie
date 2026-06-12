# eddie — Tech Stack

**Last Updated:** June 11, 2026

| Tool | Purpose |
|------|---------|
| Python 3.x | Language |
| pydantic + pydantic-settings | Stage contracts + env-based config |
| SQLAlchemy 2.0 | DB access (table reflection + writes) |
| pyodbc (`msodbcsql18`) | SQL Server / Azure SQL driver (TheWAC v2). psycopg2 available for Postgres consumers. |
| scraping API (ScraperAPI/ZenRows/ScrapingBee) | Default PFR fetch in `api` mode — vendor browser + residential IPs solve Cloudflare (DEC-005) |
| selenium (+ undetected-chromedriver) | PFR fetch in `browser` mode — real/attached Chrome for local dev; fallback only |
| cloudscraper | Legacy; no longer passes PFR's Cloudflare challenge. Still used by not-yet-retargeted Phase 7 extractors |
| beautifulsoup4 / lxml | HTML parsing |
| pytest | Tests (DB-touching tests run against a local v2 DB) |
| python-dotenv | `.env` loading |
| ruff + black | Lint/format |

## Notes

- `db_url` for TheWAC v2: `mssql+pyodbc://…`. Confirm the ODBC driver is installed on the dev machine.
- Secrets live in `.env` (gitignored), never in source.
