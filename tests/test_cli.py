"""
CLI surface tests (Phase 4.75, Sprint 4) — argument parsing and pure helpers.

These don't touch PFR or the DB; the scrape/load behavior is covered by the
loader tests. They guard the subcommand wiring and the team-id / draft-trim
helpers that replaced the old boolean-toggle main().
"""
from __future__ import annotations

import pytest

from etl.main import build_parser, _parse_team_ids


def test_draft_defaults_to_commit():
    args = build_parser().parse_args(["draft", "--season", "2026"])
    assert args.command == "draft"
    assert args.season == 2026
    assert args.limit == 0
    assert args.dry_run is False  # commits unless --dry-run


def test_players_dry_run_flag():
    args = build_parser().parse_args(["players", "--season", "2025", "--dry-run"])
    assert args.command == "players"
    assert args.dry_run is True


def test_subcommand_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_season_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["draft"])


def test_parse_team_ids_default_is_all():
    assert _parse_team_ids("", 0) == list(range(1, 33))


def test_parse_team_ids_explicit_list():
    assert _parse_team_ids("1,5,9", 0) == [1, 5, 9]


def test_parse_team_ids_max_caps():
    assert _parse_team_ids("", 3) == [1, 2, 3]
    assert _parse_team_ids("10,11,12,13", 2) == [10, 11]
