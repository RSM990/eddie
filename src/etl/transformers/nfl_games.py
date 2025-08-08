# src/etl/transformers/nfl_games.py
from __future__ import annotations

from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime

from etl.transformers.base import Transformer
from etl.utils.teams import translate_team_code_to_id
from models.schemas import NFLGame

from etl.utils.dates import parse_pfr_kickoff

class NFLGamesTransformer(Transformer):
    """
    Parse the season games table into NFLGame objects.
    """

    def parse(self, soup: BeautifulSoup, season: int) -> List[NFLGame]:
        print(f"Parsing games for season {season}...")
        table = soup.find("table", id="games") or (soup.find_all("table")[0] if soup.find_all("table") else None)
        if not table:
            return []

        tbody = table.find("tbody")
        if not tbody:
            return []

        games: List[NFLGame] = []

        for row in tbody.find_all("tr"):
            th = row.find("th")
            if not th:
                continue

            week_text = th.get_text(strip=True)
            # Skip headers & preseason
            if week_text == "Week" or "Pre" in week_text:
                continue

            try:
                week = int(week_text)  # playoff labels like "WildCard" are skipped
            except ValueError:
                continue

            cols = row.find_all("td")
            if len(cols) < 8:
                continue

            # Boxscore link ⇒ date
            link = cols[1].find("a", href=True)
            if not link:
                continue
            href = link["href"]                           # /boxscores/202409070atl.htm
            filename = href.split("/")[-1]                # 202409070atl.htm
            date_yyyymmdd = filename[:8]                  # 20240907
            if len(date_yyyymmdd) != 8 or not date_yyyymmdd.isdigit():
                continue

            # Teams
            away_a = cols[2].find("a", href=True)
            home_a = cols[5].find("a", href=True)
            if not away_a or not home_a:
                continue

            away_code = away_a["href"].split("/")[2].upper()
            home_code = home_a["href"].split("/")[2].upper()
            away_id = translate_team_code_to_id(away_code)
            home_id = translate_team_code_to_id(home_code)
            if away_id is None or home_id is None:
                continue

            time_text = cols[7].get_text(strip=True)
            start_time: Optional[datetime] = parse_pfr_kickoff(date_yyyymmdd, time_text)

            games.append(NFLGame(
                season_id=season,
                week=week,
                home_team_id=home_id,
                away_team_id=away_id,
                start_time=start_time,
                boxscore_link=f"https://www.pro-football-reference.com{href}",
            ))

        return games
