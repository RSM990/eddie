from src.data.Games import Games
from src.data.Players import Players


games = Games()
games.score_games()
games.update_todays_games()

players = Players()
players.load_players_from_games()


