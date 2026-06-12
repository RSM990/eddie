# src/etl/main.py
import sys

from src.etl.extractors.pfr.draft import PFRDraftExtractor
from src.etl.transformers.nfl_draft import NFLDraftTransformer


import argparse
from etl.config                  import Settings
from etl.extractors.pfr.http import PFRHttpClient


from etl.utils.teams             import translate_team_id_to_code


from etl.extractors.pfr.roster import PFRRosterExtractor
from etl.transformers.nfl_roster import NFLRosterTransformer
from etl.loaders.wac.player_loader   import PlayerLoader



from etl.extractors.pfr.games      import PFRGamesExtractor
from etl.transformers.nfl_games    import NFLGamesTransformer
from etl.loaders.wac.game_loader   import GameLoader

from etl.extractors.pfr.boxscores    import PFRBoxscoreExtractor
from etl.transformers.nfl_stats      import NFLStatsTransformer
from etl.loaders.wac.stat_loader     import StatLoader


from etl.extractors.pfr.season_stats import PFRSeasonExtractor
from etl.transformers.nfl_season_stats import NFLSeasonStatsTransformer
from etl.loaders.wac.season_stat_loader import SeasonStatLoader

def _normalize_box_link(link: str) -> str:
    # Accept either full URL or PFR-relative path ("/boxscores/....htm")
    if link.startswith("http"):
        return link
    return f"https://www.pro-football-reference.com{link}"

def derive_season_id(year: int) -> int:
    """
    Linear mapping provided:
      2024 -> 7, 2025 -> 8, ...
      season_id = 7 + (year - 2024)
    """
    base_year = 2024
    base_id = 7
    return base_id + (year - base_year)


from etl.extractors.pfr.injuries import PFRInjuryExtractor
from etl.transformers.nfl_injuries import NFLInjuryTransformer
from etl.loaders.wac.injury_loader import InjuryLoader


def run_injury_sync(settings):
    extractor   = PFRInjuryExtractor(settings)   # uses cloudscraper + rate limit
    transformer = NFLInjuryTransformer()
    loader      = InjuryLoader(settings.db_url)

    soup  = extractor.fetch()            # returns BeautifulSoup with the injuries table
    rows  = transformer.parse(soup)      # list of dicts
    loader.clear_injuries(False)              # clear all 3 fields first
    loader.load(rows)                    # upsert current injuries

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

    stats_extractor   = PFRBoxscoreExtractor(settings)
    stats_transformer = NFLStatsTransformer()
    stats_loader      = StatLoader(settings.db_url)

    client                    = PFRHttpClient()
    season_stat_extractor   = PFRSeasonExtractor(settings)
    season_stat_transformer = NFLSeasonStatsTransformer()
    season_stat_loader      = SeasonStatLoader(settings.db_url)

    RUN_DRAFT = False

    LOAD_GAMES = False
    
    LOAD_PLAYERS = False

    LOAD_STATS = True  

    LOAD_SEASON_STATS = False
    
    RUN_INJURIES = False

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
        injury_loader = InjuryLoader(settings.db_url)
        injury_loader.clear_injuries(True)
        for team_id in range(1, 33):
            
            code   = translate_team_id_to_code(team_id, historical=True).lower()
            soup   = extractor.fetch(args.season, code)
            roster = transformer.parse(soup, team_id)

            loader.clear_team(team_id)

            loader.load(roster)
        

            print(f"Team {team_id} ({code}): loaded {len(roster)} players")



    if LOAD_STATS:
        #remember to replace season and week with args.season and args.week
        season = 8
        week = 15
        print(f"Loading stats for season {season}, week {week}...")

        links = stats_loader.get_boxscores_for_week(season, week)
        if not links:
            print(f"No boxscores found for season={season}, week={week}")
            return

        total_patches = 0
        for raw_link in links:
            link = _normalize_box_link(raw_link)
            soup = stats_extractor.fetch(link)
            patches = stats_transformer.parse(soup)
            stats_written = stats_loader.load(season, week, patches)
            total_patches += stats_written

        print(f"✅ Stats loaded for week {week} ({season}). Patches: {total_patches}")

    if LOAD_SEASON_STATS:
        patches = season_stat_transformer.parse_all(args.season, season_stat_extractor.fetch)
        written = season_stat_loader.load(args.season, 0, patches)
        print(f"Season totals written: {written}")


    if RUN_INJURIES:
        run_injury_sync(settings)


    print("✅ WAC Data Update complete")

if __name__ == "__main__":
    main()
