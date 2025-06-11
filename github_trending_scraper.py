import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import logging
from datetime import datetime
from functools import lru_cache

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class GitHubTrendingScraper(BaseScraper):
    BASE_URL = "https://github.com/trending"

    STARS_TODAY_PATTERN = re.compile(r'\d+\s+stars?\s+today')
    AVATAR_HREF_PATTERN = re.compile(r'^/[^/]+$')

    def __init__(self,
                 cache_timeout: int = None,
                 max_workers: int = None,
                 request_timeout: int = None,
                 max_repositories: int = None):

        super().__init__(
            base_url=self.BASE_URL,
            cache_timeout=cache_timeout,
            max_workers=max_workers,
            request_timeout=request_timeout,
            max_items=max_repositories
        )

        self._language_colors = self.load_language_colors()

        self.max_repositories = self.max_items

    @lru_cache(maxsize=1)
    def load_language_colors(self) -> Dict[str, str]:
        try:
            current_dir = Path(__file__).parent
            colors_file = current_dir / "data" / "language_colors.json"
            with open(colors_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return {}

    def get_cache_key(self, language: Optional[str] = None, since: Optional[str] = None) -> str:
        return f"{language or 'all'}_{since or 'daily'}"

    def get_data(self, language: Optional[str] = None, since: Optional[str] = None) -> List[Dict[str, Any]]:
        cache_key = self.get_cache_key(language, since)

        if self.is_cache_valid(cache_key):
            return self.cache[cache_key]['data']

        try:
            url = self.base_url
            params = {}

            if language:
                url += f"/{language}"
            if since:
                params['since'] = since

            response = self._make_request(url, params)
            soup = self._parse_html(response.content)

            repos = []
            repo_articles = soup.find_all('article', class_='Box-row')

            for article in repo_articles[:self.max_items]:
                repo_data = self._extract_item_data(article)
                if repo_data:
                    repos.append(repo_data)

            self.cache[cache_key] = {
                'data': repos,
                'timestamp': datetime.now()
            }
            return repos

        except Exception as e:
            logger.error(f"GitHub scraping failed for {cache_key}: {e}", exc_info=True)
            return self._handle_scraping_failure(cache_key)

    def _extract_item_data(self, article) -> Optional[Dict[str, Any]]:
        try:
            repo_data = {}

            title_elem = article.find('h2', class_='h3')
            if not title_elem:
                return None

            link_elem = title_elem.find('a')
            if not link_elem:
                return None

            repo_name = self.WHITESPACE_PATTERN.sub(' ', link_elem.get_text().strip())
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
            logger.error(f"Error extracting repository data: {e}", exc_info=True)
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

    def get_warm_cache_queries(self) -> List[Tuple]:
        return [
            (None, 'daily'),
            ('go', 'daily'),
            ('python', 'daily'),
            ('javascript', 'daily'),
            ('typescript', 'daily')
        ]

    def get_trending_repositories(self, language: Optional[str] = None, since: Optional[str] = None) -> List[
        Dict[str, Any]]:
        return self.get_data(language, since)
