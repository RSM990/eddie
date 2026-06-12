# src/etl/loaders/wac/injury_loader.py
from __future__ import annotations

from typing import Dict, Iterable, Optional, Any
from sqlalchemy import create_engine, MetaData, select, update
from sqlalchemy.orm import sessionmaker

from etl.loaders.base import Loader


def _val(obj: Any, *candidates: str) -> Optional[str]:
    """
    Best-effort accessor that works with dicts OR objects.
    Returns the first non-empty string-ish value across candidate names.
    """
    for name in candidates:
        if isinstance(obj, dict) and name in obj:
            v = obj[name]
        else:
            v = getattr(obj, name, None)
        if v is not None:
            return str(v)
    return None


class InjuryLoader(Loader):
    """
    Loads injury rows into Players:
      - InjuryStatus           <- normalized 1-letter/whitelisted code (strict mapping)
      - InjuryComment          <- raw text
      - InjuryPracticeStatus   <- raw/trimmed text

    Usage:
      loader = InjuryLoader(db_url)
      loader.clear_injuries()
      loader.load(rows)  # rows from your transformer
    """

    # Strict whitelist for Status. If it's not here, it becomes None.
    # All comparisons are done case-insensitively after stripping.
    _STATUS_MAP = {
        "questionable": "Q",
        "doubtful": "D",
        "out": "O",
        "probable": "P",  # if PFR ever uses it
        "suspended": "SUS",
        "injured reserve": "IR",         # per your request
        "ir": "IR",                      # safety
        "physically unable to perform": "PUP",
        "pup": "PUP",
        "non-football injury": "NFI",
        "nfi": "NFI",
        "covid-19": "COVID",             # optional, keep if you see it on the page
        # You can explicitly map "active" to None to clear it rather than store a code
        "active": None,
    }

    def __init__(self, db_url: str):
        # Match PlayerLoader: engine + session + reflected Players + preload key map
        self.engine = create_engine(db_url, fast_executemany=True)
        self.Session = sessionmaker(bind=self.engine)

        metadata = MetaData()
        metadata.reflect(bind=self.engine, only=["Players"])
        self.players = metadata.tables["Players"]

        with self.engine.connect() as conn:
            result = conn.execute(
                select(self.players.c.ProReferenceKey, self.players.c.Id)
            )
            self.existing_map: Dict[str, int] = {
                row.ProReferenceKey: row.Id for row in result
            }

    def clear_injuries(self, clearAll: bool) -> None:
        """
        Clear all three injury fields on all players before loading fresh data.
        """
        if clearAll:
            stmt = (
                update(self.players)
                .values(
                    InjuryStatus=None,
                    InjuryComment=None,
                    InjuryPracticeStatus=None,
                )
            )
            with self.engine.begin() as conn:
                conn.execute(stmt)
        else:
            # Only clear injuries for players whose InjuryStatus is not one of
            # the protected codes. Leave IR, PUP, NFI, COVID alone.
            protected = ("IR", "PUP", "NFI", "COVID")
            stmt = (
                update(self.players)
                .where(~self.players.c.InjuryStatus.in_(protected))
                .values(
                    InjuryStatus=None,
                    InjuryComment=None,
                    InjuryPracticeStatus=None,
                )
            )
            with self.engine.begin() as conn:
                conn.execute(stmt)

    def _normalize_status(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        key = raw.strip().lower()
        return self._STATUS_MAP.get(key, None)  # strict whitelist

    def _normalize_practice(self, raw: Optional[str]) -> Optional[str]:
        # Keep practice status mostly as-is but trimmed; allow None.
        if raw is None:
            return None
        txt = raw.strip()
        return txt or None

    def load(self, items: Iterable[object]) -> None:
        """
        items: iterable of rows from transformer. Each row can be a dict or an object.
          Required fields (any alias will work thanks to _val()):
            - pro_reference_key | ProReferenceKey | player_key
            - status | Status
            - comment | InjuryComment | injury_comment
            - practice_status | PracticeStatus | InjuryPracticeStatus | practice
        """
        session = self.Session()
        missing = 0
        updated = 0
        processed = 0

        for idx, r in enumerate(items, start=1):
            processed += 1

            key = _val(r, "pro_reference_key", "ProReferenceKey", "player_key")
            if not key:
                # no key → cannot match a player, skip
                continue

            player_id = self.existing_map.get(key)
            if not player_id:
                missing += 1
                if missing <= 5:
                    # log a few samples; keep quiet after
                    print(f"[injury] No player match for key={key!r}")
                continue

            raw_status = _val(r, "status", "Status")
            status = self._normalize_status(raw_status)

            comment = _val(r, "comment", "InjuryComment", "injury_comment")
            practice = _val(
                r,
                "practice_status",
                "PracticeStatus",
                "InjuryPracticeStatus",
                "practice",
            )
            practice = self._normalize_practice(practice)

            # If everything is None, skip the write
            if status is None and comment is None and practice is None:
                continue

            stmt = (
                update(self.players)
                .where(self.players.c.Id == player_id)
                .values(
                    InjuryStatus=status,
                    InjuryComment=comment,
                    InjuryPracticeStatus=practice,
                )
            )
            session.execute(stmt)
            updated += 1

            # lightweight progress
            if idx % 200 == 0:
                print(f"[injury] Updated {updated} of {idx} rows...", end="\r", flush=True)

        session.commit()
        session.close()
        print(f"[injury] Done. Updated={updated}, MissingPlayers={missing}, Processed={processed}")
