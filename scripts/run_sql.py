"""Run a .sql script against the v2 DB via pyodbc (msodbcsql18).

Avoids the go-sqlcmd negative-serial TLS bug and needs no mssql-tools package —
it uses the same ODBC driver eddie connects with, so a successful run also
confirms eddie's connection path works.

Splits the script on `GO` batch separators (a sqlcmd-ism, not valid T-SQL),
and runs each batch with autocommit so DDL/GRANTs commit.

Usage (from the eddie repo, inside the venv):
    ADMIN_DB_URL='DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;UID=sa;PWD=TheWAC@Dev123!;TrustServerCertificate=yes;' \\
        python scripts/run_sql.py scripts/eddie_etl.sql

Use the SA connection for admin scripts (CREATE LOGIN needs sysadmin).
ADMIN_DB_URL is read from the environment so no password is committed.
"""
import os
import re
import sys

import pyodbc

GO = re.compile(r"(?im)^\s*GO\s*$")


def main(path: str) -> None:
    conn_str = os.environ.get("ADMIN_DB_URL")
    if not conn_str:
        sys.exit("Set ADMIN_DB_URL (ODBC connection string) in the environment.")

    with open(path, encoding="utf-8") as f:
        script = f.read()

    batches = [b.strip() for b in GO.split(script) if b.strip()]

    conn = pyodbc.connect(conn_str, autocommit=True)
    cur = conn.cursor()
    try:
        for i, batch in enumerate(batches, 1):
            cur.execute(batch)
            print(f"batch {i}/{len(batches)}: ok")
    finally:
        conn.close()
    print("done.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "scripts/eddie_etl.sql")
