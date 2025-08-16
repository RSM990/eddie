# src/etl/transformers/nfl_season_stats.py
from __future__ import annotations

from typing import Callable, Dict, List, Optional
import re

from bs4 import BeautifulSoup, Tag

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

PLAYER_LINK_RE = re.compile(r"^/players/[A-Z]/[\w\d]+\.htm$")

def _is_real_row(tr: Tag) -> bool:
    """Skip header/separator/total rows that don't carry player data."""
    if not isinstance(tr, Tag):
        return False
    classes = tr.get("class", [])
    if any(c in ("thead", "over_header", "spacer", "stat_total", "partial_table") for c in classes):
        return False
    has_playerish = (
        tr.find("th", attrs={"data-append-csv": True}) or
        tr.find("td", attrs={"data-append-csv": True}) or
        tr.find("a", href=PLAYER_LINK_RE)
    )
    return bool(has_playerish)

def _player_key(tr: Tag) -> Optional[str]:
    """
    Extract the PFR player key (e.g., 'BradTo00') from a season table row.
    Looks in:
      1) <th data-append-csv="KEY">
      2) <td data-append-csv="KEY">
      3) <a href="/players/X/KEY.htm">
    """
    th = tr.find("th", attrs={"data-append-csv": True})
    if th:
        key = th.get("data-append-csv")
        if key:
            return key.strip()

    td = tr.find("td", attrs={"data-append-csv": True})
    if td:
        key = td.get("data-append-csv")
        if key:
            return key.strip()

    a = tr.find("a", href=PLAYER_LINK_RE)
    if a and a.has_attr("href"):
        try:
            return a["href"].split("/")[3].split(".")[0].strip()
        except Exception:
            pass

    return None

def _cell(tr: Tag, data_stat: str) -> str:
    """Return raw text for a <td data-stat="..."> cell, or '' if missing."""
    td = tr.find("td", attrs={"data-stat": data_stat})
    return td.get_text(strip=True) if td else ""

def _int(tr: Tag, data_stat: str) -> int:
    s = _cell(tr, data_stat)
    if not s:
        return 0
    try:
        return int(s.replace(",", ""))
    except ValueError:
        return 0

def _float(tr: Tag, data_stat: str) -> float:
    s = _cell(tr, data_stat)
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0

def _int_any(tr: Tag, candidates: List[str]) -> int:
    """Try several candidate data-stat names; return first non-zero parse."""
    for name in candidates:
        val = _int(tr, name)
        if val != 0 or _cell(tr, name) != "":  # differentiate missing vs present zero
            return val
    return 0

def _float_any(tr: Tag, candidates: List[str]) -> float:
    for name in candidates:
        val = _float(tr, name)
        if val != 0.0 or _cell(tr, name) != "":
            return val
    return 0.0

# -----------------------------------------------------------------------------
# Transformer
# -----------------------------------------------------------------------------

