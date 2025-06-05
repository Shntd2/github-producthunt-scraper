from functools import lru_cache
from github_trending_scraper import GitHubTrendingScraper
from product_hunt_scraper import ProductHuntScraper
from config import settings
import logging

logger = logging.getLogger(__name__)


@lru_cache()
def get_scraper() -> GitHubTrendingScraper:
    return GitHubTrendingScraper(
        cache_timeout=settings.CACHE_TIMEOUT,
        max_workers=settings.MAX_WORKERS,
        request_timeout=settings.REQUEST_TIMEOUT,
        max_repositories=settings.MAX_REPOSITORIES
    )


def get_scraper_dependency() -> GitHubTrendingScraper:
    return get_scraper()

_product_hunt_scraper = None

def get_product_hunt_scraper_dependency() -> ProductHuntScraper:
    global _product_hunt_scraper
    if _product_hunt_scraper is None:
        _product_hunt_scraper = ProductHuntScraper()
    return _product_hunt_scraper
