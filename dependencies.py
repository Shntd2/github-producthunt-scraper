from functools import lru_cache
from github_trending_scraper import GitHubTrendingScraper
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
