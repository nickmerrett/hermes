"""
Google News RSS collector

Automatically generates Google News RSS feeds based on customer keywords and competitors.
Supports regional filtering and custom search queries.

Google News RSS Format:
- Search: https://news.google.com/rss/search?q=QUERY&hl=LANGUAGE&gl=COUNTRY&ceid=COUNTRY:LANGUAGE
- Top Stories: https://news.google.com/rss?hl=LANGUAGE&gl=COUNTRY&ceid=COUNTRY:LANGUAGE
"""

from typing import List, Dict, Any
from datetime import datetime
import feedparser
from urllib.parse import quote_plus
import logging

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate

logger = logging.getLogger(__name__)


class GoogleNewsCollector(RateLimitedCollector):
    """
    Collect news from Google News RSS feeds

    Automatically creates search feeds for:
    - Customer/company name
    - Competitors
    - Keywords
    - Combined queries

    Configuration:
        google_news_enabled: Enable/disable Google News collection (default: True)
        google_news_region: Country code for regional news (default: AU for Australia)
        google_news_language: Language code (default: en)
        google_news_max_results: Max results per feed (default: 10)
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=20)  # 20 feeds per minute

        self.customer_name = customer_config.get('name', '')
        self.domain = customer_config.get('domain', '')
        self.keywords = customer_config.get('keywords', [])
        self.competitors = customer_config.get('competitors', [])

        # Google News settings
        config = customer_config.get('config', {})
        self.region = config.get('google_news_region', 'AU')  # Default to Australia
        self.language = config.get('google_news_language', 'en')
        self.max_results = config.get('google_news_max_results', 10)

        # Google News RSS base URL
        self.base_url = "https://news.google.com/rss"

    def get_source_type(self) -> str:
        return "google_news"

    def _build_search_url(self, query: str) -> str:
        """
        Build Google News RSS search URL

        Args:
            query: Search query

        Returns:
            Full RSS URL
        """
        encoded_query = quote_plus(query)
        ceid = f"{self.region}:{self.language}"

        return (
            f"{self.base_url}/search?"
            f"q={encoded_query}"
            f"&hl={self.language}-{self.region}"
            f"&gl={self.region}"
            f"&ceid={ceid}"
        )

    def _generate_search_queries(self) -> List[str]:
        """
        Generate search queries based on customer configuration

        Returns:
            List of search query strings
        """
        queries = []

        # Customer/company name search
        if self.customer_name:
            queries.append(self.customer_name)

        # Domain-based search (if available)
        if self.domain:
            # Extract company name from domain (e.g., example.com -> example)
            domain_name = self.domain.split('.')[0]
            if domain_name.lower() not in self.customer_name.lower():
                queries.append(domain_name)

        # Competitor searches
        for competitor in self.competitors[:3]:  # Limit to top 3 competitors
            queries.append(competitor)

        # Combined keyword searches (group keywords for better results)
        if self.keywords:
            # Add customer name + keywords for contextual search
            priority_keywords = self.keywords[:3]  # Top 3 keywords
            if priority_keywords and self.customer_name:
                combined_query = f"{self.customer_name} {' OR '.join(priority_keywords)}"
                queries.append(combined_query)

        return queries

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect news from Google News RSS feeds

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []
        queries = self._generate_search_queries()

        if not queries:
            self.logger.info("No search queries generated for Google News")
            return items

        self.logger.info(f"Collecting from Google News with {len(queries)} search queries")

        # Track unique URLs to avoid duplicates
        seen_urls = set()

        for query in queries:
            if not self._check_rate_limit():
                self.logger.warning("Rate limit reached for Google News")
                break

            try:
                feed_url = self._build_search_url(query)
                self.logger.debug(f"Fetching Google News feed: {query}")

                # Parse RSS feed
                feed = feedparser.parse(feed_url)

                if feed.bozo and not feed.entries:
                    self.logger.warning(f"Error parsing feed for query '{query}': {feed.bozo_exception}")
                    continue

                # Process entries
                entry_count = 0
                for entry in feed.entries[:self.max_results]:
                    try:
                        # Skip duplicates
                        url = entry.get('link', '')
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)

                        # Extract data
                        title = entry.get('title', 'No title')
                        description = entry.get('summary', entry.get('description', ''))

                        # Parse published date
                        published_date = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            try:
                                published_date = datetime(*entry.published_parsed[:6])
                            except (ValueError, TypeError):
                                pass

                        # Extract source from title (Google News format: "Title - Source")
                        source_name = "Google News"
                        if ' - ' in title:
                            parts = title.rsplit(' - ', 1)
                            if len(parts) == 2:
                                source_name = parts[1]

                        # Create item
                        item = self._create_item(
                            title=title,
                            content=description,
                            url=url,
                            published_date=published_date or datetime.now(),
                            raw_data={
                                'source': source_name,
                                'query': query,
                                'feed_url': feed_url,
                                'entry': {
                                    'author': entry.get('author', ''),
                                    'tags': [tag.term for tag in entry.get('tags', [])]
                                }
                            }
                        )

                        items.append(item)
                        entry_count += 1

                    except Exception as e:
                        self.logger.error(f"Error processing entry: {e}")
                        continue

                if entry_count > 0:
                    self.logger.info(f"Collected {entry_count} items for query '{query}'")

            except Exception as e:
                self.logger.error(f"Error collecting from Google News for query '{query}': {e}")
                continue

        self.logger.info(f"Total Google News items collected: {len(items)}")
        return items
