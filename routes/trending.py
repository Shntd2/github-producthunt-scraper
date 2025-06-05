from fastapi import APIRouter, Query, Depends
from typing import Optional
import logging
from datetime import datetime
import asyncio

from github_trending_scraper import GitHubTrendingScraper
from dependencies import get_scraper_dependency

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/trending",
    tags=["trending"],
    responses={404: {"description": "Not found"}},
)


@router.get("/")
async def get_trending(
        language: Optional[str] = Query(None, description="Programming language filter (e.g., python, javascript)"),
        since: Optional[str] = Query("daily", description="Time period: daily, weekly, or monthly"),
        scraper: GitHubTrendingScraper = Depends(get_scraper_dependency)
):

    if since and since not in ['daily', 'weekly', 'monthly']:
        since = 'daily'

    try:
        loop = asyncio.get_event_loop()
        repos = await loop.run_in_executor(
            scraper.executor,
            scraper.get_trending_repositories,
            language,
            since
        )

        return {
            "repositories": repos,
            "count": len(repos),
            "language": language,
            "since": since or "daily",
            "updated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Trending endpoint error: {e}")
        fallback_repos = scraper.get_fallback_data()
        return {
            "repositories": fallback_repos,
            "count": len(fallback_repos),
            "language": language,
            "since": since or "daily",
            "updated_at": datetime.now().isoformat(),
            "error": "Fallback data due to scraping issue"
        }
