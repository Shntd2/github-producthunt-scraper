import os
from typing import List
from pydantic_settings import BaseSettings

from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "GitHub Trending Scraper"
    APP_DESCRIPTION: str = "Scrape GitHub trending repositories optimized for Glance dashboard"
    APP_VERSION: str = "2.0.0"

    HOST: str = os.getenv("HOST")
    PORT: int = int(os.getenv("PORT"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    ALLOWED_ORIGINS: List[str] = ["*"]

    CACHE_TIMEOUT: int = int(os.getenv("CACHE_TIMEOUT"))
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT"))
    MAX_REPOSITORIES: int = int(os.getenv("MAX_REPOSITORIES"))

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
