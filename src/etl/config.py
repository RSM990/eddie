from uuid import UUID

from pydantic import  HttpUrl
from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    pfr_base_url: HttpUrl = "https://www.pro-football-reference.com"
    user_agent: str     = "eddie-etl-bot/1.0"
    db_url: str         # SQLAlchemy URL for the v2 DB (mssql+pyodbc://eddie_etl:...@host/TheWAC_v2)
    # Fixed UUID namespace for uuid5(namespace, ProReferenceKey) on new players.
    # Read from ID_NAMESPACE; must stay constant forever (changing it re-IDs every rookie).
    id_namespace: UUID

    # How to fetch Cloudflare-gated PFR pages (DEC-005):
    #   "api"     -> scraping API (default; cloud/Azure-friendly, no browser needed)
    #   "browser" -> real Chrome via SeleniumFetcher (local dev / attached session)
    fetch_mode: str = "api"
    # Scraping-API settings (used when fetch_mode == "api").
    scraper_provider: str = "scraperapi"        # scraperapi | zenrows | scrapingbee
    scraper_api_key: Optional[str] = None
    scraper_render_js: bool = True              # render JS / solve the Cloudflare challenge
    scraper_timeout: float = 90.0               # API calls with a full render are slow

    position_list:  List[str] = [
        "QB", "RB", "WR", "TE", 
        "DL", "EDGE", "LB", "DB",
        "K", "P"
    ]
    class Config:
        env_file = ".env"
