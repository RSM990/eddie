# src/etl/utils/dates.py
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Optional

_AMPM_RE = re.compile(r'(?i)\b([AP])\.?\s*M\.?\b')  # A M / A.M. / AM / p m / etc.

def parse_pfr_kickoff(date_yyyymmdd: str, time_text: str) -> Optional[datetime]:
    """
    Robustly parse PFR kickoff times like:
      '8:20 PM', '9:30 AM ET', '1:00 p.m.', '8:20 PM†', 'TBD'
    Returns naive datetime in local ET (per PFR), or None if not parseable.
    """
    if not time_text:
        return None

    # Normalize unicode (NFKC) and trim
    s = unicodedata.normalize("NFKC", time_text).strip()

    # Drop trailing timezone/footnotes, e.g. ' ET', ' PT', '†', '‡', '*'
    s = re.sub(r'\s+(ET|CT|MT|PT)\b.*$', '', s, flags=re.I)
    s = s.rstrip('†‡* ')  # common footnote glyphs

    # Replace any weird unicode spaces with normal space
    s = s.replace('\u00A0', ' ').replace('\u202F', ' ').strip()

    # Quick out
    if not s or s.upper() == "TBD":
        return None

    # Normalize AM/PM variants -> 'AM'/'PM'
    s = _AMPM_RE.sub(lambda m: f"{m.group(1).upper()}M", s)

    # Now try strict parse: H:MM AM/PM
    # Accept optional spaces around colon to be extra safe
    m = re.search(r'^\s*(\d{1,2})\s*:\s*(\d{2})\s*([AP]M)\s*$', s, flags=re.I)
    if not m:
        # One last attempt: sometimes they omit the space: '8:20PM'
        m = re.search(r'^\s*(\d{1,2})\s*:\s*(\d{2})\s*([AP]M)\s*$', s.replace(' ', ''), flags=re.I)

    if not m:
        return None

    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3).upper()

    try:
        return datetime.strptime(f"{date_yyyymmdd} {hour:01d}:{minute:02d} {ampm}", "%Y%m%d %I:%M %p")
    except ValueError:
        # Extremely defensive: fall back to a looser pattern or give up
        return None
