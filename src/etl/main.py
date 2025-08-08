# src/etl/main.py
import sys

from src.etl.extractors.pfr.draft import PFRDraftExtractor
from src.etl.transformers.nfl_draft import NFLDraftTransformer


import argparse
from etl.config                  import Settings
from etl.extractors.pfr.roster import PFRRosterExtractor
from etl.transformers.nfl_roster import NFLRosterTransformer
from etl.loaders.wac.player_loader   import PlayerLoader
from etl.utils.teams             import translate_team_id_to_code
from etl.extractors.pfr.games      import PFRGamesExtractor
from etl.transformers.nfl_games    import NFLGamesTransformer
from etl.loaders.wac.game_loader   import GameLoader


def main():
    parser = argparse.ArgumentParser(prog="eddie ETL",
                                     description="Run NFL roster ETL")
    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="NFL season (e.g. 2024)"
    )
    parser.add_argument(
        "--week",
        type=int,
        required=True,
        help="NFL week number (1–18)"
    )
    args = parser.parse_args()

    settings    = Settings()
    extractor   = PFRRosterExtractor(settings, use_selenium=True)
    draft_extractor   = PFRDraftExtractor(settings)
    transformer = NFLRosterTransformer(settings)
    draft_transformer = NFLDraftTransformer(settings)
    loader      = PlayerLoader(settings.db_url)

    game_extractor   = PFRGamesExtractor(settings)
    game_transformer = NFLGamesTransformer()
    game_loader      = GameLoader(settings.db_url)



    RUN_DRAFT = False

    LOAD_GAMES = True
    
    LOAD_PLAYERS = False

    if RUN_DRAFT:
        loader.reset_rookie_flags()
        soup = draft_extractor.fetch(args.season)
        draft = draft_transformer.parse(soup, args.season)
        loader.load(draft)
    

    if LOAD_GAMES:
        soup = game_extractor.fetch(args.season)
        games = game_transformer.parse(soup, args.season)
        game_loader.load(games)

    if LOAD_PLAYERS:
        for team_id in range(1, 33):
            code   = translate_team_id_to_code(team_id, historical=True).lower()
            soup   = extractor.fetch(args.season, code)
            roster = transformer.parse(soup, team_id)

            loader.clear_team(team_id)
            loader.load(roster)
        

            print(f"Team {team_id} ({code}): loaded {len(roster)} players")

    print("✅ Roster ETL complete")

if __name__ == "__main__":
    main()
