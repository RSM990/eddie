from typing import List, Optional

TEAM_ID_MAP: dict[int, List[str]] = {
    1:  ["ARI", "CRD"],
    2:  ["ATL"],
    3:  ["BAL", "RAV"],
    4:  ["BUF"],
    5:  ["CAR"],
    6:  ["CHI"],
    7:  ["CIN"],
    8:  ["CLE"],
    9:  ["DAL"],
    10: ["DEN"],
    11: ["DET"],
    12: ["GNB"],
    13: ["HOU", "HTX"],
    14: ["IND", "CLT"],
    15: ["JAX"],
    16: ["KAN"],
    17: ["LVR", "RAI"],
    18: ["LAC", "SDG"],
    19: ["LAR", "RAM"],
    20: ["MIA"],
    21: ["MIN"],
    22: ["NWE"],
    23: ["NOR"],
    24: ["NYG"],
    25: ["NYJ"],
    26: ["PHI"],
    27: ["PIT"],
    28: ["SFO"],
    29: ["SEA"],
    30: ["TAM"],
    31: ["TEN", "OTI"],
    32: ["WAS"],
}

def translate_team_id_to_code(
    team_id: int, *, historical: bool = False
) -> Optional[str]:
    """
    Get the team code for a given NFL team_id.
    
    :param team_id: integer 1–32
    :param historical: if True, return the 2nd code (if any); else the primary (first).
    :returns: a 3‑ or 4‑letter code, or None if team_id is unknown.
    """
    codes = TEAM_ID_MAP.get(team_id)
    if not codes:
        return None
    return codes[1] if historical and len(codes) > 1 else codes[0]

def translate_team_id_to_codes(team_id: int) -> List[str]:
    """
    Get _all_ codes ever used by this franchise.
    """
    return TEAM_ID_MAP.get(team_id, [])