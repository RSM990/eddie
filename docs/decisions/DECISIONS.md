# eddie — Architecture Decision Records

**Last Updated:** June 5, 2026

These mirror, from eddie's side, the decisions recorded in TheWAC (`decisions/DECISIONS.md` DEC-012/DEC-013).

---

## DEC-001: ETL Stage Separation (Extractor / Transformer / Loader)

**Status:** Active

**Decision:** eddie is structured as three stages — extractors (fetch + parse source HTML → pydantic models), transformers (normalize → loader-ready models), loaders (write to a consumer DB under a per-consumer namespace). Shared pydantic contracts live in `src/models/`.

**Reasoning:** Keeps the consumer-agnostic work (scraping, normalization) cleanly separated from consumer-specific mapping. Adding a consumer is a new `loaders/<consumer>/`; changing a source touches only its extractor/transformer.

**Consequences:** Extractors/transformers must not import consumer schema. All consumer coupling is isolated to loaders.

---

## DEC-002: Generalized ETL, Not Embedded in a Consumer

**Status:** Active

**Decision:** eddie is a standalone repo/service, not code inside TheWAC. It is built to serve multiple consumers (TheWAC now, a sports-betting AI later).

**Reasoning:** Sports data is shared infrastructure. Embedding it in TheWAC (e.g. as .NET/Hangfire jobs) would couple it to one consumer and prevent reuse. (This is the eddie-side of TheWAC's DEC-012.)

**Consequences:** Python stays the implementation language; eddie is deployed/scheduled independently of any consumer.

---

## DEC-003: Writes Shared Tables Directly via a Scoped Login (for now)

**Status:** Active

**Decision:** eddie writes a consumer's *shared* tables directly. For TheWAC: `Player`, `NFLTeam`, `NFLSchedule`, `PlayerStatLine`, under a dedicated `eddie_etl` login with no access to league-scoped tables.

**Reasoning:** Shared tables carry no consumer business invariants, so direct writes are safe when the boundary is enforced by DB permissions. Simplest path that respects the boundary.

**Future update (flagged):** replace direct writes with a consumer-provided ingestion API when eddie is fully extracted as its own service or a second consumer shares the data plane.

---

## DEC-004: Team Defense Retired Upstream (IDP-only)

**Status:** Active (mirrors TheWAC DEC-013)

**Decision:** Going forward eddie ingests individual defensive-player (IDP) stats, not team-defense aggregates. Historical team-defense data already in consumers is untouched.

**Consequences:** Phase 7 box-score work must extract individual IDP stats (the legacy scraper only did team defense).

---

## DEC-005: Fetch Cloudflare-gated PFR via a Scraping API (cloud), Browser (local)

**Status:** Active

**Decision:** For unattended/cloud runs eddie fetches PFR through a **scraping API** (ScraperAPI / ZenRows / ScrapingBee — provider is config). Local dev keeps a **real-browser** path (`SeleniumFetcher`, attach to Chrome via `CHROME_DEBUGGER_ADDRESS`). `fetch_mode` (`api` | `browser`) selects between them; extractors call `get_pfr_fetcher(settings)` and are agnostic.

**Reasoning:** PFR fronts pages with a Cloudflare *managed JS challenge*. requests/cloudscraper get 403; headless Selenium is detected; undetected-chromedriver breaks on Chrome-version drift. The real blocker is **IP reputation** — Azure/GitHub datacenter IPs get challenged regardless of browser quality — so any cloud-native option must solve IP + browser + the ongoing arms race. A scraping API (vendor browser behind residential IPs) solves all three, is the lowest-maintenance, and lets the container ship **without a browser**. Volume is tiny (~hundreds of small pages per run, infrequent), so per-request cost is negligible.

**Consequences:** New config: `fetch_mode`, `scraper_provider`, `scraper_api_key`, `scraper_render_js`, `scraper_timeout`. Container is browser-free (`Dockerfile`, API mode default). Selenium/undetected-chromedriver stay as the local fallback only. Phase 7 (weekly stats/injuries) inherits the same fetch layer — adopting API there means those extractors can drop cloudscraper too. Rejected: FlareSolverr / DIY xvfb+proxy (still fight the datacenter-IP problem, higher maintenance).
