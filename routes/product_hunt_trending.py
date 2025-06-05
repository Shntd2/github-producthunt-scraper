from fastapi import APIRouter, Query, Depends, BackgroundTasks
from typing import Optional
import logging
from datetime import datetime
import asyncio

from product_hunt_scraper import ProductHuntScraper
from dependencies import get_product_hunt_scraper_dependency

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/product-hunt",
    tags=["product-hunt"],
    responses={404: {"description": "Not found"}},
)


@router.get("/stories")
async def get_trending_stories(
        background_tasks: BackgroundTasks,
        category: Optional[str] = Query(None, description="Category filter (e.g., technology, startups, design)"),
        scraper: ProductHuntScraper = Depends(get_product_hunt_scraper_dependency)
):
    try:
        cache_key = scraper.get_cache_key(category)
        if scraper.is_cache_valid(cache_key):
            stories = scraper.cache[cache_key]['data']
            return {
                "stories": stories,
                "count": len(stories),
                "category": category,
                "updated_at": datetime.now().isoformat(),
                "cached": True
            }

        is_first_request = len(scraper.cache) == 0
        if is_first_request:
            original_max = scraper.max_stories
            scraper.max_stories = min(10, original_max)

            try:
                loop = asyncio.get_event_loop()
                stories = await asyncio.wait_for(
                    loop.run_in_executor(
                        scraper.executor,
                        scraper.get_trending_stories,
                        category
                    ),
                    timeout=3.0
                )
            finally:
                scraper.max_stories = original_max

                background_tasks.add_task(
                    fetch_full_data_background,
                    scraper,
                    category
                )
        else:
            loop = asyncio.get_event_loop()
            stories = await loop.run_in_executor(
                scraper.executor,
                scraper.get_trending_stories,
                category
            )

        return {
            "stories": stories,
            "count": len(stories),
            "category": category,
            "updated_at": datetime.now().isoformat(),
            "cached": False
        }

    except asyncio.TimeoutError:
        logger.warning("Request timed out, returning minimal data")
        minimal_stories = scraper.get_fallback_data()[:5]

        background_tasks.add_task(
            fetch_full_data_background,
            scraper,
            category
        )

        return {
            "stories": minimal_stories,
            "count": len(minimal_stories),
            "category": category,
            "updated_at": datetime.now().isoformat(),
            "partial": True,
            "message": "Partial data returned, full data is being fetched in background"
        }

    except Exception as e:
        logger.error(f"Product Hunt stories endpoint error: {e}")
        fallback_stories = scraper.get_fallback_data()
        return {
            "stories": fallback_stories,
            "count": len(fallback_stories),
            "category": category,
            "updated_at": datetime.now().isoformat(),
            "error": "Fallback data due to scraping issue"
        }


async def fetch_full_data_background(scraper: ProductHuntScraper, category: Optional[str]):
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            scraper.executor,
            scraper.get_trending_stories,
            category
        )
    except Exception as e:
        logger.error(f"Background fetch failed: {e}")

