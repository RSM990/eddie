# eddie ETL — API-mode image (no browser; scraping API handles Cloudflare, DEC-005).
# Built for Azure Container Apps Jobs alongside the v2 Azure SQL DB.
FROM python:3.11-slim

# Microsoft ODBC Driver 18 — pyodbc needs it to reach (Azure) SQL Server.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates apt-transport-https \
 && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -sSL https://packages.microsoft.com/config/debian/12/prod.list \
      | sed 's#deb #deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] #' \
      > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/

ENV PYTHONPATH=/app/src \
    FETCH_MODE=api

# DB_URL, ID_NAMESPACE, SCRAPER_PROVIDER, SCRAPER_API_KEY come from the job's env/secrets.
# The job sets the subcommand, e.g.  ["players", "--season", "2025"]
ENTRYPOINT ["python", "-m", "etl.main"]
CMD ["--help"]
