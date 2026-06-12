"""
Player loader retarget tests (Phase 4.75, Sprint 2).

Asserts the v2 ``Players`` upsert contract:
  - new rookies get deterministic ``uuid5`` Guid primary keys
  - re-running is idempotent (no duplicates)
  - IDP rookies get ``DefensivePosition`` set
  - scraped int team id resolves to an ``NFLTeam`` Guid
  - the loader only ever touches the shared tables (Players, NFLTeams)

Runs against the local v2 DB. Every write happens inside a transaction that is
rolled back, so the real ``Players`` data is never mutated (the scoped login has
no DELETE grant, so rollback — not cleanup — is how we stay clean).
"""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid5

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

from etl.config import Settings
from etl.loaders.wac.player_loader import PlayerLoader
from models.schemas import RosterPlayer


def _make(key: str, position: str, nfl_team_id: int = 1, **over) -> RosterPlayer:
    base = dict(
        pro_reference_key=key,
        pro_reference_url=f"https://example.com/{key}.htm",
        full_name="Test Rookie",
        first_name="Test",
        last_name="Rookie",
        nfl_team_id=nfl_team_id,
        jersey_number=None,
        rookie=True,
        position=position,
        college=None,
        date_of_birth=None,
        height=None,
        weight=None,
    )
    base.update(over)
    return RosterPlayer(**base)


@pytest.fixture(scope="module")
def settings():
    return Settings()


@pytest.fixture(scope="module")
def loader(settings):
    try:
        eng = create_engine(settings.db_url)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        pytest.skip(f"v2 DB not reachable: {exc.__class__.__name__}")
    return PlayerLoader(settings.db_url, settings.id_namespace)


@pytest.fixture
def txn(loader):
    """A connection with an open transaction that is always rolled back."""
    conn = loader.engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()


def _row(conn, players, key):
    return conn.execute(
        select(
            players.c.Id,
            players.c.Position,
            players.c.DefensivePosition,
            players.c.NFLTeamId,
            players.c.Rookie,
            players.c.DateOfBirth,
        ).where(players.c.ProReferenceKey == key)
    ).fetchall()


def test_loader_only_reflects_shared_tables(loader):
    # No league-scoped table is ever in scope for this loader.
    assert loader.players.name == "Players"
    assert loader.nfl_teams.name == "NFLTeams"


def test_player_guid_is_deterministic(loader, settings):
    key = "zztest_det_key"
    expected = str(uuid5(settings.id_namespace, key))
    assert loader.player_guid(key) == expected
    assert loader.player_guid(key) == loader.player_guid(key)


def test_rookie_inserted_with_uuid5_pk(loader, txn):
    key = "zztest_qb_pk"
    assert key not in loader.existing_map  # not a real player

    loader.load([_make(key, "QB")], conn=txn)

    rows = _row(txn, loader.players, key)
    assert len(rows) == 1
    got_id = str(rows[0].Id).upper()
    expected = str(uuid5(loader.id_namespace, key)).upper()
    assert got_id == expected
    UUID(got_id)  # parses as a real Guid
    assert rows[0].Rookie is True
    # QB is not IDP -> no DefensivePosition
    assert rows[0].DefensivePosition is None
    # DOB sentinel applied (date_of_birth was None)
    assert rows[0].DateOfBirth.date() == date(1900, 1, 1)


def test_idp_rookie_gets_defensive_position(loader, txn):
    key = "zztest_dl_idp"
    loader.load([_make(key, "DL")], conn=txn)
    rows = _row(txn, loader.players, key)
    assert len(rows) == 1
    assert rows[0].Position == "DL"
    assert rows[0].DefensivePosition == "DL"


def test_team_int_resolves_to_guid(loader, txn):
    # ExternalId 1 exists in the live NFLTeams reference data.
    expected_guid = str(loader.team_map[1]).upper()
    key = "zztest_team_resolve"
    loader.load([_make(key, "WR", nfl_team_id=1)], conn=txn)
    rows = _row(txn, loader.players, key)
    assert str(rows[0].NFLTeamId).upper() == expected_guid


def test_reload_is_idempotent(loader, txn):
    key = "zztest_idem"
    player = _make(key, "RB")
    loader.load([player], conn=txn)
    loader.load([player], conn=txn)  # second run must update, not duplicate
    count = txn.execute(
        text("SELECT COUNT(*) FROM Players WHERE ProReferenceKey = :k"), {"k": key}
    ).scalar()
    assert count == 1
