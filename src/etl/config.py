from pydantic import  HttpUrl
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    pfr_base_url: HttpUrl = "https://www.pro-football-reference.com"
    user_agent: str     = "eddie-etl-bot/1.0"
    db_url: str         # e.g. postgresql://user:pass@...
    position_list:  List[str] = [
        "QB", "RB", "WR", "TE", 
        "DL", "EDGE", "LB", "DB",
        "K", "P"
    ]
    class Config:
        env_file = ".env"
