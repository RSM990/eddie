# src/etl/shared/db.py
from __future__ import annotations

from typing import Optional
from urllib.parse import quote_plus

def build_db_url_if_needed(raw: Optional[str]) -> str:
    """
    Accepts either:
      - a full SQLAlchemy URL (e.g., 'mssql+pyodbc:///?odbc_connect=...')
      - a bare ODBC connection string from .NET/pyodbc (e.g., 'Driver={ODBC Driver 18 for SQL Server};Server=...')

    Returns a SQLAlchemy URL suitable for create_engine().
    """
    if not raw:
        raise ValueError("No database URL/connection string provided.")

    s = raw.strip()

    # If it already looks like a SQLAlchemy URL, just return it.
    # (e.g., 'mssql+pyodbc://...', 'postgresql+psycopg2://...', etc.)
    if "://" in s and not s.lower().startswith("driver="):
        return s

    # Otherwise treat it as a raw ODBC connection string and wrap it.
    # Example input:
    #   Driver={ODBC Driver 18 for SQL Server};Server=tcp:host,1433;Database=DB;UID=sa;PWD=***;Encrypt=yes;TrustServerCertificate=no;
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(s)}"
