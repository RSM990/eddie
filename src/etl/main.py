# src/etl/main.py
import sys
print("▶ sys.argv:", sys.argv)

import argparse
from etl.config                  import Settings
from etl.extractors.pfr.roster import PFRRosterExtractor
from etl.transformers.nfl_roster import NFLRosterTransformer
from etl.loaders.wac.player_loader   import PlayerLoader
from etl.utils.teams             import translate_team_id_to_code

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
    transformer = NFLRosterTransformer(settings)
    loader      = PlayerLoader(settings.db_url)

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
