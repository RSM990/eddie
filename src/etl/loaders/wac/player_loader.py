from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid5

from sqlalchemy import create_engine, MetaData, Table, update, insert, select
from sqlalchemy.engine import Connection

from models.schemas import RosterPlayer
from etl.loaders.base import Loader

# IDP positions get DefensivePosition mirrored from Position.
IDP_POSITIONS = {"EDGE", "DL", "LB", "DB"}

# DateOfBirth is NOT NULL on v2 Players; use this sentinel when DOB is unknown.
DOB_SENTINEL = date(1900, 1, 1)

# Max string lengths on v2 Players (see V2_SCHEMA_CONTRACT.md). Writes are
# truncated to these so an over-long scrape can never overflow a column.
_MAXLEN = {
    "ProReferenceKey": 40,
    "ProReferenceURL": 100,
    "FullName": 250,
    "FirstName": 100,
    "LastName": 150,
    "Position": 10,
    "DefensivePosition": 4,
    "College": 50,
    "Height": 10,
    "Weight": 10,
    "InjuryStatus": 5,
    "InjuryComment": 45,
    "InjuryPracticeStatus": 45,
}


def _trunc(value: Optional[object], col: str) -> Optional[str]:
    """Coerce to str and clamp to the column's max length; pass None through."""
    if value is None:
        return None
    s = str(value)
    n = _MAXLEN.get(col)
    return s[:n] if n is not None else s


