from __future__ import annotations

from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Union, Iterable
import re

from etl.transformers.base import Transformer
from models.stats import PlayerWeekStatPatch


def _safe_int(s: str) -> int:
    s = (s or "").strip().replace(",", "")
    return int(s) if s and re.fullmatch(r"-?\d+", s) else 0

def _safe_float(s: str) -> float:
    s = (s or "").strip().replace(",", "")
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0

def _get_table(soup: BeautifulSoup, table_id: str):
    return soup.find("table", id=table_id)

def _first_number(text: str) -> Optional[int]:
    m = re.search(r"(\d+)", text or "")
    return int(m.group(1)) if m else None

def _merge_add(existing: Optional[Dict[str, int]], new: Dict[str, int]) -> Dict[str, int]:
    if not existing:
        return dict(new)
    merged = dict(existing)
    for k, v in new.items():
        merged[k] = merged.get(k, 0) + (v or 0)
    return merged

def _td_text_by_names(row, names: Iterable[str]) -> str:
    """Return the first matching td text for any of the provided data-stat names."""
    for n in names:
        td = row.find("td", {"data-stat": n})
        if td:
            return td.get_text(strip=True)
    return ""


class NFLStatsTransformer(Transformer):
    """
    Abstract-interface compliant transformer:
      - Public API: parse(doc) -> List[PlayerWeekStatPatch]
      - Private helper: _parse_boxscore(soup)
    """

    def parse(self, doc: Union[BeautifulSoup, str]) -> List[PlayerWeekStatPatch]:
        if isinstance(doc, BeautifulSoup):
            soup = doc
        elif isinstance(doc, str):
            soup = BeautifulSoup(doc, "html.parser")
        else:
            raise TypeError("NFLStatsTransformer.parse expects BeautifulSoup or HTML string")
        return self._parse_boxscore(soup)

    def _parse_boxscore(self, soup: BeautifulSoup) -> List[PlayerWeekStatPatch]:
        patches: Dict[str, Dict[str, int]] = {}

        # ---- OFFENSE ----
        off = _get_table(soup, "player_offense")
        if off and off.tbody:
            for row in off.tbody.find_all("tr"):
                th = row.find("th")
                a = th.find("a", href=True) if th else None
                if not a:
                    continue
                key = a["href"].split("/")[3].split(".")[0]

                fields = {
                    "PassAttempts": _safe_int(_td_text_by_names(row, ["pass_att"])),
                    "Completions":  _safe_int(_td_text_by_names(row, ["pass_cmp"])),
                    "PassYards":    _safe_int(_td_text_by_names(row, ["pass_yds"])),
                    "PassTDs":      _safe_int(_td_text_by_names(row, ["pass_td"])),
                    "Interceptions":_safe_int(_td_text_by_names(row, ["pass_int"])),
                    "RushYards":    _safe_int(_td_text_by_names(row, ["rush_yds"])),
                    "RushAttempts": _safe_int(_td_text_by_names(row, ["rush_att"])),
                    "RushTDs":      _safe_int(_td_text_by_names(row, ["rush_td"])),
                    "Targets":      _safe_int(_td_text_by_names(row, ["targets"])),
                    "Receptions":   _safe_int(_td_text_by_names(row, ["rec"])),
                    "RecYards":     _safe_int(_td_text_by_names(row, ["rec_yds"])),
                    "RecTDs":       _safe_int(_td_text_by_names(row, ["rec_td"])),
                    "Fumbles":      _safe_int(_td_text_by_names(row, ["fumbles_lost"])),
                }
                patches[key] = _merge_add(patches.get(key), fields)

        # ---- SCORING (FG bins) ----
        scoring = _get_table(soup, "scoring")
        if scoring and scoring.tbody:
            for row in scoring.tbody.find_all("tr"):
                tds = row.find_all("td")
                if len(tds) >= 3:
                    desc = tds[2]
                    txt = desc.get_text(" ", strip=True).lower()
                    if "field goal" in txt:
                        a = desc.find("a", href=True)
                        if not a:
                            continue
                        key = a["href"].split("/")[3].split(".")[0]
                        dist = _first_number(desc.get_text(" ", strip=True))
                        if dist is None:
                            continue

                        fg_fields = {}
                        if dist < 20:
                            fg_fields["FieldGoals1to19Made"] = 1
                        elif 20 <= dist < 30:
                            fg_fields["FieldGoals20to29Made"] = 1
                        elif 30 <= dist < 40:
                            fg_fields["FieldGoals30to39Made"] = 1
                        elif 40 <= dist < 50:
                            fg_fields["FieldGoals40to49Made"] = 1
                        else:
                            fg_fields["FieldGoals50PlusMade"] = 1

                        patches[key] = _merge_add(patches.get(key), fg_fields)

        # ---- KICKING (PAT made) ----
        kicking = _get_table(soup, "kicking")
        if kicking and kicking.tbody:
            for row in kicking.tbody.find_all("tr"):
                th = row.find("th")
                a = th.find("a", href=True) if th else None
                if not a:
                    continue
                key = a["href"].split("/")[3].split(".")[0]
                xpm = _safe_int(_td_text_by_names(row, ["xpm", "xpmade"]))
                if xpm:
                    patches[key] = _merge_add(patches.get(key), {"PATMade": xpm})

        # ---- RETURNS (KR/PR) ----
        returns = _get_table(soup, "returns")
        if returns and returns.tbody:
            for row in returns.tbody.find_all("tr"):
                th = row.find("th")
                a = th.find("a", href=True) if th else None
                if not a:
                    continue
                key = a["href"].split("/")[3].split(".")[0]
                fields = {
                    "KRYards": _safe_int(_td_text_by_names(row, [ "kr_yds","kick_ret_yds"])),
                    "KRTDs":   _safe_int(_td_text_by_names(row, ["kr_td", "kick_ret_td"])),
                    "PRYards": _safe_int(_td_text_by_names(row, ["pr_yds", "punt_ret_yds"])),
                    "PRTDs":   _safe_int(_td_text_by_names(row, ["pr_td", "punt_ret_td"])),
                }
                patches[key] = _merge_add(patches.get(key), fields)

        # ---- DEFENSE (IDP) ----
        # Map PFR data-stat names (which can vary slightly) to your PlayerStatLine fields.
        defense = _get_table(soup, "player_defense")
        if defense and defense.tbody:
            for row in defense.tbody.find_all("tr"):
                th = row.find("th")
                a = th.find("a", href=True) if th else None
                if not a:
                    continue
                key = a["href"].split("/")[3].split(".")[0]

                # Flexible fetches for columns that sometimes change labels
                solo_tk   = _safe_int(_td_text_by_names(row, ["tkl", "tackles_solo", "tackles"]))
                ast_tk    = _safe_int(_td_text_by_names(row, ["ast", "tackles_assist", "tackles_assists"]))
                tfl       = _safe_int(_td_text_by_names(row, ["tfl", "tackle_for_loss", "tackles_loss"]))
                qb_hit    = _safe_int(_td_text_by_names(row, ["qb_hit", "qb_hits"]))
                pd        = _safe_int(_td_text_by_names(row, ["pd", "pass_defended", "pass_defendeds"]))

                ff        = _safe_int(_td_text_by_names(row, ["fumbles_forced", "ff"]))
                fr        = _safe_int(_td_text_by_names(row, ["fumbles_rec", "fr"]))
                fr_yds    = _safe_int(_td_text_by_names(row, ["fumbles_rec_yds", "fumble_yds", "fumbles_rec_yards"]))

                # Interceptions and yards
                d_int     = _safe_int(_td_text_by_names(row, ["int", "def_int"]))
                int_yds   = _safe_int(_td_text_by_names(row, ["int_yds", "def_int_yds"]))

                # Touchdowns — PFR may split between INT TD and Fumble Return TD
                int_td    = _safe_int(_td_text_by_names(row, ["int_td", "def_int_td"]))
                fr_td     = _safe_int(_td_text_by_names(row, ["fumbles_rec_td", "fr_td"]))
                misc_td   = _safe_int(_td_text_by_names(row, ["def_td", "td"]))  # sometimes a generic 'def_td' or 'td'
                def_td    = int_td + fr_td + misc_td

                # Sacks can be fractional on PFR; your DB uses int -> round to nearest int
                sacks     = _safe_float(_td_text_by_names(row, ["sk", "sacks"]))

                safety    = _safe_int(_td_text_by_names(row, ["sfty", "safety"]))
                blk_kick  = _safe_int(_td_text_by_names(row, ["blk_kick", "blk"]))
                d2pt      = _safe_int(_td_text_by_names(row, ["def_two_pt", "def_2pt", "two_pt_def", "two_pt_defense"]))
                d1pt      = _safe_int(_td_text_by_names(row, ["def_one_pt", "def_1pt", "one_pt_def"]))  # rarely present

                fields = {
                    "TackleSolo":               solo_tk,
                    "TackleAssists":            ast_tk,
                    "TackleForLoss":            tfl,
                    "QBHit":                    qb_hit,
                    "PassDefended":             pd,
                    "ForcedFumble":             ff,
                    "DefensiveFumbleRecovery":  fr,
                    "FumbleYards":              fr_yds,
                    "DefensiveInt":             d_int,
                    "DefensiveIntYards":        int_yds,
                    "DefensiveTD":              def_td,
                    "Sacks":                    sacks,
                    "Safety":                   safety,
                    "BlockedKick":              blk_kick,
                    "Defensive2PtReturn":       d2pt,
                    "Defensive1PtReturn":       d1pt,
                }
                # Strip zeroes to reduce noise (optional)
                fields = {k: v for k, v in fields.items() if v}
                if fields:
                    patches[key] = _merge_add(patches.get(key), fields)

        return [PlayerWeekStatPatch(pro_reference_key=k, fields=v) for k, v in patches.items()]
