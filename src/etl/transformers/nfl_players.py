from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime
from etl.transformers.base import Transformer
from etl.utils.teams import translate_team_code_to_id
from etl.utils.position_map import normalize_position
from etl.utils.http import get_session, rate_limited
from string import ascii_uppercase

# Simple DTO for status updates
class PlayerStatus:
    def __init__(
        self,
        pro_reference_key: str,
        retired: bool,
        jersey_number: Optional[int],
        current_team_id: Optional[int],
    ):
        self.pro_reference_key = pro_reference_key
        self.retired            = retired
        self.jersey_number      = jersey_number
        self.current_team_id    = current_team_id

class PFRPlayersTransformer(Transformer):
    def __init__(self, settings):
        self.last_active_year = settings.LAST_ACTIVE_YEAR_CHECK
        self.position_list    = settings.POSITION_LIST
        self.session          = get_session(settings.user_agent)

    @rate_limited(max_calls=10, period=60.0)
    def fetch_player_soup(self, pro_url: str) -> BeautifulSoup:
        """Rate‑limited personal‐page fetch."""
        resp = self.session.get(pro_url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def parse_letter(self, soup: BeautifulSoup) -> List[PlayerStatus]:
        container = soup.find("div", id="div_players")
        if not container:
            return []

        statuses: List[PlayerStatus] = []
        for p in container.find_all("p"):
            txt = p.get_text()
            # skip anyone whose final year < threshold
            try:
                last_year = int(txt.rsplit("-", 1)[-1].strip(") "))
            except ValueError:
                continue
            if last_year < self.last_active_year:
                continue

            # retired = not-bold
            retired = not bool(p.find_all("b"))

            # link + key
            a = p.find("a", href=True)
            key = a["href"].split("/")[3].split(".")[0]

            # position filter
            raw_pos = txt.split("(")[1].split(")")[0]
            pos     = normalize_position(raw_pos)
            if pos not in self.position_list:
                continue

            # fetch personal page
            pro_url     = f"https://www.pro-football-reference.com{a['href']}"
            player_soup = self.fetch_player_soup(pro_url)

            # jersey
            jersey = None
            uni = player_soup.find("div", class_="uni_holder")
            if uni:
                texts = uni.find_all("text")
                if texts:
                    try:
                        jersey = int(texts[-1].get_text())
                    except ValueError:
                        jersey = None

            # current team
            team_id = None
            aff = player_soup.find("span", itemprop="affiliation")
            if aff:
                link = aff.find("a", href=True)
                if link:
                    code    = link["href"].split("/")[2].upper()
                    team_id = translate_team_code_to_id(code)

            statuses.append(PlayerStatus(
                pro_reference_key = key,
                retired            = retired,
                jersey_number      = jersey,
                current_team_id    = team_id
            ))

        return statuses
