"""
Boundary test for the scoped ``eddie_etl`` SQL login (Phase 4.75, Sprint 1).

eddie must be able to read/write the four shared tables and must be DENIED on
every league-scoped table. That boundary is enforced at the DB by permissions
(see ``scripts/eddie_etl.sql``), not by convention — this test proves it holds.

Runs against the local v2 DB using the ``db_url`` from ``.env`` (the scoped
login). If the DB is unreachable, the test is skipped rather than failed, since
DB-touching tests require a running local v2 instance.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from etl.config import Settings


# Tables eddie is allowed to touch vs. the league-scoped tables it must not.
SHARED_TABLES = ["dbo.Players", "dbo.NFLTeams", "dbo.PlayerStatLines", "dbo.NFLSchedule"]
LEAGUE_SCOPED_TABLES = ["dbo.Contracts", "dbo.LeaguePlayers"]


@pytest.fixture(scope="module")
def engine():
    """Engine bound to the scoped eddie_etl login; skip if the DB is unreachable."""
    settings = Settings()
    eng = create_engine(settings.db_url)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        pytest.skip(f"v2 DB not reachable for boundary test: {exc.__class__.__name__}")
    return eng


def _has_perm(conn, table: str, perm: str) -> int:
    """HAS_PERMS_BY_NAME -> 1 (granted), 0 (denied), or None (object missing)."""
    return conn.execute(
        text("SELECT HAS_PERMS_BY_NAME(:t, 'OBJECT', :p)"),
        {"t": table, "p": perm},
    ).scalar()


def test_connected_as_eddie_etl(engine):
    """Guard: the test is meaningless unless we're actually the scoped login."""
    with engine.connect() as conn:
        login = conn.execute(text("SELECT SUSER_SNAME()")).scalar()
    assert login == "eddie_etl", f"expected eddie_etl login, got {login!r}"


def test_can_read_players(engine):
    """A real SELECT against Players proves shared-table read access works."""
    with engine.connect() as conn:
        # Should not raise; count is incidental.
        conn.execute(text("SELECT COUNT(*) FROM dbo.Players")).scalar()


@pytest.mark.parametrize("table", SHARED_TABLES)
@pytest.mark.parametrize("perm", ["SELECT", "INSERT", "UPDATE"])
def test_shared_tables_writable(engine, table, perm):
    """eddie may SELECT/INSERT/UPDATE every shared table."""
    with engine.connect() as conn:
        assert _has_perm(conn, table, perm) == 1, f"expected {perm} granted on {table}"


@pytest.mark.parametrize("table", LEAGUE_SCOPED_TABLES)
@pytest.mark.parametrize("perm", ["SELECT", "INSERT", "UPDATE", "DELETE"])
def test_league_scoped_tables_denied(engine, table, perm):
    """eddie must be denied on every league-scoped table."""
    with engine.connect() as conn:
        assert _has_perm(conn, table, perm) == 0, f"expected {perm} denied on {table}"
