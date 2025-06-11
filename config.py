import os
from pydantic_settings import BaseSettings

from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "GitHub ProductHunt Scraper"
    APP_DESCRIPTION: str = "FastAPI-based web scraping service optimized for Glance dashboard integration. Provides trending data from GitHub and Product Hunt"
    APP_VERSION: str = "2.1"

    HOST: str = os.getenv("HOST")
    PORT: int = int(os.getenv("PORT"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

    CACHE_TIMEOUT: int = int(os.getenv("CACHE_TIMEOUT"))
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT"))
    MAX_REPOSITORIES: int = int(os.getenv("MAX_REPOSITORIES"))

    POOL_CONNECTIONS: int = int(os.getenv("POOL_CONNECTIONS"))
    POOL_MAXSIZE: int = int(os.getenv("POOL_MAXSIZE"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES"))
    POOL_BLOCK: bool = os.getenv("POOL_BLOCK", "False").lower() in ("true", "1", "yes")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
