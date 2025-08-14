from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, Any

class PlayerWeekStatPatch(BaseModel):
    """
    A patch (partial set) of stats for a single player in a single week.
    Keys in `fields` must match your PlayerStatLines column names.
    """
    pro_reference_key: str  # e.g. 'BradTo00'
    fields: Dict[str, Any]
