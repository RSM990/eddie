-- eddie_etl.sql
-- Creates a least-privilege SQL login/user for eddie's ingestion.
-- eddie may read/write ONLY the four shared tables. It has NO access to any
-- league-scoped table (LeaguePlayers, Contracts, Teams, etc.) — the boundary
-- from DEC-002/DEC-003 is enforced here, by permissions, not by convention.
--
-- Run as sa against the v2 instance. Replace the password before running and
-- store it in eddie's .env (never commit it).
--
--   sqlcmd -S localhost,1433 -U sa -P 'TheWAC@Dev123!' -C -i scripts/eddie_etl.sql

-- 1) Server login
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'eddie_etl')
BEGIN
    CREATE LOGIN [eddie_etl] WITH PASSWORD = N'CHANGE_ME_BEFORE_RUNNING',
        CHECK_POLICY = OFF;
END
GO

USE [TheWAC_v2];
GO

-- 2) Database user
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'eddie_etl')
BEGIN
    CREATE USER [eddie_etl] FOR LOGIN [eddie_etl];
END
GO

-- 3) Grant SELECT/INSERT/UPDATE on the four shared tables ONLY.
--    (No DELETE: loaders upsert and null-out FKs via UPDATE; they never delete.)
--    No role membership, no other grants => no access to any other table.
GRANT SELECT, INSERT, UPDATE ON OBJECT::[dbo].[Players]         TO [eddie_etl];
GRANT SELECT, INSERT, UPDATE ON OBJECT::[dbo].[NFLTeams]        TO [eddie_etl];
GRANT SELECT, INSERT, UPDATE ON OBJECT::[dbo].[PlayerStatLines] TO [eddie_etl];
GRANT SELECT, INSERT, UPDATE ON OBJECT::[dbo].[NFLSchedule]     TO [eddie_etl];
GO

-- 4) Belt-and-suspenders: explicitly deny on a couple of representative
--    league-scoped tables. (Not strictly needed — absence of GRANT already
--    denies — but makes the intent unmistakable and survives future role grants.)
DENY SELECT, INSERT, UPDATE, DELETE ON OBJECT::[dbo].[LeaguePlayers] TO [eddie_etl];
DENY SELECT, INSERT, UPDATE, DELETE ON OBJECT::[dbo].[Contracts]     TO [eddie_etl];
GO

-- Smoke test (run as eddie_etl): SELECT on Players succeeds; any write to
-- Contracts/LeaguePlayers is denied.
