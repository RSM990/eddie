# V2 Schema Contract (TheWAC shared tables)

**Last Updated:** June 5, 2026
**Source of truth:** TheWAC `src/TheWAC.Domain/Entities/*` + EF configurations. This doc mirrors them for eddie so eddie is self-contained. If TheWAC changes a shared table, update this doc and the affected loader in the same change.

eddie writes **only** these shared (non-league-scoped) tables. All have **Guid** primary keys (`Id`) except `PlayerStatLines` (composite key). eddie has no access to league-scoped tables.

## Connection (local dev)

```
Server:   localhost,1433
Database: TheWAC_v2
SA login: sa / TheWAC@Dev123!   (dev only — eddie uses the scoped eddie_etl login, see scripts/eddie_etl.sql)
SQLAlchemy db_url: mssql+pyodbc://eddie_etl:<pw>@localhost:1433/TheWAC_v2?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

## Table names (entity → table)

| Entity | **Table** | Notes |
|---|---|---|
| `Player` | **`Players`** | plural |
| `NFLTeam` | **`NFLTeams`** | plural |
| `PlayerStatLine` | **`PlayerStatLines`** | plural; composite key |
| `NFLSchedule` | **`NFLSchedule`** | **singular** — the odd one out |

---

## Players  (entity `Player`)

Shared NFL biographical data. League-specific status lives in `LeaguePlayer` (off-limits to eddie).

| Column | Type | Notes |
|---|---|---|
| `Id` | Guid (PK) | Existing rows: reuse by `ProReferenceKey` lookup. New rookies: `uuid5(NAMESPACE, ProReferenceKey)`. |
| `ProReferenceKey` | nvarchar(40) | **Natural key** for upsert/dedupe. |
| `ProReferenceURL` | nvarchar(100) | |
| `FullName` | nvarchar(250) | required |
| `FirstName` | nvarchar(100) | |
| `LastName` | nvarchar(150) | |
| `NFLTeamId` | Guid? | FK → `NFLTeams.Id`. Resolve via `NFLTeams.ExternalId`/`Abbreviation`. `null` = active free agent (not on an NFL team). |
| `JerseyNumber` | int? | parse from scraped string; null if absent |
| `Rookie` | bool | true for draft-class loads; `reset_rookie_flags` clears prior class |
| `Position` | nvarchar(10) | QB/RB/WR/TE/K/DL/LB/DB/EDGE |
| `DefensivePosition` | nvarchar(4) | IDP / two-way players |
| `College` | nvarchar(50) | |
| `DateOfBirth` | datetime | **non-null** — sentinel (e.g. 1900-01-01) if unknown |
| `Height` | nvarchar(10) | |
| `Weight` | nvarchar(10) | |
| `InjuryStatus` | nvarchar(5) | |
| `InjuryComment` | nvarchar(45) | |
| `InjuryPracticeStatus` | nvarchar(45) | |
| `Retired` | bool | **PENDING** TheWAC migration (DEC-014). eddie doesn't write it until it exists; then set by roster refresh (Sprint 3). |

**Do NOT write:** `TradingBlock`, `WeeksLeftOnIR`, `WACStatus`, `TeamId` — these live on league-scoped `LeaguePlayer`, owned by the app. (They are not columns on `Players`.)

Respect the max lengths above when writing (truncate/validate in the loader).

---

## NFLTeams  (entity `NFLTeam`)

Reference data. eddie reads this to resolve `NFLTeamId`; rarely writes it.

| Column | Type | Notes |
|---|---|---|
| `Id` | Guid (PK) | |
| `ExternalId` | int (unique) | **The v1 int team id** — map eddie's `translate_team_code_to_id` output → Guid via this. |
| `Abbreviation` | nvarchar(3) | alternative natural-key lookup |
| `Name`, `City` | nvarchar(75) | |
| stadium + jersey color columns | nvarchar | display only |

**Team resolution:** scraped code → `translate_team_code_to_id` (int) → `SELECT Id FROM NFLTeams WHERE ExternalId = :int`.

---

## NFLSchedule  *(singular table; Phase 7 — to be detailed)*

Has `Id` (Guid PK), unique `ExternalId`, `BoxscoreLink` (nvarchar 140), `HomeTeamId`/`AwayTeamId` (FK → NFLTeams). Columns transcribed in full when the games loader is retargeted in Phase 7.

---

## PlayerStatLines  *(entity `PlayerStatLine`; Phase 7 — to be detailed)*

Shared raw stats, no fantasy points. **Composite key:** (`PlayerId`, `SeasonId`, `NFLWeek`, `ProjectedStat`). `NFLWeek` 0 = season totals; `ProjectedStat` distinguishes projections from actuals. 50+ stat categories (`Sacks` is decimal(5,1)). **IDP individual stats required going forward; team defense retired** (TheWAC DEC-013). Full columns transcribed when stat/box-score loaders are retargeted in Phase 7.

---

## ID generation summary

- **Existing player:** find by `ProReferenceKey`, reuse stored `Id`.
- **New player (rookie):** `Id = uuid5(NAMESPACE, ProReferenceKey)` — deterministic, idempotent.
- **NFL team FK:** lookup by `ExternalId`, never generate.
- The migration's deterministic-UUID scheme does **not** need to be reproduced — natural-key resolution covers every case.
