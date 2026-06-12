from typing import List, Dict, Optional
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
        for idx, p in enumerate(items, start=1):
            injury_status = None
            injury_comment = None
            injury_practice_status = None
            if "(IR)" in p.full_name:
                injury_status = "IR"
                injury_comment = "On Injured Reserve"
                injury_practice_status = "IR"
            elif "(PUP)" in p.full_name:
                injury_status = "PUP"
                injury_comment = "On Physically Unable to Perform List"
                injury_practice_status = "PUP"
            elif "(NFI)" in p.full_name:
                injury_status = "NFI"
                injury_comment = "On Non-Football Injury List"
                injury_practice_status = "NFI"
            elif "(COVID)" in p.full_name:
                injury_status = "COVID"
                injury_comment = "On COVID-19 List"
                injury_practice_status = "COVID"    
            elif ("IRD" in p.full_name) or ("(IR-R)" in p.full_name):
                injury_status = "IR-R"
                injury_comment = "On Injured Reserve - Designated for Return"
                injury_practice_status = "IR-R"



            existing_id = self.existing_map.get(p.pro_reference_key)
            if existing_id:
                print(
                    f"Row {idx} of {len(items)}  - Updating ({p.full_name})",
                    end="\r",
                    flush=True
                )
                defensive_position = None
                # Update existing player
                if p.position in [ "EDGE", "DL", "LB", "DB" ]:
                    defensive_position = p.position
                    

                stmt = (
                    update(self.players)
                    .where(self.players.c.Id == existing_id)
                    .values(NFLTeamId=p.nfl_team_id, 
                            Retired=False, 
                            Position=p.position,  
                            JerseyNumber=p.jersey_number, 
                            DefensivePosition= defensive_position, 
                            InjuryStatus=injury_status, 
                            InjuryComment=injury_comment, 
                            InjuryPracticeStatus=injury_practice_status)
                )

                session.execute(stmt)
            else:
                print(
                    f"Row {idx} of {len(items)}  - Adding ({p.full_name})",
                    end="\r",
                    flush=True
                )
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
                    WeeksLeftOnIR   = p.weeks_left_on_ir,
                    DefensivePosition = p.position if p.position in [ "EDGE", "DL", "LB", "DB" ] else None,
                    InjuryStatus    = injury_status,
                    InjuryComment   = injury_comment,
                    InjuryPracticeStatus = injury_practice_status
                )
                result = session.execute(stmt)
                # Capture the newly inserted ID
                new_id = result.inserted_primary_key[0]
                self.existing_map[p.pro_reference_key] = new_id
        print()
        session.commit()
        session.close()

        
    def update_player_status(
        self,
        pro_reference_key: str,
        retired: bool,
        jersey_number: Optional[int],
        nfl_team_id: Optional[int],
    ):
        player_id = self.existing_map.get(pro_reference_key)
        if not player_id:
            return
        stmt = (
            update(self.players)
            .where(self.players.c.Id == player_id)
            .values(
                Retired        = retired,
                JerseyNumber   = jersey_number,
                NFLTeamId      = nfl_team_id
            )
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)


    def reset_rookie_flags(self):
            """
            Clear the Rookie flag on *all* existing players before loading new rookies.
            """
            stmt = update(self.players).values(Rookie=False)
            with self.engine.begin() as conn:
                conn.execute(stmt)