def _injury_from_name(full_name: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Roster names can carry a status tag, e.g. "Player Name (IR)".
    Returns (InjuryStatus, InjuryComment, InjuryPracticeStatus); all None if untagged.
    Draft picks have no tag, so this is a no-op for the rookie path.
    """
    if "(IR)" in full_name:
        return "IR", "On Injured Reserve", "IR"
    if "(PUP)" in full_name:
        return "PUP", "On Physically Unable to Perform List", "PUP"
    if "(NFI)" in full_name:
        return "NFI", "On Non-Football Injury List", "NFI"
    if "(COVID)" in full_name:
        return "COVID", "On COVID-19 List", "COVID"
    if ("IRD" in full_name) or ("(IR-R)" in full_name):
        return "IR-R", "On Injured Reserve - Designated for Return", "IR-R"
    return None, None, None


class PlayerLoader(Loader):
    """
    Upserts shared NFL biographical data into the v2 ``Players`` table.

    - Primary key: deterministic ``uuid5(id_namespace, ProReferenceKey)`` for new
      players; existing rows are matched by ``ProReferenceKey`` and keep their Guid.
    - NFL team: scraped int team id (``ExternalId``) -> ``NFLTeams.Id`` Guid.
    - Shared fields only. Never writes ``TradingBlock``/``WeeksLeftOnIR``/``WACStatus``
      (not columns here) nor ``Retired`` (pending the TheWAC migration, DEC-014).
    - Idempotent: re-running produces the same rows, no duplicates.

    Write methods accept an optional ``conn``; when provided, the caller owns the
    transaction (used by tests to roll back). Otherwise each call is its own
    transaction.
    """

    def __init__(self, db_url: str, id_namespace: UUID):
        self.engine = create_engine(db_url, fast_executemany=True)
        self.id_namespace = id_namespace

        # Reflect only the shared tables this loader touches.
        metadata = MetaData()
        metadata.reflect(bind=self.engine, only=["Players", "NFLTeams"])
        self.players: Table = metadata.tables["Players"]
        self.nfl_teams: Table = metadata.tables["NFLTeams"]

        with self.engine.connect() as conn:
            # ProReferenceKey -> existing Player.Id (Guid)
            self.existing_map: Dict[str, str] = {
                row.ProReferenceKey: row.Id
                for row in conn.execute(
                    select(self.players.c.ProReferenceKey, self.players.c.Id)
                )
                if row.ProReferenceKey
            }
            # NFLTeam.ExternalId (v1 int) -> NFLTeam.Id (Guid)
            self.team_map: Dict[int, str] = {
                row.ExternalId: row.Id
                for row in conn.execute(
                    select(self.nfl_teams.c.ExternalId, self.nfl_teams.c.Id)
                )
            }
            # Abbreviation -> NFLTeam.Id (fallback resolution)
            self.team_abbr_map: Dict[str, str] = {
                row.Abbreviation.upper(): row.Id
                for row in conn.execute(
                    select(self.nfl_teams.c.Abbreviation, self.nfl_teams.c.Id)
                )
                if row.Abbreviation
            }

    # --- helpers -------------------------------------------------------------

    def player_guid(self, pro_reference_key: str) -> str:
        """Deterministic Guid for a new player; idempotent across re-runs."""
        return str(uuid5(self.id_namespace, pro_reference_key))

    def resolve_team(self, nfl_team_id: Optional[int]) -> Optional[str]:
        """Map a scraped int team id (ExternalId) to an NFLTeam Guid; None if unrostered/unknown."""
        if nfl_team_id is None:
            return None
        guid = self.team_map.get(nfl_team_id)
        if guid is None:
            print(f"[player] WARN: no NFLTeam for ExternalId={nfl_team_id!r}; leaving NFLTeamId NULL")
        return guid

    # --- writes --------------------------------------------------------------

    def load(self, items: List[RosterPlayer], conn: Optional[Connection] = None) -> Tuple[int, int]:
        """Upsert players. Returns (inserted, updated)."""
        if conn is None:
            with self.engine.begin() as owned:
                result = self._load(owned, items)
        else:
            result = self._load(conn, items)
        inserted, updated = result
        print(f"[player] Done. inserted={inserted}, updated={updated}, total={len(items)}")
        return result

    def _load(self, conn: Connection, items: List[RosterPlayer]) -> Tuple[int, int]:
        inserted = 0
        updated = 0
        for p in items:
            injury_status, injury_comment, injury_practice = _injury_from_name(p.full_name)
            defensive = p.position if p.position in IDP_POSITIONS else None
            team_guid = self.resolve_team(p.nfl_team_id)

            existing_id = self.existing_map.get(p.pro_reference_key)
            if existing_id:
                stmt = (
                    update(self.players)
                    .where(self.players.c.Id == existing_id)
                    .values(
                        NFLTeamId=team_guid,
                        Position=_trunc(p.position, "Position"),
                        JerseyNumber=p.jersey_number,
                        Rookie=p.rookie,
                        DefensivePosition=_trunc(defensive, "DefensivePosition"),
                        InjuryStatus=_trunc(injury_status, "InjuryStatus"),
                        InjuryComment=_trunc(injury_comment, "InjuryComment"),
                        InjuryPracticeStatus=_trunc(injury_practice, "InjuryPracticeStatus"),
                    )
                )
                conn.execute(stmt)
                updated += 1
            else:
                new_id = self.player_guid(p.pro_reference_key)
                stmt = insert(self.players).values(
                    Id=new_id,
                    ProReferenceKey=_trunc(p.pro_reference_key, "ProReferenceKey"),
                    ProReferenceURL=_trunc(p.pro_reference_url, "ProReferenceURL"),
                    FullName=_trunc(p.full_name, "FullName"),
                    FirstName=_trunc(p.first_name, "FirstName"),
                    LastName=_trunc(p.last_name, "LastName"),
                    NFLTeamId=team_guid,
                    JerseyNumber=p.jersey_number,
                    Rookie=p.rookie,
                    Position=_trunc(p.position, "Position"),
                    College=_trunc(p.college, "College"),
                    DateOfBirth=p.date_of_birth or DOB_SENTINEL,
                    Height=_trunc(p.height, "Height"),
                    Weight=_trunc(p.weight, "Weight"),
                    DefensivePosition=_trunc(defensive, "DefensivePosition"),
                    InjuryStatus=_trunc(injury_status, "InjuryStatus"),
                    InjuryComment=_trunc(injury_comment, "InjuryComment"),
                    InjuryPracticeStatus=_trunc(injury_practice, "InjuryPracticeStatus"),
                )
                conn.execute(stmt)
                self.existing_map[p.pro_reference_key] = new_id
                inserted += 1
        return inserted, updated

    def clear_team(self, nfl_team_id: int, conn: Optional[Connection] = None) -> None:
        """Null out NFLTeamId for everyone currently on the given team (roster refresh, Sprint 3)."""
        team_guid = self.resolve_team(nfl_team_id)
        if team_guid is None:
            return
        stmt = (
            update(self.players)
            .where(self.players.c.NFLTeamId == team_guid)
            .values(NFLTeamId=None)
        )
        if conn is None:
            with self.engine.begin() as owned:
                owned.execute(stmt)
        else:
            conn.execute(stmt)

    def reset_rookie_flags(self, conn: Optional[Connection] = None) -> None:
        """Clear the Rookie flag on all players before loading a new draft class."""
        stmt = update(self.players).values(Rookie=False)
        if conn is None:
            with self.engine.begin() as owned:
                owned.execute(stmt)
        else:
            conn.execute(stmt)
