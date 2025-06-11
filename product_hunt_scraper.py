import re
from typing import Optional, List, Dict, Any, Tuple
import logging
from datetime import datetime

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class ProductHuntScraper(BaseScraper):
    BASE_URL = "https://www.producthunt.com/stories?ref=header_nav"

    def __init__(self,
                 cache_timeout: int = None,
                 max_workers: int = None,
                 request_timeout: int = None,
                 max_stories: int = None):

        super().__init__(
            base_url=self.BASE_URL,
            cache_timeout=cache_timeout,
            max_workers=max_workers,
            request_timeout=request_timeout,
            max_items=max_stories
        )

        self.max_stories = self.max_items

    def get_cache_key(self, category: Optional[str] = None) -> str:
        return f"stories_{category or 'all'}"

    def get_data(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        cache_key = self.get_cache_key(category)

        if self.is_cache_valid(cache_key):
            return self.cache[cache_key]['data']

        try:
            url = self.base_url
            params = {}
            if category:
                params['category'] = category

            response = self._make_request(url, params)
            soup = self._parse_html(response.content)

            stories = []
            story_articles = soup.find_all('div', attrs={'data-test': re.compile(r'story-item-\d+')})
            if not story_articles:
                story_articles = soup.find_all('div', class_=re.compile(r'styles_item__\w+'))

            for article in story_articles[:self.max_items]:
                story_data = self._extract_item_data(article)
                if story_data:
                    stories.append(story_data)

            self.cache[cache_key] = {
                'data': stories,
                'timestamp': datetime.now()
            }
            return stories

        except Exception as e:
            logger.error(f"Product Hunt scraping failed for {cache_key}: {e}", exc_info=True)
            return self._handle_scraping_failure(cache_key)

    def _extract_item_data(self, article) -> Optional[Dict[str, Any]]:
        try:
            story_data = {}

            story_id_match = re.search(r'story-item-(\d+)', article.get('data-test', ''))
            story_data['story_id'] = story_id_match.group(1) if story_id_match else None

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
                story_data['url'] = ""
                for link in potential_links:
                    href = link.get('href', '')
                    if '/category/' not in href:
                        story_data['url'] = f"https://www.producthunt.com{href}"
                        break

            if not story_data.get('url'):
                logger.warning(f"Could not extract URL for story: {story_data['title']}")

            self._extract_story_metadata(article, story_data)

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
            logger.error(f"Error extracting story data: {e}", exc_info=True)
            return None

    def _extract_story_metadata(self, article, story_data: Dict[str, Any]):
        meta_info_elem = article.find('div', class_=re.compile(r'text-12.*text-light-gray'))

        story_data['author'] = "Unknown"
        story_data['author_url'] = None
        story_data['category'] = None
        story_data['read_time'] = None

        if not meta_info_elem:
            return

        author_link_elem = meta_info_elem.find('a', href=re.compile(r'linkedin\.com|twitter\.com|github\.com',
                                                                    re.IGNORECASE))
        if not author_link_elem:
            author_link_elem = meta_info_elem.find('a', href=True)

        if author_link_elem:
            story_data['author'] = author_link_elem.get_text().strip()
            author_url = author_link_elem.get('href', '')
            if author_url.startswith('/@'):
                story_data['author_url'] = f"https://www.producthunt.com{author_url}"
            else:
                story_data['author_url'] = author_url
        else:
            text_content = meta_info_elem.get_text(separator='|').strip()
            parts = [p.strip() for p in text_content.split('|') if p.strip()]
            if parts:
                potential_author = parts[0]
                if not any(kw in potential_author.lower() for kw in ['min read', 'comment', 'launch']):
                    story_data['author'] = potential_author

        category_elem = meta_info_elem.find('a', href=re.compile('/stories/category/'))
        if category_elem:
            story_data['category'] = category_elem.get_text().strip()

        text_content = meta_info_elem.get_text()
        read_time_match = re.search(r'(\d+)\s*min\s*read', text_content)
        if read_time_match:
            story_data['read_time'] = int(read_time_match.group(1))

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

    def get_warm_cache_queries(self) -> List[Tuple]:
        return [
            (None,),
            ('makers',),
            ('product-updates',),
            ('how-tos',),
            ('news',)
        ]

    def get_trending_stories(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.get_data(category)
