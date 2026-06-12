# src/etl/transformers/nfl_injuries.py
from __future__ import annotations

from typing import List, Dict, Optional
from bs4 import BeautifulSoup, Tag

from etl.transformers.base import Transformer


class NFLInjuryTransformer(Transformer):
    """
    Transform the injuries table at
      https://www.pro-football-reference.com/players/injuries.htm
    into a list[dict] with keys:
      - pro_reference_key
      - status
      - injury_comment
      - practice_status

    The InjuryLoader will handle normalization + DB writes.
    """

    def parse(self, soup: BeautifulSoup) -> List[Dict[str, Optional[str]]]:
        table = self._find_injuries_table(soup)
        if not table:
            return []

        # Build a header map so we can fallback to header text when data-stat is missing
        header_map = self._build_header_map(table)

        out: List[Dict[str, Optional[str]]] = []
        tbody = table.find("tbody")
        if not tbody:
            return out

        for tr in tbody.find_all("tr", recursive=False):
            # Skip spacer/group header rows PFR sometimes uses
            if "class" in tr.attrs and any(c in ("thead", "stat_total", "partial_table") for c in tr["class"]):
                continue

            key = self._player_key_from_row(tr)
            if not key:
                continue

            status = self._get_cell_text(tr, ["status"], header_map, ["status"])
            comment = self._get_cell_text(
                tr,
                # common names PFR might use
                ["injury", "injury_note", "injury_comment", "detail", "note"],
                header_map,
                ["injury", "injury comment", "comment", "note"],
            )
            practice_status = self._get_cell_text(
                tr,
                ["practice_status", "practice"],
                header_map,
                ["practice", "practice status"],
            )

            out.append(
                {
                    "pro_reference_key": key,
                    "status": status,
                    "injury_comment": comment,
                    "practice_status": practice_status,
                }
            )

        return out

    # -----------------------
    # helpers
    # -----------------------

    def _find_injuries_table(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Prefer an explicit id="injuries". Fall back to any table whose id contains 'injur'.
        """
        table = soup.find("table", id="injuries")
        if table:
            return table
        # fallback: any table with id like injuries/injury_report/etc.
        for tbl in soup.find_all("table"):
            tid = tbl.get("id", "") or ""
            if "injur" in tid.lower():
                return tbl
        return None

    def _build_header_map(self, table: Tag) -> Dict[str, int]:
        """
        Returns a map of normalized header text -> column index for fallback access.
        """
        thead = table.find("thead")
        if not thead:
            return {}
        # last header row usually holds the actual column titles
        hdr_row = thead.find_all("tr")[-1]
        headers = []
        for th in hdr_row.find_all(["th", "td"], recursive=False):
            txt = (th.get_text(" ", strip=True) or "").strip().lower()
            headers.append(txt)
        return {txt: idx for idx, txt in enumerate(headers)}

    def _player_key_from_row(self, tr: Tag) -> Optional[str]:
        """
        Extract player key from the 'player' header cell (th[data-stat=player]) or first link.
        """
        # PFR usually puts player link in TH with data-stat="player"
        th_player = tr.find("th", attrs={"data-stat": "player"})
        if th_player:
            a = th_player.find("a", href=True)
            if a:
                return self._key_from_href(a["href"])

        # fallback: first link in the row that points to /players/
        a = tr.find("a", href=True)
        if a and "/players/" in a["href"]:
            return self._key_from_href(a["href"])

        return None

    def _key_from_href(self, href: str) -> Optional[str]:
        """
        '/players/B/BradTo00.htm' -> 'BradTo00'
        """
        if not href:
            return None
        last = href.rsplit("/", 1)[-1]
        return last.split(".")[0] if "." in last else None

    def _get_cell_text(
        self,
        tr: Tag,
        data_stat_candidates: List[str],
        header_map: Dict[str, int],
        header_text_candidates: List[str],
    ) -> Optional[str]:
        """
        Try to fetch a cell's text by data-stat candidates first,
        then fall back to header text position lookup.
        """
        # 1) by data-stat
        for name in data_stat_candidates:
            td = tr.find("td", attrs={"data-stat": name})
            if td:
                txt = td.get_text(" ", strip=True)
                return txt or None

        # 2) by header text position
        # Grab all cells in order, align with header_map index
        tds = tr.find_all(["td", "th"], recursive=False)
        if not tds:
            return None

        # find the first candidate header that matches header_map, use its index
        for hdr in header_text_candidates:
            idx = header_map.get(hdr)
            if idx is not None and idx < len(tds):
                txt = tds[idx].get_text(" ", strip=True)
                return txt or None

        return None
