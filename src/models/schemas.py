from pydantic import BaseModel
from datetime import date
from typing import Optional

class RosterPlayer(BaseModel):
    pro_reference_key:  str
    pro_reference_url:  str
    full_name:          str
    first_name:         str
    last_name:          str
    nfl_team_id:        int
    jersey_number:      Optional[int]
    rookie:             bool
    position:           str
    college:            Optional[str]
    date_of_birth:      Optional[date]
    height:             Optional[str]
    weight:             Optional[str]
    trading_block:      bool = False
    retired:            bool = False
    weeks_left_on_ir:   int  = 0
