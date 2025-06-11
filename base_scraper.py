import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
import re
from typing import Optional, List, Dict, Any, Tuple
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from config import settings
import socket
import asyncio
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseScraper(ABC):

    WHITESPACE_PATTERN = re.compile(r'\s+')
    NUMBER_PATTERN = re.compile(r'\d+')

    def __init__(self,
                 base_url: str,
                 cache_timeout: int = None,
                 max_workers: int = None,
                 request_timeout: int = None,
                 max_items: int = None):

        self.base_url = base_url
        self.cache_timeout = cache_timeout or settings.CACHE_TIMEOUT
        self.request_timeout = request_timeout or settings.REQUEST_TIMEOUT
        self.max_items = max_items or settings.MAX_REPOSITORIES

        self.session = self._setup_session()

        self.cache = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers or settings.MAX_WORKERS)

        self._pre_resolve_domain()

    def _setup_session(self) -> requests.Session:
        session = requests.Session()

        adapter = HTTPAdapter(
            pool_connections=settings.POOL_CONNECTIONS,
            pool_maxsize=settings.POOL_MAXSIZE,
            max_retries=settings.MAX_RETRIES,
            pool_block=settings.POOL_BLOCK
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })

        return session

    def _pre_resolve_domain(self):
        try:
            domain = self.base_url.replace('https://', '').replace('http://', '').split('/')[0]
            socket.gethostbyname(domain)
        except socket.gaierror as e:
            logger.warning(f"Failed to pre-resolve domain: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error during domain pre-resolution: {e}")

    def is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self.cache:
            return False

        cached_time = self.cache[cache_key].get('timestamp')
        if not cached_time:
            return False

        elapsed_seconds = (datetime.now() - cached_time).total_seconds()
        is_valid = elapsed_seconds < self.cache_timeout

        return is_valid

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

    def _make_request(self, url: str, params: Dict = None) -> requests.Response:
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.request_timeout,
                stream=True
            )
            response.raise_for_status()
            return response
        except requests.Timeout:
            logger.error(f"Request timeout for {url} (timeout: {self.request_timeout}s)")
            raise
        except requests.ConnectionError as e:
            logger.error(f"Connection error for {url}: {e}")
            raise
        except requests.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e} (status: {e.response.status_code})")
            raise
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise

    def _parse_html(self, content: bytes) -> BeautifulSoup:
        try:
            return BeautifulSoup(content, 'lxml')
        except Exception:
            return BeautifulSoup(content, 'html.parser')

    def _handle_request_failure(self, cache_key: str) -> List[Dict[str, Any]]:
        if cache_key in self.cache:
            logger.warning(f"Returning expired cache for {cache_key} due to request failure")
            return self.cache[cache_key]['data']

        logger.warning(f"No cache available for {cache_key}, returning fallback data")
        return self.get_fallback_data()

    def _handle_scraping_failure(self, cache_key: str) -> List[Dict[str, Any]]:
        if cache_key in self.cache:
            logger.warning(f"Returning cached data for {cache_key} due to scraping failure")
            return self.cache[cache_key]['data']

        logger.warning(f"No cache available for {cache_key}, returning fallback data")
        return self.get_fallback_data()

    def get_cache_info(self) -> Dict[str, Any]:
        cache_details = {}
        for key, value in self.cache.items():
            timestamp = value.get('timestamp')
            cache_details[key] = {
                "timestamp": timestamp.isoformat() if timestamp else None,
                "size": len(value.get('data', [])),
                "age_seconds": (datetime.now() - timestamp).total_seconds() if timestamp else None,
                "is_valid": self.is_cache_valid(key)
            }

        return {
            "cached_entries": len(self.cache),
            "cache_keys": list(self.cache.keys()),
            "cache_timeout": self.cache_timeout,
            "cache_details": cache_details
        }

    async def warm_cache(self):
        queries = self.get_warm_cache_queries()

        if not queries:
            return

        try:
            loop = asyncio.get_event_loop()

            tasks = []
            for query in queries:
                task = loop.run_in_executor(
                    self.executor,
                    self.get_data,
                    *query
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful = 0
            failed = 0

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed += 1
                    logger.error(f"Cache warming for query '{queries[i]}' failed: {result}")
                elif isinstance(result, list) and self._is_valid_data(result):
                    successful += 1
                else:
                    failed += 1
                    logger.warning(f"Cache warming for query '{queries[i]}' returned fallback data")

            logger.info(f"Cache warming completed: {successful}/{len(tasks)} queries successful, {failed} failed")

        except Exception as e:
            logger.error(f"Cache warming failed: {e}", exc_info=True)

    def _is_valid_data(self, data: List[Dict]) -> bool:
        if not data or not isinstance(data, list):
            return False

        first_item = data[0]
        title = str(first_item.get("title", "")).lower()
        name = str(first_item.get("name", "")).lower()

        fallback_indicators = ["unavailable", "temporarily", "try again", "error", "fallback"]

        return not any(indicator in title or indicator in name for indicator in fallback_indicators)

    def clear_cache(self):
        self.cache.clear()

    def clear_expired_cache(self):
        expired_keys = [key for key in self.cache.keys() if not self.is_cache_valid(key)]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired cache entries")

    def __del__(self):
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)
            if hasattr(self, 'session'):
                self.session.close()
        except Exception:
            pass


    @abstractmethod
    def get_cache_key(self, *args, **kwargs) -> str:
        pass

    @abstractmethod
    def get_data(self, *args, **kwargs) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def _extract_item_data(self, element) -> Optional[Dict[str, Any]]:
        pass

    @staticmethod
    @abstractmethod
    def get_fallback_data() -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_warm_cache_queries(self) -> List[Tuple]:
        pass
