from src.data.Games import Games
from src.data.Players import Players
from src.utils.EddieService import EddieService

games = Games()
games.score_games()
games.update_todays_games()
# games.load_stats_test()


#
# players = Players()
# players.load_players_from_games()
# from tqdm import tqdm
#
# for i in tqdm(range(int(9e6)), desc="Testy testy"):
#     pass


