#!/usr/bin/env python
"""
eddie ETL command-line entry point.

Subcommands replace the old boolean-toggle main(). Run with src on the path:

    PYTHONPATH=src python -m etl.main draft   --season 2026
    PYTHONPATH=src python -m etl.main players --season 2025

or directly (this file adds src/ to sys.path itself):

    python src/etl/main.py draft --season 2026

Both PFR-scraping commands drive a real browser (PFR is Cloudflare-gated): launch
Chrome with --remote-debugging-port and export CHROME_DEBUGGER_ADDRESS first —
see etl/utils/selenium_client.py. Commands COMMIT by default; pass --dry-run to
roll back (scrape + load, then discard — useful for verifying before a real run).
"""
from __future__ import annotations

import argparse
import os
import sys

# Allow `python src/etl/main.py ...` without setting PYTHONPATH: put src/ on path.
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from etl.config import Settings
from etl.extractors.pfr.draft import PFRDraftExtractor
from etl.transformers.nfl_draft import NFLDraftTransformer
from etl.extractors.pfr.roster import PFRRosterExtractor
from etl.transformers.nfl_roster import NFLRosterTransformer
from etl.loaders.wac.player_loader import PlayerLoader, IDP_POSITIONS
from etl.utils.teams import translate_team_id_to_code


def _parse_team_ids(teams: str, max_teams: int) -> list[int]:
    """Comma list of team ids (default all 1-32), optionally capped for a smoke run."""
    ids = [int(t) for t in teams.split(",") if t.strip()] if teams else list(range(1, 33))
    if max_teams:
        ids = ids[:max_teams]
    return ids


def _trim_draft_table(soup, limit: int) -> int:
    """Drop all but the first `limit` pick rows from the draft table (for smoke runs)."""
    table = soup.find("table", id="drafts") or soup.find_all("table")[0]
    tbody = table.find("tbody")
    kept = 0
    for row in list(tbody.find_all("tr")):
        if row.find_all("td"):
            if kept >= limit:
                row.decompose()
                continue
            kept += 1
    return kept


def run_draft(settings: Settings, season: int, limit: int, commit: bool) -> None:
    """Reset rookie flags and load a draft class — atomically, in one transaction."""
    extractor = PFRDraftExtractor(settings)
    transformer = NFLDraftTransformer(settings)
    loader = PlayerLoader(settings.db_url, settings.id_namespace)

    print(f"Fetching {season} draft index...")
    soup = extractor.fetch(season)
    if limit and limit > 0:
        print(f"Trimmed to first {_trim_draft_table(soup, limit)} pick rows.")
    print("Scraping per-player pages (rate-limited ~18/min)...")
    picks = transformer.parse(soup, season)
    print(f"Parsed {len(picks)} picks.")

    conn = loader.engine.connect()
    txn = conn.begin()
    try:
        # Reset + load in one transaction: a mid-run failure can't strand the
        # prior class cleared and the new one unloaded.
        loader.reset_rookie_flags(conn=conn)
        ins, upd = loader._load(conn, picks)
        if commit:
            txn.commit()
        else:
            txn.rollback()
    except Exception:
        txn.rollback()
        raise
    finally:
        conn.close()

    idp = sum(1 for p in picks if p.position in IDP_POSITIONS)
    unresolved = sum(1 for p in picks if p.nfl_team_id not in loader.team_map)
    state = "COMMITTED" if commit else "rolled back (dry run)"
    print(f"draft {season}: inserted={ins}, updated={upd}, IDP={idp}, "
          f"unresolved_team={unresolved} [{state}]")


def run_players(settings: Settings, season: int, team_ids: list[int], commit: bool) -> None:
    """Refresh the Player universe from team rosters; per-team clear+upsert is atomic."""
    extractor = PFRRosterExtractor(settings)
    transformer = NFLRosterTransformer(settings)
    loader = PlayerLoader(settings.db_url, settings.id_namespace)

    tot_ins = tot_upd = tot_rows = 0
    for team_id in team_ids:
        # PFR uses franchise-specific codes (CRD, RAV, …) — the "historical" code.
        code = translate_team_id_to_code(team_id, historical=True).lower()
        soup = extractor.fetch(season, code)
        roster = transformer.parse(soup, team_id)

        conn = loader.engine.connect()
        txn = conn.begin()
        try:
            loader.clear_team(team_id, conn=conn)
            ins, upd = loader._load(conn, roster)
            if commit:
                txn.commit()
            else:
                txn.rollback()
        except Exception:
            txn.rollback()
            raise
        finally:
            conn.close()

        tot_ins += ins
        tot_upd += upd
        tot_rows += len(roster)
        print(f"  team {team_id:>2} ({code}): {len(roster):>3} players (+{ins} new / ~{upd} updated)")

    state = "COMMITTED" if commit else "rolled back (dry run)"
    print(f"players {season}: {tot_rows} roster rows over {len(team_ids)} team(s), "
          f"inserted={tot_ins}, updated={tot_upd} [{state}]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eddie", description="eddie sports-data ETL")
    sub = parser.add_subparsers(dest="command", required=True)

    p_draft = sub.add_parser("draft", help="Load a rookie draft class into v2 Players (resets rookie flags first).")
    p_draft.add_argument("--season", type=int, required=True, help="Draft year, e.g. 2026")
    p_draft.add_argument("--limit", type=int, default=0, help="Scrape only the first N picks (0 = all).")
    p_draft.add_argument("--dry-run", action="store_true", help="Scrape + load, then roll back (no writes).")

    p_players = sub.add_parser("players", help="Refresh the v2 Player universe from team rosters.")
    p_players.add_argument("--season", type=int, required=True, help="Season year, e.g. 2025")
    p_players.add_argument("--teams", default="", help="Comma list of team ids 1-32 (default: all).")
    p_players.add_argument("--max-teams", type=int, default=0, help="Cap number of teams (smoke). 0 = no cap.")
    p_players.add_argument("--dry-run", action="store_true", help="Scrape + load, then roll back (no writes).")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    commit = not args.dry_run

    if args.command == "draft":
        run_draft(settings, args.season, args.limit, commit)
    elif args.command == "players":
        run_players(settings, args.season, _parse_team_ids(args.teams, args.max_teams), commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
