# src/etl/loaders/wac/game_loader.py
from __future__ import annotations

from typing import List, Dict
from sqlalchemy import create_engine, MetaData, Table, select, update, insert
from sqlalchemy.orm import sessionmaker

from models.schemas import NFLGame
from etl.loaders.base import Loader


class GameLoader(Loader):
    """
    Upsert NFLSchedule rows by BoxscoreLink.
    """
    def __init__(self, db_url: str):
        self.engine  = create_engine(db_url, fast_executemany=True)
        self.Session = sessionmaker(bind=self.engine)

        meta = MetaData()
        meta.reflect(bind=self.engine, only=["NFLSchedule"])
        self.schedule: Table = meta.tables["NFLSchedule"]

        with self.engine.connect() as conn:
            rows = conn.execute(select(self.schedule.c.BoxscoreLink, self.schedule.c.Id))
            self.existing_map: Dict[str, int] = {
                row.BoxscoreLink: row.Id for row in rows
            }

    def load(self, games: List[NFLGame]) -> None:
        print(f"Loading {len(games)} games...")

        if not games:
            return

        session = self.Session()
        game_id = 1601
        try:
            for g in games:
                existing_id = self.existing_map.get(g.boxscore_link)
                if existing_id:
                    stmt = (
                        update(self.schedule)
                        .where(self.schedule.c.Id == existing_id)
                        .values(
                            SeasonId=8,
                            Week=g.week,
                            HomeTeamId=g.home_team_id,
                            AwayTeamId=g.away_team_id,
                            StartTime=g.start_time,
                        )
                    )
                    session.execute(stmt)
                else:
                    stmt = insert(self.schedule).values(
                        Id=game_id,
                        SeasonId=8,
                        Week=g.week,
                        HomeTeamId=g.home_team_id,
                        AwayTeamId=g.away_team_id,
                        StartTime=g.start_time,
                        BoxscoreLink=g.boxscore_link,
                    )
                    result = session.execute(stmt)
                    new_id = result.inserted_primary_key[0]
                    self.existing_map[g.boxscore_link] = new_id
                    game_id += 1

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
