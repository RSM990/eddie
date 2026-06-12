# src/etl/transformers/nfl_draft.py

from bs4 import BeautifulSoup
from typing import List
from datetime import datetime
from etl.transformers.base import Transformer
from etl.utils.teams import translate_team_code_to_id
from etl.utils.position_map import normalize_position
from etl.utils.http import rate_limited
from etl.utils.fetcher import get_pfr_fetcher
from models.schemas import RosterPlayer

class NFLDraftTransformer(Transformer):
    def __init__(self, settings):
        self.position_list = settings.position_list
        # Per-player pages are Cloudflare-gated like the index, so fetch via the
        # configured strategy. Rate-limited below to respect PFR (~18 req/min).
        self.fetcher = get_pfr_fetcher(settings)

    @rate_limited(max_calls=18, period=60.0)
    def fetch_player_soup(self, pro_url: str) -> BeautifulSoup:
        return self.fetcher.get_soup(pro_url)

    def __del__(self):
        fetcher = getattr(self, "fetcher", None)
        if fetcher is not None:
            fetcher.quit()

    @rate_limited(max_calls=19, period=60.0)
    def parse(self, soup: BeautifulSoup, year: int) -> List[RosterPlayer]:
        table = soup.find("table", id="drafts") or soup.find_all("table")[0]
        rows  = table.find("tbody").find_all("tr")
        picks: List[RosterPlayer] = []

        for row in rows:
            cols = row.find_all("td")
            if not cols:
                continue

            # position column is index 3
            raw_pos  = cols[3].get_text().strip()
            position = normalize_position(raw_pos)
            if position not in self.position_list:
                continue

            # drafting team code is in column 1
            team_code     = cols[1].get_text().strip()
            nfl_team_id   = translate_team_code_to_id(team_code)

            # player link is in column 2
            a_tag         = cols[2].find("a", href=True)
            full_name     = a_tag.get_text().strip()
            href          = a_tag["href"]
            key           = href.split("/")[3].split(".")[0]
            pro_url       = f"https://www.pro-football-reference.com{href}"

            # split into first & last
            parts = full_name.split(" ")
            first = parts[0]
            last  = " ".join(parts[1:])

            # fetch the personal page for extra details
            player_soup = self.fetch_player_soup(pro_url)

            # jersey
            jersey = ""
            uni_holder = player_soup.find("div", class_="uni_holder")
            if uni_holder:
                texts = uni_holder.find_all("text")
                if texts:
                    jersey = texts[-1].get_text().strip()

            # birth date
            dob_tag = player_soup.find("span", itemprop="birthDate")
            dob = '1900-01-01'  
            if dob_tag and dob_tag.has_attr("data-birth"):
                try:
                    dob = datetime.fromisoformat(dob_tag["data-birth"]).date()
                except ValueError:
                    dob = '1900-01-01'  

            # height & weight
            h_tag = player_soup.find("span", itemprop="height")
            w_tag = player_soup.find("span", itemprop="weight")
            height = h_tag.get_text().strip() if h_tag else None
            weight = w_tag.get_text().strip() if w_tag else None

            # college (last of comma-split if needed)
            college_col = cols[26].get_text().strip()
            if "," in college_col:
                college = college_col.split(",")[-1].strip()
            else:
                college = college_col or None

            picks.append(RosterPlayer(
                pro_reference_key   = key,
                pro_reference_url   = pro_url,
                full_name           = full_name,
                first_name          = first,
                last_name           = last,
                nfl_team_id         = nfl_team_id,
                jersey_number       = jersey or None,
                rookie              = True,
                position            = position,
                college             = college,
                date_of_birth       = dob,
                height              = height,
                weight              = weight
            ))

        return picks
