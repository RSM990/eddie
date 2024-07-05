from dotenv import load_dotenv
import os
import requests

from src.data.Leagues import Leagues
from src.data.Teams import Teams
from src.data.Venues import Venues
from src.utils.EddieService import EddieService
from src.utils.NatStatService import NatStatService


class Games:
    load_dotenv()

    def __init__(self):
        self.resource = "games"
        self.eddie_url = os.getenv('EDDIE_URL')
        self.nat_stat_service = NatStatService()
        self.eddie_service = EddieService()
        self.leagues = Leagues()
        self.venues = Venues()
        self.teams = Teams()

    def update_todays_games(self):
        print("Updating Today's Games")
        path = "games/todays-games"
        self.update_games(path)

    def score_games(self):
        path = "games/games-to-score"
        self.update_games(path)

    def update_games(self, path):
        games = self.eddie_service.get_data(path, self.resource)
        for game in games:
            league = game.get('league')
            game_id = game.get('_id')
            nat_stat_game_id = game.get('natStatCode')
            data = self.nat_stat_service.get_data(league,  self.resource, nat_stat_game_id)

            update_body = {
                "homeScore": data.get('score-home'),
                "awayScore": data.get('score-vis'),
                "gameStatus": data.get('gamestatus'),
                "overtime": data.get('overtime'),
                "gameDay": data.get('gamedate')
            }

            update_url = f"{self.eddie_url}/{self.resource}/{game_id}"
            requests.patch(update_url, json=update_body)

    def load_games(self):
        for current_league in self.leagues.get_leagues():
            for year in range(2009, 2025):
                url = "not null to start!"
                while url is not None:
                    response = self.nat_stat_service.get_full_response(current_league, self.resource, year)
                    if self.nat_stat_service.is_successful_response(response):
                        games = response[self.resource]
                        for game_id, game in games.items():
                            if game is None:
                                continue
                            league_id = current_league.get("_id")
                            post_request = self.parse_game_data(league_id, year, game)
                            self.eddie_service.post_data(self.resource, post_request)

                        url = self.nat_stat_service.get_next_url(response)
                    else:
                        url = None

    def parse_game_data(self, league_id, season, data):
        return {
            "natStatCode": data.get('id'),
            "awayTeam": self.teams.get_team_from_code(league_id, data.get('visitor-code')),
            "awayScore": data.get('score-vis'),
            "homeTeam": self.teams.get_team_from_code(league_id, data.get('home-code')),
            "homeScore": data.get('score-home'),
            "gameStatus": data.get('gamestatus'),
            "overtime": data.get('overtime'),
            "winner": data.get('winner-code'),
            "loser": data.get('loser-code'),
            "gameDay": data.get('gameday'),
            "gameNumber": data.get('gameno'),
            "venue": self.venues.get_venue_id_from_code(data.get('venue-code')),
            "season": season,
            "league": league_id
        }