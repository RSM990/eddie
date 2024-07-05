from dotenv import load_dotenv
import os
from src.utils.EddieService import EddieService
from src.utils.Helpers import Helpers
from src.utils.NatStatService import NatStatService


class Players:
    load_dotenv()

    def __init__(self):
        self.eddie_service = EddieService()
        self.nat_stat_service = NatStatService()
        self.helpers = Helpers()
        self.players_added = self.load_players_added()
        self.eddie_url = os.getenv('EDDIE_URL')

    def load_players_added(self):
        players = self.eddie_service.get_data("players?limit=10000", 'players')
        player_list = self.parse_data_to_dictionary(players)

        missing_players = self.eddie_service.get_data('missingPlayers')
        missing_player_list = self.parse_data_to_dictionary(missing_players)

        return missing_player_list | player_list

    @staticmethod
    def parse_data_to_dictionary(data):
        return dict((f"{x.get('league').get('_id')}_{x.get('natStatCode')}", x.get("name")) for x in data)

    def load_players_from_games(self):
        settings_value = 'gamesForPlayerIndex'
        current_index = self.eddie_service.get_settings_value(settings_value)

        url = f"{self.eddie_url}/games?page={current_index}&limit=100"
        while url is not None:
            response = self.eddie_service.get_full_response(url)
            if response is not None:
                data = response.get('data')
                games = data.get('games')

                for game in games:
                    league = game.get('league')
                    league_id = league["_id"]
                    nat_stat_game_id = game.get('natStatCode')
                    data = self.nat_stat_service.get_data(league, "games", nat_stat_game_id)
                    players = data.get('players')
                    for key, player in players.items():
                        if isinstance(player, list):
                            player = player[0]
                        player_id = player.get('player-code')
                        player_name = player.get('player')
                        player_code = f"{league_id}_{player_id}"
                        if self.players_added.get(player_code) is None:
                            player_data = self.nat_stat_service.get_data(league, "players", player_id)
                            if player_data is not None:
                                player_post_request = {
                                    "name": player_data.get('name'),
                                    "natStatCode": player_id,
                                    "careerStart": player_data.get('career-start'),
                                    "careerEnd": player_data.get('career-until'),
                                    "dateOfBirth": player_data.get('dateofbirth'),
                                    "height": player_data.get('height'),
                                    "weight": self.helpers.parse_empty_dict_to_none(player_data.get('weight')),
                                    "hometown": player_data.get('hometown'),
                                    "nationality": player_data.get('nation'),
                                    "league": league_id
                                }

                                self.eddie_service.post_data("players", player_post_request)
                                self.players_added[player_code] = player_data.get('name')
                            else:
                                missing_player = {
                                    "name": player_name,
                                    "natStatCode": player_id,
                                    "league": league_id
                                }
                                self.eddie_service.post_data("missingPlayers", missing_player)
                                self.players_added[player_code] = player_name

                url = response.get('nextPage')
                next_page_index = self.helpers.get_query_string_value(url, 'page')
                self.eddie_service.update_settings_value(settings_value, next_page_index)
            else:
                url = None
