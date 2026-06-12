"""
Roster / player-refresh retarget tests (Phase 4.75, Sprint 3).

Asserts the v2 roster-refresh contract on PlayerLoader:
  - clear_team nulls NFLTeamId for a team (int -> Guid resolution)
  - a player who leaves a team and isn't reloaded ends up unrostered (NULL)
  - re-loading an existing player updates team / position / injury (upsert)
  - status tags in the scraped name map to InjuryStatus
  - the roster path never writes Retired (column not present yet; owned by a
    separate retirement signal + manual admin, never inferred from rosters)

Writes happen inside a rolled-back transaction so real Players data is untouched.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

from etl.config import Settings
from etl.loaders.wac.player_loader import PlayerLoader, _injury_from_name
from models.schemas import RosterPlayer


def _roster(key: str, position: str, team_id: int, full_name: str = "Test Player", **over) -> RosterPlayer:
    base = dict(
        pro_reference_key=key,
        pro_reference_url=f"https://example.com/{key}.htm",
        full_name=full_name,
        first_name="Test",
        last_name="Player",
        nfl_team_id=team_id,
        jersey_number=None,
        rookie=False,
        position=position,
        college=None,
        date_of_birth=None,
        height=None,
        weight=None,
    )
    base.update(over)
    return RosterPlayer(**base)


@pytest.fixture(scope="module")
def loader():
    settings = Settings()
    try:
        eng = create_engine(settings.db_url)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        pytest.skip(f"v2 DB not reachable: {exc.__class__.__name__}")
    return PlayerLoader(settings.db_url, settings.id_namespace)


@pytest.fixture
def txn(loader):
    conn = loader.engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()


def _team_of(conn, players, key):
    return conn.execute(
        select(players.c.NFLTeamId, players.c.Position, players.c.DefensivePosition,
               players.c.InjuryStatus)
        .where(players.c.ProReferenceKey == key)
    ).fetchone()


# --- pure logic ----------------------------------------------------------

def test_injury_from_name_tags():
    assert _injury_from_name("Joe Back (IR)")[0] == "IR"
    assert _injury_from_name("Joe Back (PUP)")[0] == "PUP"
    assert _injury_from_name("Joe Back (NFI)")[0] == "NFI"
    assert _injury_from_name("Healthy Guy") == (None, None, None)


def test_roster_path_does_not_write_retired(loader):
    # The migration hasn't landed; the roster path must not depend on Retired.
    assert "Retired" not in loader.players.c


# --- DB round-trips (rolled back) ----------------------------------------

def test_clear_team_nulls_assignment(loader, txn):
    key = "zztest_clear_team"
    loader.load([_roster(key, "WR", team_id=1)], conn=txn)
    row = _team_of(txn, loader.players, key)
    assert str(row.NFLTeamId).upper() == str(loader.team_map[1]).upper()

    loader.clear_team(1, conn=txn)
    row = _team_of(txn, loader.players, key)
    assert row.NFLTeamId is None  # unrostered after clear


def test_player_leaving_team_is_unrostered(loader, txn):
    # Simulate a player who was on team 1 but isn't on the refreshed roster:
    # clear_team runs, the player isn't reloaded, so NFLTeamId stays NULL.
    key = "zztest_left_team"
    loader.load([_roster(key, "RB", team_id=1)], conn=txn)
    loader.clear_team(1, conn=txn)
    # (no reload for this player)
    row = _team_of(txn, loader.players, key)
    assert row.NFLTeamId is None


def test_reload_updates_team_position_and_injury(loader, txn):
    key = "zztest_upsert_refresh"
    loader.load([_roster(key, "WR", team_id=1)], conn=txn)

    # Player moved to team 2, switched to an IDP position, now on IR.
    loader.load([_roster(key, "LB", team_id=2, full_name="Test Player (IR)")], conn=txn)

    row = _team_of(txn, loader.players, key)
    assert str(row.NFLTeamId).upper() == str(loader.team_map[2]).upper()
    assert row.Position == "LB"
    assert row.DefensivePosition == "LB"   # IDP mirror
    assert row.InjuryStatus == "IR"
