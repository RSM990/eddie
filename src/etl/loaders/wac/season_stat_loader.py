# src/etl/loaders/wac/season_stat_loader.py
from __future__ import annotations

from typing import Dict, List, Any, Iterable, Tuple, Union
from sqlalchemy import create_engine, MetaData, Table, select, update, insert, and_, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql import ColumnElement


class SeasonStatLoader:
    """
    Upserts season totals (NFLWeek=0, ProjectedStat=0) into PlayerStatLines.

    Accepts patches either as:
      - a list of {"player_key": str, "category": str, "fields": dict}, or
      - a dict {category: [same objects]}
    """

    def __init__(self, db_url: str) -> None:
        self.engine: Engine = create_engine(db_url)
        md = MetaData()
        # Reflect only the tables we need
        md.reflect(bind=self.engine, only=["Players", "PlayerStatLines"])
        self.players: Table = md.tables["Players"]
        self.player_stat_lines: Table = md.tables["PlayerStatLines"]

        # Preloaded map of ProReferenceKey -> Player.Id
        self.player_key_to_id: Dict[str, int] = {}

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def load(self, year: Union[int, str], week: int, patches: Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]) -> int:
        """
        Upsert season totals for the given year.

        - year: e.g., 2024
        - week: ignored for season totals; we always write NFLWeek = 0
        - patches: list or dict; see class docstring
        """
        y = int(year)
        season_id = self._map_year_to_season_id(y)

        rows = self._normalize_patches(patches)
        if not rows:
            return 0

        self._preload_players()
        existing = self._preload_existing_rows(season_id)  # set of PlayerId with season totals already present

        written = 0
        with self.engine.begin() as conn:
            for patch in rows:
                key = str(patch.get("player_key") or "").strip()
                fields: Dict[str, Any] = patch.get("fields") or {}
                if not key or not isinstance(fields, dict) or not fields:
                    continue

                pid = self.player_key_to_id.get(key)
                if not pid:
                    # Unknown player; skip
                    continue

                where_clause = and_(
                    self.player_stat_lines.c.PlayerId == pid,
                    self.player_stat_lines.c.SeasonId == season_id,
                    self.player_stat_lines.c.NFLWeek == 0,
                    self.player_stat_lines.c.ProjectedStat == 0,
                )

                # Only write valid columns present in the table
                writable = {k: v for k, v in fields.items() if k in self.player_stat_lines.c}

                if pid in existing:
                    # UPDATE path
                    if writable:
                        upd = (
                            update(self.player_stat_lines)
                            .where(where_clause)
                            .values(**writable)
                        )
                        res = conn.execute(upd)
                        # res.rowcount may be -1 under some drivers; treat as success if no exception
                        written += 1
                else:
                    # INSERT path
                    base = {
                        "PlayerId": pid,
                        "SeasonId": season_id,
                        "NFLWeek": 0,
                        "ProjectedStat": 0,
                    }
                    to_insert = {**base, **writable}
                    ins = insert(self.player_stat_lines).values(**to_insert)
                    conn.execute(ins)
                    existing.add(pid)
                    written += 1

        return written

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------

    @staticmethod
    def _map_year_to_season_id(year: int) -> int:
        """
        Linear mapping: 2024 -> 7, 2025 -> 8, etc.
        => season_id = year - 2017
        """
        return year - 2017

    @staticmethod
    def _normalize_patches(
        patches: Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]
    ) -> List[Dict[str, Any]]:
        """
        Accept both shapes:
          - list of {"player_key", "category", "fields"}
          - dict {category: [ {"player_key", "fields"} ]} (category optional inside)
        Returns a flat list of canonical patch dicts.
        """
        if isinstance(patches, list):
            # Already canonical (as returned by the new transformer)
            return patches

        if isinstance(patches, dict):
            flat: List[Dict[str, Any]] = []
            for category, items in patches.items():
                if not isinstance(items, list):
                    continue
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    # Ensure category is present
                    if "category" not in it:
                        it = {**it, "category": category}
                    flat.append(it)
            return flat

        # Unknown shape
        return []

    def _preload_players(self) -> None:
        """Load ProReferenceKey -> Id for Players table."""
        if self.player_key_to_id:
            return

        with self.engine.connect() as conn:
            stmt = select(self.players.c.ProReferenceKey, self.players.c.Id)
            for key, pid in conn.execute(stmt):
                if key:
                    self.player_key_to_id[str(key).strip()] = int(pid)

    def _preload_existing_rows(self, season_id: int) -> set[int]:
        """
        Return a set of PlayerId that already have a season totals row
        (NFLWeek=0, ProjectedStat=0) for the given SeasonId.
        """
        existing: set[int] = set()
        with self.engine.connect() as conn:
            stmt = select(self.player_stat_lines.c.PlayerId).where(
                and_(
                    self.player_stat_lines.c.SeasonId == season_id,
                    self.player_stat_lines.c.NFLWeek == 0,
                    self.player_stat_lines.c.ProjectedStat == 0,
                )
            )
            for (pid,) in conn.execute(stmt):
                existing.add(int(pid))
        return existing
