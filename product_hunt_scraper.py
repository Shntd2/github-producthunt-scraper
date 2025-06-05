import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import socket
import asyncio
from functools import lru_cache


# Placeholder for settings if config.py is not available. remove it
class SettingsMock:
    CACHE_TIMEOUT = 3600
    MAX_WORKERS = 5
    REQUEST_TIMEOUT = 15
    MAX_REPOSITORIES = 25
    POOL_CONNECTIONS = 10
    POOL_MAXSIZE = 10
    MAX_RETRIES = 3
    POOL_BLOCK = False


settings = SettingsMock()  # REPLACE with actual settings import

logger = logging.getLogger(__name__)


class ProductHuntScraper:
    BASE_URL = "https://www.producthunt.com/stories?ref=header_nav"

    WHITESPACE_PATTERN = re.compile(r'\s+')
    NUMBER_PATTERN = re.compile(r'\d+')

    def __init__(self,
                 cache_timeout: int = settings.CACHE_TIMEOUT,
                 max_workers: int = settings.MAX_WORKERS,
                 request_timeout: int = settings.REQUEST_TIMEOUT,
                 max_stories: int = settings.MAX_REPOSITORIES):

        self.session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=settings.POOL_CONNECTIONS,
            pool_maxsize=settings.POOL_MAXSIZE,
            max_retries=settings.MAX_RETRIES,
            pool_block=settings.POOL_BLOCK
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        self.cache = {}
        self.cache_timeout = cache_timeout
        self.request_timeout = request_timeout
        self.max_stories = max_stories

        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        self._pre_resolve_domain()

    def _pre_resolve_domain(self):
        try:
            socket.gethostbyname('producthunt.com')
        except socket.gaierror:
            logger.warning("Failed to pre-resolve domain producthunt.com")
        except Exception:
            logger.warning("An unexpected error occurred during pre-resolve domain.")

    @staticmethod
    def get_cache_key(category: Optional[str] = None) -> str:
        return f"stories_{category or 'all'}"

    def is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self.cache:
            return False

        cached_time = self.cache[cache_key].get('timestamp')
        if not cached_time:
            return False

        return (datetime.now() - cached_time).total_seconds() < self.cache_timeout

    def get_trending_stories(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        cache_key = self.get_cache_key(category)

        if self.is_cache_valid(cache_key):
            logger.info(f"Returning cached data for key: {cache_key}")
            return self.cache[cache_key]['data']

        logger.info(f"Fetching fresh data for key: {cache_key}")
        try:
            url = self.BASE_URL
            params = {}

            if category:
                params['category'] = category

            response = self.session.get(
                url,
                params=params,
                timeout=self.request_timeout,
                stream=True
            )
            response.raise_for_status()

            content = response.content

            try:
                soup = BeautifulSoup(content, 'lxml')
            except Exception:
                soup = BeautifulSoup(content, 'html.parser')

            stories = []

            story_articles = soup.find_all('div', attrs={'data-test': re.compile(r'story-item-\d+')})

            if not story_articles:
                story_articles = soup.find_all('div', class_=re.compile(r'styles_item__\w+'))

            for article in story_articles[:self.max_stories]:
                story_data = self._extract_story_data(article)
                if story_data:
                    stories.append(story_data)

            self.cache[cache_key] = {
                'data': stories,
                'timestamp': datetime.now()
            }
            return stories

        except requests.RequestException as e:
            logger.error(f"Request failed for {cache_key}: {e}")
            if cache_key in self.cache:
                logger.warning(f"Returning expired cache for {cache_key} due to request failure")
                return self.cache[cache_key]['data']
            return self.get_fallback_data()

        except Exception as e:
            logger.error(f"Scraping failed for {cache_key}: {e}", exc_info=True)
            if cache_key in self.cache:
                logger.warning(f"Returning cached data for {cache_key} due to scraping failure")
                return self.cache[cache_key]['data']
            return self.get_fallback_data()

    def _extract_story_data(self, article: BeautifulSoup) -> Optional[Dict[str, Any]]:
        try:
            story_data = {}

            story_id_match = re.search(r'story-item-(\d+)', article.get('data-test', ''))
            if story_id_match:
                story_data['story_id'] = story_id_match.group(1)
            else:
                story_data['story_id'] = None

            title_elem = article.find('div', class_=re.compile(r'text-18.*font-bold'))
            if not title_elem:
                logger.debug(f"Skipping item, title element not found. Data-test: {story_data.get('story_id', 'N/A')}")
                return None
            story_data['title'] = self.WHITESPACE_PATTERN.sub(' ', title_elem.get_text().strip())

            url_tag = title_elem.find_parent('a', href=re.compile(r'^/stories/[^/]+'))
            if url_tag and '/category/' not in url_tag.get('href', ''):
                story_data['url'] = f"https://www.producthunt.com{url_tag.get('href')}"
            else:
                potential_links = article.find_all('a', href=re.compile(r'^/stories/[^/]+'))
                found_url = None
                for link in potential_links:
                    href = link.get('href', '')
                    if '/category/' not in href:
                        found_url = f"https://www.producthunt.com{href}"
                        break
                story_data['url'] = found_url if found_url else ''

            if not story_data.get('url'):
                logger.warning(f"Could not extract URL for story: {story_data['title']}")

            meta_info_elem = article.find('div', class_=re.compile(r'text-12.*text-light-gray'))
            author_name = "Unknown"
            author_url = None
            category_name = None
            read_time_val = None

            if meta_info_elem:
                author_link_elem = meta_info_elem.find('a', href=re.compile(r'linkedin\.com|twitter\.com|github\.com',
                                                                            re.IGNORECASE))
                if not author_link_elem:
                    author_link_elem = meta_info_elem.find('a', href=True)

                if author_link_elem:
                    author_name = author_link_elem.get_text().strip()
                    author_url = author_link_elem.get('href', '')
                    if author_url.startswith('/@'):
                        author_url = f"https://www.producthunt.com{author_url}"
                else:
                    text_content = meta_info_elem.get_text(separator='|').strip()
                    parts = [p.strip() for p in text_content.split('|') if p.strip()]
                    if parts:
                        potential_author_part = parts[0]
                        if not any(kw in potential_author_part.lower() for kw in ['min read', 'comment', 'launch']):
                            author_name = potential_author_part

                category_elem = meta_info_elem.find('a', href=re.compile('/stories/category/'))
                if category_elem:
                    category_name = category_elem.get_text().strip()

                text_content_for_read_time = meta_info_elem.get_text()
                read_time_match = re.search(r'(\d+)\s*min\s*read', text_content_for_read_time)
                if read_time_match:
                    read_time_val = int(read_time_match.group(1))

            story_data['author'] = author_name
            story_data['author_url'] = author_url
            story_data['category'] = category_name
            story_data['read_time'] = read_time_val

            img_elem = article.find('img', class_=re.compile(r'styles_headerImage__\w*'))
            if img_elem:
                story_data['thumbnail_url'] = img_elem.get('src')
                if not story_data['thumbnail_url'] and img_elem.get('srcset'):
                    srcset = img_elem.get('srcset', '')
                    story_data['thumbnail_url'] = srcset.split(' ')[0] if srcset else None
            else:
                story_data['thumbnail_url'] = None

            story_data['tags'] = [story_data['category']] if story_data.get('category') else []
            story_data['upvotes'] = 0
            story_data['published_at'] = None
            story_data['description'] = ""

            return story_data

        except Exception as e:
            logger.error(
                f"Error extracting story data for item (Story ID: {story_data.get('story_id', 'N/A')} Title: {story_data.get('title', 'N/A')}): {e}",
                exc_info=True)
            return None

    def parse_number(self, text: str) -> int:
        if not text:
            return 0
        text = str(text).strip().replace(',', '')
        if text.isdigit():
            return int(text)
        text_lower = text.lower()
        if text_lower.endswith('k'):
            try:
                return int(float(text_lower[:-1]) * 1000)
            except ValueError:
                pass
        elif text_lower.endswith('m'):
            try:
                return int(float(text_lower[:-1]) * 1000000)
            except ValueError:
                pass
        numbers = self.NUMBER_PATTERN.findall(text)
        return int(numbers[0]) if numbers else 0

    @staticmethod
    def get_fallback_data() -> List[Dict[str, Any]]:
        return [
            {
                "title": "Product Hunt Stories Unavailable",
                "url": "https://www.producthunt.com/stories",
                "description": "Product Hunt stories data is temporarily unavailable. Please try again later.",
                "author": "Product Hunt",
                "author_url": None,
                "category": None,
                "published_at": datetime.now().isoformat(),
                "read_time": 0,
                "tags": [],
                "thumbnail_url": None,
                "upvotes": 0,
                "story_id": None
            }
        ]

    def get_cache_info(self) -> Dict[str, Any]:
        return {
            "cached_entries": len(self.cache),
            "cache_keys": list(self.cache.keys()),
            "cache_details": {
                key: {
                    "timestamp": value.get('timestamp').isoformat() if value.get('timestamp') else None,
                    "size": len(value.get('data', []))
                } for key, value in self.cache.items()
            }
        }

    async def warm_cache(self):
        common_queries = [
            None,
            'makers',
            'product-updates',
            'how-tos'
            # Add more relevant category slugs
        ]
        logger.info(f"Starting cache warming for {len(common_queries)} queries.")

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.warning(
                    "warm_cache called outside of a running asyncio event loop. Tasks may not run as expected.")
                for category in common_queries:
                    self.executor.submit(self.get_trending_stories, category)
                logger.info(f"Cache warming tasks submitted synchronously to ThreadPoolExecutor.")
                return

            tasks = []
            for category in common_queries:
                task = loop.run_in_executor(
                    self.executor,
                    self.get_trending_stories,
                    category
                )
                tasks.append(task)

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                successful = sum(1 for r in results if isinstance(r, list) and not (len(r) == 1 and r[0].get(
                    "title") == "Product Hunt Stories Unavailable"))
                failed = len(results) - successful
                logger.info(
                    f"Cache warming completed: {successful}/{len(tasks)} queries cached successfully. Failed: {failed}")
                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        logger.error(f"Cache warming for query '{common_queries[i]}' failed: {res}")
                    elif isinstance(res, list) and len(r) == 1 and r[0].get(
                            "title") == "Product Hunt Stories Unavailable":
                        logger.warning(f"Cache warming for query '{common_queries[i]}' returned fallback data.")

            else:
                logger.info("No queries specified for cache warming.")

        except Exception as e:
            logger.error(f"Cache warming task dispatcher failed: {e}", exc_info=True)
