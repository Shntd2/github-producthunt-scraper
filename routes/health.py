from fastapi import APIRouter
from datetime import datetime
from config import settings

from github_trending_scraper import GitHubTrendingScraper

router = APIRouter(
    prefix="/health",
    tags=["health"],
    responses={404: {"description": "Not found"}},
)

scraper = GitHubTrendingScraper()


@router.get("/")
async def health_check():
    cache_info = scraper.get_cache_info()

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": settings.APP_VERSION,
        "cache": cache_info
    }
