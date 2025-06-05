from fastapi import APIRouter, Query, Depends, BackgroundTasks
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
        background_tasks: BackgroundTasks,
        language: Optional[str] = Query(None, description="Programming language filter (e.g., python, javascript)"),
        since: Optional[str] = Query("daily", description="Time period: daily, weekly, or monthly"),
        scraper: GitHubTrendingScraper = Depends(get_scraper_dependency)
):
    if since and since not in ['daily', 'weekly', 'monthly']:
        since = 'daily'

    try:
        cache_key = scraper.get_cache_key(language, since)
        if scraper.is_cache_valid(cache_key):
            repos = scraper.cache[cache_key]['data']
            return {
                "repositories": repos,
                "count": len(repos),
                "language": language,
                "since": since or "daily",
                "updated_at": datetime.now().isoformat(),
                "cached": True
            }

        is_first_request = len(scraper.cache) == 0
        if is_first_request:
            original_max = scraper.max_repositories
            scraper.max_repositories = min(10, original_max)

            try:
                loop = asyncio.get_event_loop()
                repos = await asyncio.wait_for(
                    loop.run_in_executor(
                        scraper.executor,
                        scraper.get_trending_repositories,
                        language,
                        since
                    ),
                    timeout=3.0
                )
            finally:
                scraper.max_repositories = original_max

                background_tasks.add_task(
                    fetch_full_data_background,
                    scraper,
                    language,
                    since
                )
        else:
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
            "updated_at": datetime.now().isoformat(),
            "cached": False
        }

    except asyncio.TimeoutError:
        logger.warning("Request timed out, returning minimal data")
        minimal_repos = scraper.get_fallback_data()[:5]

        background_tasks.add_task(
            fetch_full_data_background,
            scraper,
            language,
            since
        )

        return {
            "repositories": minimal_repos,
            "count": len(minimal_repos),
            "language": language,
            "since": since or "daily",
            "updated_at": datetime.now().isoformat(),
            "partial": True,
            "message": "Partial data returned, full data is being fetched in background"
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


async def fetch_full_data_background(scraper: GitHubTrendingScraper, language: Optional[str], since: Optional[str]):
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            scraper.executor,
            scraper.get_trending_repositories,
            language,
            since
        )
    except Exception as e:
        logger.error(f"Background fetch failed: {e}")
