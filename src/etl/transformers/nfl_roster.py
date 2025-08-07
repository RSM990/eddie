# src/etl/transformers/nfl_roster.py

from bs4 import BeautifulSoup
from datetime import datetime
from typing import List

# Absolute imports off src/
from models.schemas                import RosterPlayer
from etl.utils.position_map        import normalize_position
from etl.transformers.base        import Transformer

class NFLRosterTransformer(Transformer):
    def __init__(self, settings):
        self.position_list = settings.position_list

    def parse(self, soup: BeautifulSoup, team_id: int) -> List[RosterPlayer]:
        table = soup.find("table", id="roster")
        if not table:
            return []
        rows = table.find("tbody").find_all("tr")
        players: List[RosterPlayer] = []

        print(f"Parsing {len(rows)} players for team {team_id}",end="\r",flush=True)
        for  row in rows:
            cols = row.find_all("td")
            if not cols:
                continue

            full_name = cols[0].text.strip()

            raw_pos   = cols[2].text.split("/")[0]
            position  = normalize_position(raw_pos)

            if position not in self.position_list:
                continue

            link = cols[0].find("a")
            if not link:
                continue

            href = link["href"]
            key  = href.split("/")[3].split(".")[0]
            pro_url = f"https://www.pro-football-reference.com{href}"

            first, *rest = full_name.split(" ")
            last = " ".join(rest)

            try:
                jersey = int(cols[1].text.strip())
            except ValueError:
                jersey = None

            dob_text = cols[8].text.strip()
            try:
                dob = datetime.strptime(dob_text, "%Y-%m-%d").date()
            except ValueError:
                dob = '1900-01-01'  

            rookie  = cols[9].text.strip() == "Rook"
            raw_college = cols[7].text.strip()
            if "," in raw_college:
                # e.g. "School A, School B" → take "School B"
                college = raw_college.split(",")[-1].strip() or None
            else:
                college = raw_college or None
                
            height  = cols[6].text.strip() or None
            weight  = cols[5].text.strip() or None      
            
            players.append(RosterPlayer(
                pro_reference_key=key,
                pro_reference_url=pro_url,
                full_name=full_name,
                first_name=first,
                last_name=last,
                nfl_team_id=team_id,
                jersey_number=jersey,
                rookie=rookie,
                position=position,
                college=college,
                date_of_birth=dob,
                height=height,
                weight=weight
            ))
        
        return players
