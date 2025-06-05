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
from config import settings
import socket
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)


class GitHubTrendingScraper:
    BASE_URL = "https://github.com/trending"

    STARS_TODAY_PATTERN = re.compile(r'\d+\s+stars?\s+today')
    WHITESPACE_PATTERN = re.compile(r'\s+')
    NUMBER_PATTERN = re.compile(r'\d+')
    AVATAR_HREF_PATTERN = re.compile(r'^/[^/]+$')

    def __init__(self,
                 cache_timeout: int = settings.CACHE_TIMEOUT,
                 max_workers: int = settings.MAX_WORKERS,
                 request_timeout: int = settings.REQUEST_TIMEOUT,
                 max_repositories: int = settings.MAX_REPOSITORIES):

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
        self.max_repositories = max_repositories

        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        self._language_colors = self.load_language_colors()

        self._pre_resolve_domain()

    def _pre_resolve_domain(self):
        try:
            socket.gethostbyname('github.com')
        except:
            pass

    @lru_cache(maxsize=1)
    def load_language_colors(self) -> Dict[str, str]:
        try:
            current_dir = Path(__file__).parent
            colors_file = current_dir / "data" / "language_colors.json"

            with open(colors_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load language colors from JSON file: {e}")
            return {}

    @staticmethod
    def get_cache_key(language: Optional[str], since: Optional[str]) -> str:
        return f"{language or 'all'}_{since or 'daily'}"

    def is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self.cache:
            return False

        cached_time = self.cache[cache_key].get('timestamp')
        if not cached_time:
            return False

        return (datetime.now() - cached_time).seconds < self.cache_timeout

    def get_trending_repositories(self, language: Optional[str] = None, since: Optional[str] = None) -> List[
        Dict[str, Any]]:
        cache_key = self.get_cache_key(language, since)

        if self.is_cache_valid(cache_key):
            return self.cache[cache_key]['data']

        try:
            url = self.BASE_URL
            params = {}

            if language:
                url += f"/{language}"

            if since:
                params['since'] = since

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
            except:
                soup = BeautifulSoup(content, 'html.parser')

            repos = []
            repo_articles = soup.find_all('article', class_='Box-row')

            for article in repo_articles[:self.max_repositories]:
                repo_data = self._extract_repository_data(article)
                if repo_data:
                    repos.append(repo_data)

            self.cache[cache_key] = {
                'data': repos,
                'timestamp': datetime.now()
            }
            return repos

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            if cache_key in self.cache:
                logger.warning("Returning expired cache due to request failure")
                return self.cache[cache_key]['data']
            return self.get_fallback_data()

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            if cache_key in self.cache:
                logger.warning("Returning cached data due to scraping failure")
                return self.cache[cache_key]['data']
            return self.get_fallback_data()

    def _extract_repository_data(self, article) -> Optional[Dict[str, Any]]:
        try:
            repo_data = {}

            title_elem = article.find('h2', class_='h3')
            if not title_elem:
                return None

            link_elem = title_elem.find('a')
            if not link_elem:
                return None

            repo_name = link_elem.get_text().strip()
            repo_name = self.WHITESPACE_PATTERN.sub(' ', repo_name)

            repo_data['name'] = repo_name
            href = link_elem.get('href', '')
            repo_data['url'] = f'https://github.com{href}'

            repo_path = href.strip('/')
            if '/' in repo_path:
                owner, repository = repo_path.split('/', 1)
                repo_data['owner'] = owner.strip()
                repo_data['repository'] = repository.strip()

            desc_elem = article.find('p', class_='col-9')
            if desc_elem:
                description = desc_elem.get_text().strip()
                repo_data['description'] = description[:200] + "..." if len(description) > 200 else description
            else:
                repo_data['description'] = ""

            lang_elem = article.find('span', attrs={'itemprop': 'programmingLanguage'})
            if lang_elem:
                language = lang_elem.get_text().strip()
                repo_data['language'] = language
                repo_data['language_color'] = self._language_colors.get(language, '#586069')
            else:
                repo_data['language'] = None
                repo_data['language_color'] = '#586069'

            self._extract_repository_stats(article, repo_data)

            repo_data['contributors'] = self._extract_contributors_fast(article)

            return repo_data

        except Exception as e:
            logger.error(f"Error extracting repo data: {e}")
            return None

    def _extract_repository_stats(self, article, repo_data: Dict[str, Any]):
        repo_data['stars'] = 0
        repo_data['forks'] = 0

        links = article.find_all('a', href=True)

        for link in links:
            href = link.get('href', '')

            if '/stargazers' in href:
                repo_data['stars'] = self.parse_number(link.get_text().strip())
            elif '/network/members' in href or '/forks' in href:
                repo_data['forks'] = self.parse_number(link.get_text().strip())

        stars_today_elem = article.find('span', string=self.STARS_TODAY_PATTERN)
        if stars_today_elem:
            stars_today_text = stars_today_elem.get_text()
            repo_data['stars_today'] = self.parse_number(stars_today_text.split()[0])
        else:
            repo_data['stars_today'] = 0

    def _extract_contributors_fast(self, article) -> List[Dict[str, str]]:
        contributors = []

        imgs = article.find_all('img', class_=lambda x: x and 'avatar' in x)

        for img in imgs[:3]:
            parent_link = img.find_parent('a')
            if parent_link:
                href = parent_link.get('href', '')
                if href and self.AVATAR_HREF_PATTERN.match(href):
                    contributors.append({
                        'username': href.strip('/'),
                        'avatar_url': img.get('src', '')
                    })

        return contributors

    def parse_number(self, text: str) -> int:
        if not text:
            return 0

        text = text.strip().replace(',', '')

        if text.isdigit():
            return int(text)

        text_lower = text.lower()
        if text_lower.endswith('k'):
            try:
                return int(float(text[:-1]) * 1000)
            except:
                pass
        elif text_lower.endswith('m'):
            try:
                return int(float(text[:-1]) * 1000000)
            except:
                pass

        numbers = self.NUMBER_PATTERN.findall(text)
        return int(numbers[0]) if numbers else 0

    @staticmethod
    def get_fallback_data() -> List[Dict[str, Any]]:
        return [
            {
                "name": "GitHub Trending Unavailable",
                "url": "https://github.com/trending",
                "owner": "github",
                "repository": "trending",
                "description": "GitHub trending data is temporarily unavailable. Please try again later",
                "language": None,
                "language_color": "#586069",
                "stars": 0,
                "forks": 0,
                "stars_today": 0,
                "contributors": []
            }
        ]

    def get_cache_info(self) -> Dict[str, Any]:
        return {
            "cached_entries": len(self.cache),
            "cache_keys": list(self.cache.keys())
        }

    async def warm_cache(self):
        common_queries = [
            (None, 'daily'),
            ('python', 'daily'),
            ('javascript', 'daily'),
            ('typescript', 'daily')
        ]

        async def _warm_cache_task():
            try:
                loop = asyncio.get_event_loop()
                tasks = []

                for lang, since in common_queries:
                    task = loop.run_in_executor(
                        self.executor,
                        self.get_trending_repositories,
                        lang,
                        since
                    )
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)
                successful = sum(1 for r in results if not isinstance(r, Exception))
                logger.info(f"Cache warming completed: {successful}/{len(tasks)} queries cached successfully")
            except Exception as e:
                logger.error(f"Cache warming failed: {e}")

        asyncio.create_task(_warm_cache_task())
