from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
	title="GitHub Trending Scraper",
	description="Scrape GitHub trending repositories optimized for Glance dashboard",
	version="2.0.0"
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


class GitHubTrendingScraper:
	BASE_URL = "https://github.com/trending"

	def __init__(self):
		self.session = requests.Session()
		self.session.headers.update({
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
			'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
			'Accept-Language': 'en-US,en;q=0.5',
			'Accept-Encoding': 'gzip, deflate',
			'Connection': 'keep-alive',
			'Upgrade-Insecure-Requests': '1',
		})

		self.cache = {}
		self.cache_timeout = 600

		self.executor = ThreadPoolExecutor(max_workers=2)

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

	def get_trending_repositories(self, language: Optional[str] = None, since: Optional[str] = None) -> List[Dict[str, Any]]:
		cache_key = self.get_cache_key(language, since)

		if self.is_cache_valid(cache_key):
			logger.info(f"Returning cached results for {cache_key}")
			return self.cache[cache_key]['data']

		try:
			url = self.BASE_URL
			params = {}

			if language:
				url += f"/{language}"

			if since:
				params['since'] = since

			response = self.session.get(url, params=params, timeout=8)
			response.raise_for_status()

			soup = BeautifulSoup(response.content, 'html.parser')

			repos = []
			repo_articles = soup.find_all('article', class_='Box-row')

			for article in repo_articles[:15]:
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
			repo_name = re.sub(r'\s+', ' ', repo_name)

			repo_data['name'] = repo_name
			repo_data['url'] = 'https://github.com' + link_elem.get('href', '')

			repo_path = link_elem.get('href', '').strip('/')
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
				repo_data['language_color'] = self.get_language_color(language)
			else:
				repo_data['language'] = None
				repo_data['language_color'] = '#586069'

			self._extract_repository_stats(article, repo_data)

			repo_data['contributors'] = self.extract_contributors(article)

			return repo_data

		except Exception as e:
			logger.error(f"Error extracting repo data: {e}")
			return None

	def _extract_repository_stats(self, article, repo_data: Dict[str, Any]):
		repo_data['stars'] = 0

		links = article.find_all('a', href=True)

		for link in links:
			href = link.get('href', '')
			text = link.get_text().strip()

			if '/stargazers' in href:
				repo_data['stars'] = self.parse_number(text)
			elif '/network/members' in href or '/forks' in href:
				repo_data['forks'] = self.parse_number(text)

		stars_today_elem = article.find('span', string=re.compile(r'\d+\s+stars?\s+today'))
		if stars_today_elem:
			stars_today_text = stars_today_elem.get_text()
			repo_data['stars_today'] = self.parse_number(stars_today_text.split()[0])

	@staticmethod
	def extract_contributors(article) -> List[Dict[str, str]]:
		contributors = []

		avatar_links = article.find_all('a', href=re.compile(r'^/[^/]+$'))

		for link in avatar_links[:3]:
			img = link.find('img')
			if img and any('avatar' in cls for cls in img.get('class', [])):
				contributor = {
					'username': link.get('href', '').strip('/'),
					'avatar_url': img.get('src', '')
				}
				contributors.append(contributor)

		return contributors

	@staticmethod
	def parse_number(text: str) -> int:
		if not text:
			return 0

		text = text.strip().replace(',', '')

		if text.lower().endswith('k'):
			return int(float(text[:-1]) * 1000)
		elif text.lower().endswith('m'):
			return int(float(text[:-1]) * 1000000)
		else:
			numbers = re.findall(r'\d+', text)
			return int(numbers[0]) if numbers else 0

	@staticmethod
	def get_language_color(language: str) -> str:
		colors = {
			'Python': '#3572A5',
			'JavaScript': '#f1e05a',
			'TypeScript': '#2b7489',
			'Go': '#00ADD8',
			'Java': '#b07219',
			'HTML': '#e34c26',
			'CSS': '#563d7c',
			'C++': '#f34b7d',
			'C#': '#239120',
			'Jupyter Notebook': '#DA5B0B',
			'MDX': '#fcb32c',
			'Rust': '#dea584',
			'PHP': '#4F5D95',
			'Swift': '#FA7343',
			'Kotlin': '#A97BFF',
			'Ruby': '#701516',
			'Vue': '#4FC08D',
			'React': '#61DAFB',
		}
		return colors.get(language, '#586069')

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


scraper = GitHubTrendingScraper()


@app.get("/")
async def root():
	return {
		"message": "GitHub Trending Scraper API - Optimized for Glance",
		"version": "2.0.0",
		"endpoints": {
			"trending": "/trending",
			"health": "/health"
		},
		"glance_ready": True,
		"timestamp": datetime.now().isoformat()
	}


@app.get("/trending")
async def get_trending(
		language: Optional[str] = Query(None, description="Programming language filter (e.g., python, javascript)"),
		since: Optional[str] = Query("daily", description="Time period: daily, weekly, or monthly")
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


@app.get("/health")
async def health_check():
	cache_info = scraper.get_cache_info()

	return {
		"status": "healthy",
		"timestamp": datetime.now().isoformat(),
		"version": "2.0.0",
		"cache": cache_info
	}


if __name__ == "__main__":
	import uvicorn
	APP_HOST = os.getenv("HOST")
	APP_PORT = int(os.getenv("PORT"))

	uvicorn.run(
		app,
		host=APP_HOST,
		port=APP_PORT,
		access_log=True,
		reload=False
	)
