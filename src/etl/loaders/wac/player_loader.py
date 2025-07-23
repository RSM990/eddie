from typing import List, Dict
from sqlalchemy import create_engine, MetaData, Table, update, insert, select
from sqlalchemy.orm import sessionmaker

from models.schemas import RosterPlayer
from etl.loaders.base import Loader

class PlayerLoader(Loader):
    def __init__(self, db_url: str):
        # Create engine with fast_executemany for ODBC
        self.engine = create_engine(db_url, fast_executemany=True)
        self.Session = sessionmaker(bind=self.engine)

        # Reflect only the Players table
        metadata = MetaData()
        metadata.reflect(bind=self.engine, only=["Players"])
        self.players = metadata.tables["Players"]

        # Preload existing players: ProReferenceKey -> Id
        with self.engine.connect() as conn:
            result = conn.execute(
                select(self.players.c.ProReferenceKey, self.players.c.Id)
            )
            self.existing_map: Dict[str, int] = {
                row.ProReferenceKey: row.Id for row in result
            }

    def clear_team(self, team_id: int):
        stmt = (
            update(self.players)
            .where(self.players.c.NFLTeamId == team_id)
            .where(self.players.c.Id > 0)
            .values(NFLTeamId=None)
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def load(self, items: List[RosterPlayer]):
        session = self.Session()
        for p in items:
            existing_id = self.existing_map.get(p.pro_reference_key)
            if existing_id:
                # Update existing player
                stmt = (
                    update(self.players)
                    .where(self.players.c.Id == existing_id)
                    .values(NFLTeamId=p.nfl_team_id, Retired=False)
                )
                session.execute(stmt)
            else:
                # Insert new player
                stmt = insert(self.players).values(
                    ProReferenceKey = p.pro_reference_key,
                    ProReferenceURL = p.pro_reference_url,
                    FullName        = p.full_name,
                    FirstName       = p.first_name,
                    LastName        = p.last_name,
                    NFLTeamId       = p.nfl_team_id,
                    JerseyNumber    = p.jersey_number,
                    Rookie          = p.rookie,
                    Position        = p.position,
                    College         = p.college,
                    DateOfBirth     = p.date_of_birth,
                    Height          = p.height,
                    Weight          = p.weight,
                    TradingBlock    = p.trading_block,
                    Retired         = p.retired,
                    WeeksLeftOnIR   = p.weeks_left_on_ir
                )
                result = session.execute(stmt)
                # Capture the newly inserted ID
                new_id = result.inserted_primary_key[0]
                self.existing_map[p.pro_reference_key] = new_id

        session.commit()
        session.close()


    def reset_rookie_flags(self):
            """
            Clear the Rookie flag on *all* existing players before loading new rookies.
            """
            stmt = update(self.players).values(Rookie=False)
            with self.engine.begin() as conn:
                conn.execute(stmt)
