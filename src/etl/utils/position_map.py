# src/etl/utils/position_map.py

from typing import Mapping

# Any lookup that isn’t in here will pass through unchanged.
_POSITION_TRANSLATIONS: Mapping[str, str] = {
    # fullbacks treated as RB
    "FB": "RB",
    # interior DL
    "RDT": "DL",
    "NT":  "DL",
    "LDT": "DL",
    "DT":  "DL",
    # edge rushers
    "ROLB": "EDGE",
    "RDE":  "EDGE",
    "OLB":  "EDGE",
    "LOLB": "EDGE",
    "LDE":  "EDGE",
    "DE":   "EDGE",
    # linebackers
    "RLB":  "LB",
    "RILB": "LB",
    "MLB":  "LB",
    "LLB":  "LB",
    "LILB": "LB",
    # defensive backs
    "SS":  "DB",
    "S":   "DB",
    "RCB": "DB",
    "LCB": "DB",
    "FS":  "DB",
    "CB":  "DB",
}

def normalize_position(pos: str) -> str:
    """
    Map raw PFR positions into your canonical set.
    If a position isn’t in _POSITION_TRANSLATIONS, return it unchanged.
    """
    # strip whitespace/casing
    key = pos.strip().upper()
    return _POSITION_TRANSLATIONS.get(key, key)
