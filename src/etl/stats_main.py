from __future__ import annotations

import argparse

from etl.config                      import Settings
from etl.extractors.pfr.boxscores    import PFRBoxscoreExtractor
from etl.transformers.nfl_stats      import NFLStatsTransformer
from etl.loaders.wac.stat_loader     import StatLoader


def _normalize_box_link(link: str) -> str:
    # Accept either full URL or PFR-relative path ("/boxscores/....htm")
    if link.startswith("http"):
        return link
    return f"https://www.pro-football-reference.com{link}"

def main():
    parser = argparse.ArgumentParser("eddie Stats ETL (box score → PlayerStatLines)")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week",   type=int, required=True)
    args = parser.parse_args()

    settings    = Settings()
    extractor   = PFRBoxscoreExtractor(settings)
    transformer = NFLStatsTransformer()
    loader      = StatLoader(settings.db_url)

    #remember to replace season and week with args.season and args.week
    season = 7
    week = 1


    links = loader.get_boxscores_for_week(season, week)
    if not links:
        print(f"No boxscores found for season={season}, week={week}")
        return

    total_patches = 0
    for raw_link in links:
        link = _normalize_box_link(raw_link)
        soup = extractor.fetch_boxscore(link)
        patches = transformer.parse_boxscore(soup)
        loader.upsert_stats(season, week, patches)
        total_patches += len(patches)

    print(f"✅ Stats loaded for week {week} ({season}). Patches: {total_patches}")


if __name__ == "__main__":
    main()
