from dotenv import load_dotenv
import os
import requests
import sys
from tqdm import tqdm

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
        self.league_id = "665675c96ee6047fe80443da"
        self.player_lookup = {}
        self.team_lookup = {}

    def update_todays_games(self):
        print("Updating Today's Games")
        path = "games/todays-games"
        self.update_games(path)

    def score_games(self):
        path = "games/games-to-score"
        self.update_games(path)

    def load_stats_test(self):
        url = f"{self.eddie_service.eddie_url}/games?league={self.league_id}&limit=10&page=1821"
        api_response = self.eddie_service.get_data_new(url)
        for i in tqdm(range(1821, api_response.total_pages), initial=1821, desc="Parsing Game Pages", leave=False):
            url = f"{self.eddie_service.eddie_url}/games?league={self.league_id}&limit=10&page={i+1}"
            api_response = self.eddie_service.get_data_new(url)
            for game in tqdm(api_response.data, desc="Parsing Games", leave=False):
                league = game.get('league')
                game_id = game.get('_id')
                nat_stat_game_id = game.get('natStatCode')
                data = self.nat_stat_service.get_data(league, self.resource, nat_stat_game_id)
                if data is not None:
                    update_body = {
                        "homeScore": data.get('score-home'),
                        "awayScore": data.get('score-vis'),
                        "gameStatus": data.get('gamestatus'),
                        "overtime": data.get('overtime'),
                        "gameDay": data.get('gamedate')
                    }

                    update_url = f"{self.eddie_url}/{self.resource}/{game_id}"
                    requests.patch(update_url, json=update_body)

                    self.load_game_stats(data, nat_stat_game_id)

            pass


    def load_nba_game_stats(self):
        url = f"{self.eddie_service.eddie_url}/games?league={self.league_id}"
        # first_pass = True
        # while url is not None:
        #
        #     api_response = self.eddie_service.get_data_new(url)
        #
        #     if first_pass:
        #         game_count = tqdm(api_response.total_results, desc=f"Processing Games", file=sys.stdout)
        #         first_pass = False
        #
        #     for game in api_response.data:
        #         league = game.get('league')
        #         game_id = game.get('_id')
        #         nat_stat_game_id = game.get('natStatCode')
        #         data = self.nat_stat_service.get_data(league, self.resource, nat_stat_game_id)
        #         if data is not None:
        #             update_body = {
        #                 "homeScore": data.get('score-home'),
        #                 "awayScore": data.get('score-vis'),
        #                 "gameStatus": data.get('gamestatus'),
        #                 "overtime": data.get('overtime'),
        #                 "gameDay": data.get('gamedate')
        #             }
        #
        #             update_url = f"{self.eddie_url}/{self.resource}/{game_id}"
        #             requests.patch(update_url, json=update_body)
        #
        #             self.load_game_stats(data, nat_stat_game_id)
        #         game_count.update(1)
        #         url = api_response.next_page


    def update_games(self, path):
        games = self.eddie_service.get_data(path, self.resource)
        game_count = tqdm(len(games), desc=f"Processing Games", file=sys.stdout)
        for game in games:
            league = game.get('league')
            game_id = game.get('_id')
            nat_stat_game_id = game.get('natStatCode')
            data = self.nat_stat_service.get_data(league,  self.resource, nat_stat_game_id)
            if data is not None:
                update_body = {
                    "homeScore": data.get('score-home'),
                    "awayScore": data.get('score-vis'),
                    "gameStatus": data.get('gamestatus'),
                    "overtime": data.get('overtime'),
                    "gameDay": data.get('gamedate')
                }

                update_url = f"{self.eddie_url}/{self.resource}/{game_id}"
                requests.patch(update_url, json=update_body)

                self.load_game_stats(data, nat_stat_game_id)
            game_count.update(1)

    def load_game_stats(self, data, nat_stat_game_id):
        player_performances = data.get('playerperfs')
        if player_performances:
            stat_lines = list(player_performances.values())
            for stats in tqdm(stat_lines, desc="Parsing Players in Game", leave=False):
                player = stats.get('player')
                nat_stat_player_id = stats.get('player-code')

                team_id = None
                if stats.get('team'):
                    team_code = stats.get('team').get('code')
                    if team_code in self.team_lookup:
                        team_id = self.team_lookup[team_code]
                    else:
                        team_data = self.eddie_service.get_data(f'teams?code={team_code}&league=665675c96ee6047fe80443da',
                                                            "teams")
                        if len(team_data) > 0:
                            team_id = team_data[0].get("_id")
                            self.team_lookup[team_code] = team_id

                player_id = None
                if nat_stat_player_id in self.player_lookup:
                    player_id = self.player_lookup[nat_stat_player_id]
                else:
                    player_data = self.eddie_service.get_data(f'players?natStatCode={nat_stat_player_id}', "players")
                    if len(player_data) == 0:
                        missing_player = {
                            "name": player,
                            "natStatCode": nat_stat_player_id,
                            "league": self.league_id
                        }
                        self.eddie_service.post_data("missingPlayers", missing_player)
                        self.eddie_service.post_data("players", missing_player)
                        player_data = self.eddie_service.get_data(f'players?natStatCode={nat_stat_player_id}',
                                                                  "players")
                        player_id = player_data[0].get("_id")
                        self.player_lookup[nat_stat_player_id] = player_id
                    else:
                        player_id = player_data[0].get("_id")
                        self.player_lookup[nat_stat_player_id] = player_id

                game_data = self.eddie_service.get_data(f'games?natStatCode={nat_stat_game_id}', "games")
                if player_id is not None and len(game_data) > 0 and team_id is not None:
                    data_fields = ["min", "pts", "fgm", "fga", "threefm", "threefa", "ftm", "fta", "reb", "ast", "stl",
                                   "blk", "oreb", "to", "pf"]

                    stat_object = {stat: stats.get(stat) for stat in data_fields}
                    stat_object["player"] = player_id
                    stat_object["game"] = game_data[0].get("_id")
                    stat_object["team"] = team_id
                    stat_object["statType"] = "Basketball"

                    response = self.eddie_service.post_data("gameStats", stat_object)

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