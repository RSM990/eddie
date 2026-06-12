# src/etl/loaders/wac/stat_loader.py
from __future__ import annotations

from typing import Dict, List
from sqlalchemy import create_engine, MetaData, Table, select, insert, update, and_

from etl.loaders.base import Loader
from models.stats import PlayerWeekStatPatch

from datetime import datetime


class StatLoader(Loader):
    """
    Loads weekly player stats into PlayerStatLines.
    Upsert key: (SeasonId, NFLWeek, PlayerId, ProjectedStat=False).
    """

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url, fast_executemany=True)
        self.meta   = MetaData()
        self.meta.reflect(bind=self.engine, only=["Players", "PlayerStatLines", "NFLSchedule"])

        self.players           : Table = self.meta.tables["Players"]
        self.player_stat_lines : Table = self.meta.tables["PlayerStatLines"]
        self.schedule          : Table = self.meta.tables["NFLSchedule"]

        # Preload player key -> Id
        with self.engine.connect() as conn:
            rows = conn.execute(select(self.players.c.ProReferenceKey, self.players.c.Id))
            self.player_id_map: Dict[str, int] = {r.ProReferenceKey: r.Id for r in rows}

        # Cache the valid stat columns to avoid trying to write unknown/computed fields
        self._psl_cols = set(self.player_stat_lines.c.keys())
        self._key_cols = {"SeasonId", "NFLWeek", "PlayerId", "ProjectedStat"}

    def get_boxscores_for_week(self, season: int, week: int) -> List[str]:
        with self.engine.connect() as conn:
            now = datetime.now()
            rows = conn.execute(
                select(self.schedule.c.BoxscoreLink)
                .where(and_(
                    self.schedule.c.SeasonId == season,
                    self.schedule.c.Week     == week,
                    self.schedule.c.StartTime < now
                ))
            )
            return [r.BoxscoreLink for r in rows]

    # === Abstract interface implementation ===
    def load(self, *args, **kwargs) -> int:
        """
        Accepts:
          load(season, week, patches)
        or:
          load(season=..., week=..., patches=[PlayerWeekStatPatch,...])
        Returns the number of patches processed (not necessarily distinct players).
        """
        if args and len(args) == 3:
            season, week, patches = args
        else:
            season  = kwargs.get("season")
            week    = kwargs.get("week")
            patches = kwargs.get("patches")

        if season is None or week is None or patches is None:
            raise TypeError("StatLoader.load expects (season, week, patches)")

        self.upsert_stats(int(season), int(week), patches)
        return len(patches)

    def upsert_stats(self, season: int, week: int, player_patches: List[PlayerWeekStatPatch]) -> None:
        # Merge multiple patches per player key
        merged_by_key: Dict[str, Dict[str, int]] = {}
        for p in player_patches:
            d = merged_by_key.get(p.pro_reference_key, {})
            for k, v in p.fields.items():
                d[k] = d.get(k, 0) + (v or 0)
            merged_by_key[p.pro_reference_key] = d

        # Resolve ProReferenceKey -> PlayerId and filter to existing players
        rows_by_pid: Dict[int, Dict[str, int]] = {}
        for pro_key, fields in merged_by_key.items():
            pid = self.player_id_map.get(pro_key)
            if not pid:
                # Unknown player in DB; skip it
                continue
            rows_by_pid[pid] = fields

        # Preload existing PlayerIds for this (season, week, ProjectedStat=False)
        with self.engine.connect() as conn:
            rs = conn.execute(
                select(self.player_stat_lines.c.PlayerId)
                .where(and_(
                    self.player_stat_lines.c.SeasonId      == season,
                    self.player_stat_lines.c.NFLWeek       == week,
                    self.player_stat_lines.c.ProjectedStat == False
                ))
            )
            existing_pids = {row.PlayerId for row in rs}

        # Upsert using the composite key
        with self.engine.begin() as conn:
            for pid, raw_fields in rows_by_pid.items():
                # Only keep columns that actually exist in PlayerStatLines and are not key columns
                fields = {k: v for k, v in raw_fields.items() if k in self._psl_cols and k not in self._key_cols}

                if pid in existing_pids:
                    # UPDATE ... WHERE composite key
                    stmt = (
                        update(self.player_stat_lines)
                        .where(and_(
                            self.player_stat_lines.c.SeasonId      == season,
                            self.player_stat_lines.c.NFLWeek       == week,
                            self.player_stat_lines.c.PlayerId      == pid,
                            self.player_stat_lines.c.ProjectedStat == False
                        ))
                        .values(**fields)
                    )
                    conn.execute(stmt)
                else:
                    # INSERT with composite key + fields
                    payload = {
                        "SeasonId": season,
                        "NFLWeek":  week,
                        "PlayerId": pid,
                        "ProjectedStat": False,
                    }
                    payload.update(fields)
                    conn.execute(insert(self.player_stat_lines).values(**payload))