class NFLSeasonStatsTransformer:
    """
    Turns PFR season pages into a list of patches:
      {
        "player_key": "BradTo00",
        "category": "passing" | "rushing" | "receiving" | "returns" | "scoring" | "kicking" | "defense",
        "fields": { DBColumnName: value, ... },  # season totals (NFLWeek=0, ProjectedStat=False)
      }
    """

    # PFR season pages (the extractor maps categories to URLs);
    # here we map categories to the table IDs we want to parse.
    CATEGORY_TABLE_IDS: Dict[str, str] = {
        "passing":   "passing",
        "rushing":   "rushing",
        "receiving": "receiving",
        "returns":   "returns",
        "scoring":   "scoring",
        "kicking":   "kicking",
        "defense":   "defense",   # IDP totals
    }

    CATEGORIES: List[str] = list(CATEGORY_TABLE_IDS.keys())

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def parse_all(
        self,
        year: int,
        fetch_fn: Callable[[int, str], BeautifulSoup],
    ) -> List[Dict]:
        """
        Fetch and parse all season categories for the given year.
        `fetch_fn(year, category)` must return a BeautifulSoup of that category page.
        """
        patches: List[Dict] = []
        for cat in self.CATEGORIES:
            soup = fetch_fn(int(year), cat)
            patches.extend(self.parse(soup, cat))
        return patches

    def parse(self, soup: BeautifulSoup, category: str) -> List[Dict]:
        """Parse a single category page into patches."""
        cat = category.lower().strip()
        table_id = self.CATEGORY_TABLE_IDS.get(cat)
        if not table_id:
            return []

        table = soup.find("table", id=table_id)
        tbody = table and table.find("tbody")
        if not tbody:
            return []

        out: List[Dict] = []

        for tr in tbody.find_all("tr"):
            if not _is_real_row(tr):
                continue

            key = _player_key(tr)
            if "." in key:
                key = key.split(".")[0].strip()  # e.g., "BradTo00.01" -> "BradTo00"
            if not key:
                continue

            if cat == "passing":
                out.append(self._row_passing(key, tr))
            elif cat == "rushing":
                out.append(self._row_rushing(key, tr))
            elif cat == "receiving":
                out.append(self._row_receiving(key, tr))
            elif cat == "returns":
                out.append(self._row_returns(key, tr))
            elif cat == "scoring":
                out.append(self._row_scoring(key, tr))
            elif cat == "kicking":
                out.append(self._row_kicking(key, tr))
            elif cat == "defense":
                out.append(self._row_defense(key, tr))

        return out

    # -------------------------------------------------------------------------
    # Category row parsers
    # Each returns one patch: {"player_key": key, "category": "<cat>", "fields": {...}}
    # Field names are your DB column names (PlayerStatLines)
    # -------------------------------------------------------------------------

    def _row_passing(self, key: str, tr: Tag) -> Dict:
        fields = {
            "GamesPlayed":   _int_any(tr, ["g", "games"]),
            "GamesStarted":  _int_any(tr, ["gs", "games_started"]),
            "PassYards":     _int_any(tr, ["pass_yds", "pass_yards"]),
            "Completions":   _int_any(tr, ["pass_cmp", "completions"]),
            "PassTDs":       _int_any(tr, ["pass_td", "pass_tds"]),
            "Interceptions": _int_any(tr, ["pass_int", "ints"]),
            "PassAttempts":  _int_any(tr, ["pass_att", "attempts"]),
            "QBRating":      _float_any(tr, ["pass_rating", "qbr"]),
        }
        return {"player_key": key, "category": "passing", "fields": fields}

    def _row_rushing(self, key: str, tr: Tag) -> Dict:
        fields = {
            "GamesPlayed":  _int_any(tr, ["g", "games"]),
            "GamesStarted": _int_any(tr, ["gs", "games_started"]),
            "RushAttempts": _int_any(tr, ["rush_att", "rush_attmpts", "rush_attempts"]),
            "RushYards":    _int_any(tr, ["rush_yds", "rush_yards"]),
            "RushTDs":      _int_any(tr, ["rush_td", "rush_tds"]),
            "Fumbles":      _int_any(tr, ["fumbles", "rush_fumbles"]),
            "RushAverage":  _float_any(tr, ["rush_yds_per_att", "rush_avg"]),
        }
        return {"player_key": key, "category": "rushing", "fields": fields}

    def _row_receiving(self, key: str, tr: Tag) -> Dict:
        fields = {
            "GamesPlayed":  _int_any(tr, ["g", "games"]),
            "GamesStarted": _int_any(tr, ["gs", "games_started"]),
            "Targets":      _int_any(tr, ["targets"]),
            "Receptions":   _int_any(tr, ["rec", "receptions"]),
            "RecYards":     _int_any(tr, ["rec_yds", "rec_yards"]),
            "RecTDs":       _int_any(tr, ["rec_td", "rec_tds"]),
            "Fumbles":      _int_any(tr, ["fumbles", "rec_fumbles"]),
            "RecAverage":   _float_any(tr, ["rec_yds_per_rec", "rec_avg"]),
        }
        return {"player_key": key, "category": "receiving", "fields": fields}

    def _row_returns(self, key: str, tr: Tag) -> Dict:
        # Punt returns
        pr_att = _int_any(tr, ["punt_ret", "pr"])
        pr_yds = _int_any(tr, ["punt_ret_yds", "pr_yds"])
        pr_tds = _int_any(tr, ["punt_ret_td", "pr_td", "punt_ret_tds"])

        # Kick returns
        kr_att = _int_any(tr, ["kick_ret", "kr"])
        kr_yds = _int_any(tr, ["kick_ret_yds", "kr_yds"])
        kr_tds = _int_any(tr, ["kick_ret_td", "kr_td", "kick_ret_tds"])

        fields = {
            "GamesPlayed":  _int_any(tr, ["g", "games"]),
            "GamesStarted": _int_any(tr, ["gs", "games_started"]),
            "PRAttempted":  pr_att,
            "PRYards":      pr_yds,
            "PRTDs":        pr_tds,
            "KRAttempted":  kr_att,
            "KRYards":      kr_yds,
            "KRTDs":        kr_tds,
        }
        return {"player_key": key, "category": "returns", "fields": fields}

    def _row_scoring(self, key: str, tr: Tag) -> Dict:
        # PFR scoring page has 2pt made; data-stat names vary; cover common ones.
        two_pt = _int_any(tr, ["two_pt_md", "two_pt_made", "two_pt"])
        fields = {
            "GamesPlayed":  _int_any(tr, ["g", "games"]),
            "GamesStarted": _int_any(tr, ["gs", "games_started"]),
            "TwoPointConv": two_pt,
        }
        return {"player_key": key, "category": "scoring", "fields": fields}

    def _row_kicking(self, key: str, tr: Tag) -> Dict:
        """
        Kicking has reliable overall columns (fgm/fga, xpm/xpa) and range splits.
        For range splits, data-stat names differ across years; try multiple.
        """
        fields = {
            "GamesPlayed":  _int_any(tr, ["g", "games"]),
            "GamesStarted": _int_any(tr, ["gs", "games_started"]),
            "FieldGoalsMade":       _int_any(tr, ["fgm", "fg"]),
            "FieldGoalsAttempted":  _int_any(tr, ["fga"]),
            "PATAttempted":         _int_any(tr, ["xpa"]),
            "PATMade":              _int_any(tr, ["xpm"]),
            # 1–19
            "FieldGoals1to19Attempted": _int_any(tr, ["fga_1_19", "fg1a", "fg_1_19_att"]),
            "FieldGoals1to19Made":      _int_any(tr, ["fgm_1_19", "fg1",  "fg_1_19"]),
            # 20–29
            "FieldGoals20to29Attempted": _int_any(tr, ["fga_20_29", "fg2a", "fg_20_29_att"]),
            "FieldGoals20to29Made":      _int_any(tr, ["fgm_20_29", "fg2",  "fg_20_29"]),
            # 30–39
            "FieldGoals30to39Attempted": _int_any(tr, ["fga_30_39", "fg3a", "fg_30_39_att"]),
            "FieldGoals30to39Made":      _int_any(tr, ["fgm_30_39", "fg3",  "fg_30_39"]),
            # 40–49
            "FieldGoals40to49Attempted": _int_any(tr, ["fga_40_49", "fg4a", "fg_40_49_att"]),
            "FieldGoals40to49Made":      _int_any(tr, ["fgm_40_49", "fg4",  "fg_40_49"]),
            # 50+
            "FieldGoals50PlusAttempted": _int_any(tr, ["fga_50p",   "fg5a", "fg_50+_att", "fg_50_att"]),
            "FieldGoals50PlusMade":      _int_any(tr, ["fgm_50p",   "fg5",  "fg_50+",     "fg_50"]),
        }
        return {"player_key": key, "category": "kicking", "fields": fields}

    def _row_defense(self, key: str, tr: Tag) -> Dict:
        """
        IDP season totals from defense.htm
        Covers common columns; tries multiple data-stat names per field.
        """
        fields = {
            "GamesPlayed":  _int_any(tr, ["g", "games"]),
            "GamesStarted": _int_any(tr, ["gs", "games_started"]),
            "DefensiveTD":  _int_any(tr, ["def_td", "td"]),
            "DefensiveInt": _int_any(tr, ["def_int", "int"]),
            "DefensiveIntYards": _int_any(tr, ["int_yds", "def_int_yds"]),
            "Sacks":        _int_any(tr, ["sacks", "sk"]),
            "TackleSolo":   _int_any(tr, ["tackles_solo", "solo_tkl", "solo"]),
            "TackleAssists":_int_any(tr, ["tackles_assists", "ast_tkl", "assist"]),
            "TackleForLoss":_int_any(tr, ["tackles_loss", "tfl"]),
            "ForcedFumble": _int_any(tr, ["fumbles_forced", "ff"]),
            "DefensiveFumbleRecovery": _int_any(tr, ["fumbles_rec", "fr"]),
            "FumbleYards":  _int_any(tr, ["fumbles_rec_yds", "fr_yds"]),
            "Safety":       _int_any(tr, ["safety", "sfty"]),
            "PassDefended": _int_any(tr, ["pass_defended", "passes_defended", "pd"]),
            "BlockedKick":  _int_any(tr, ["blk_kick", "blk", "blocked_kicks"]),
            "QBHit":        _int_any(tr, ["qb_hits", "qb_hit", "qbh"]),
        }
        return {"player_key": key, "category": "defense", "fields": fields}
