"""Australian news sites collector for specific regional sources"""

from typing import List, Dict, Any
from datetime import datetime
import httpx
import feedparser
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector
from app.models.schemas import IntelligenceItemCreate
from app.models.database import PlatformSettings


class AustralianNewsCollector(BaseCollector):
    """
    Collector for Australian news sources

    Supported sites:
    - itnews.com.au (IT news)
    - news.abc.net.au (ABC News)
    - afr.com.au (Australian Financial Review)
    - theguardian.com/au (The Guardian Australia)
    - smh.com.au (Sydney Morning Herald)
    - theage.com.au (The Age)
    - news.com.au (News.com.au)
    """

    def __init__(self, customer_config: Dict[str, Any], db: Session = None):
        super().__init__(customer_config)

        # Load sources from platform settings
        self.news_feeds = self._load_sources_from_settings(db)

        self.headers = {
            'User-Agent': 'CustomerIntelligenceTool/1.0 (News Aggregator)',
        }

        # Log configuration for debugging
        self.logger.info(f"Initialized for customer: {self.customer_name}")
        self.logger.info(f"Loaded {len(self.news_feeds)} news sources: {list(self.news_feeds.keys())}")
        self.logger.info(f"Filtering with {len(self.keywords)} keywords: {self.keywords[:5]}{'...' if len(self.keywords) > 5 else ''}")

    def _load_sources_from_settings(self, db: Session = None) -> Dict[str, Dict[str, str]]:
        """Load Australian news sources from platform settings"""

        if db:
            try:
                setting = db.query(PlatformSettings).filter(
                    PlatformSettings.key == 'australian_news_sources'
                ).first()

                if setting and setting.value and 'sources' in setting.value:
                    # Filter to only enabled sources
                    all_sources = setting.value['sources']
                    enabled_sources = [s for s in all_sources if s.get('enabled', True)]

                    if enabled_sources:
                        # Convert platform settings format to internal format
                        news_feeds = {}
                        for source in enabled_sources:
                            source_key = source.get('name', '').lower().replace(' ', '_')
                            source_name = source.get('name')
                            feeds = source.get('feeds', [])

                            if not source_name or not feeds:
                                self.logger.warning(f"Skipping invalid source config: {source}")
                                continue

                            # Convert feeds list to dict format
                            feed_dict = {'name': source_name}
                            for i, feed_url in enumerate(feeds):
                                # Clean URL (strip whitespace)
                                clean_url = feed_url.strip() if isinstance(feed_url, str) else feed_url
                                if i == 0:
                                    feed_dict['rss'] = clean_url
                                else:
                                    feed_dict[f'rss_{i}'] = clean_url

                            news_feeds[source_key] = feed_dict

                        if news_feeds:
                            self.logger.info(f"Loaded {len(news_feeds)} Australian news sources from platform settings")
                            return news_feeds
            except Exception as e:
                self.logger.warning(f"Error loading Australian news sources from settings: {e}")

        # Use fallback defaults if database not available or not configured
        return self._get_default_sources()

    def _get_default_sources(self) -> Dict[str, Dict[str, str]]:
        """Return default Australian news sources as fallback"""
        self.logger.warning("⚠️  Using default Australian news sources fallback (database not configured)")
        self.logger.warning("⚠️  Configure via Platform Settings UI or API for better coverage")

        # Improved defaults with business/tech focused feeds
        return {
            'abc_news_business': {
                'name': 'ABC News Business',
                'rss': 'https://www.abc.net.au/news/feed/45924/rss.xml',  # Business feed
                'rss_2': 'https://www.abc.net.au/news/feed/51120/rss.xml'  # General (backup)
            },
            'guardian_au_business': {
                'name': 'The Guardian Australia Business',
                'rss': 'https://www.theguardian.com/australia-news/business/rss',
                'rss_2': 'https://www.theguardian.com/technology/rss'
            },
            'smh_business': {
                'name': 'Sydney Morning Herald Business',
                'rss': 'https://www.smh.com.au/rss/business.xml',
                'rss_2': 'https://www.smh.com.au/rss/technology.xml'
            },
            'itnews': {
                'name': 'ITNews Australia',
                'rss': 'https://www.itnews.com.au/rss.xml'
            }
        }

    def get_source_type(self) -> str:
        return "australian_news"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect news from Australian sources

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        self.logger.info("=" * 60)
        self.logger.info(f"Starting Australian news collection for {self.customer_name}")
        self.logger.info("=" * 60)

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
                # Collect from each news source
                for source_key, source_config in self.news_feeds.items():
                    self.logger.info(f"Processing source: {source_config.get('name', source_key)}")
                    source_items = await self._collect_from_source(
                        client,
                        source_key,
                        source_config
                    )
                    items.extend(source_items)
                    self.logger.info(f"  → Collected {len(source_items)} items from {source_config.get('name', source_key)}")

            self.logger.info("=" * 60)
            self.logger.info(f"✅ Collection complete: {len(items)} total items collected")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"❌ Error collecting from Australian news: {e}")
            raise

        return items

    async def _collect_from_source(
        self,
        client: httpx.AsyncClient,
        source_key: str,
        source_config: Dict[str, Any]
    ) -> List[IntelligenceItemCreate]:
        """
        Collect from a specific Australian news source

        Args:
            client: HTTP client
            source_key: Source identifier
            source_config: Source configuration

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []
        source_name = source_config.get('name', source_key)

        try:
            # Collect from all RSS feeds for this source
            for key, value in source_config.items():
                if key.endswith('_rss') or key == 'rss':
                    feed_items = await self._collect_from_rss(
                        client,
                        value,
                        source_name
                    )
                    items.extend(feed_items)

        except Exception as e:
            self.logger.error(f"Error collecting from {source_name}: {e}")

        return items

    async def _collect_from_rss(
        self,
        client: httpx.AsyncClient,
        feed_url: str,
        source_name: str
    ) -> List[IntelligenceItemCreate]:
        """
        Collect from an RSS feed

        Args:
            client: HTTP client
            feed_url: RSS feed URL
            source_name: Name of the source

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        try:
            # Clean URL (strip whitespace, common issues)
            feed_url = feed_url.strip()

            self.logger.info(f"  📰 Fetching feed: {feed_url}")
            response = await client.get(feed_url)
            response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.text)
            total_entries = len(feed.entries)
            entries_to_check = feed.entries[:30]

            self.logger.info(f"  📊 Feed has {total_entries} entries, checking most recent {len(entries_to_check)}")

            checked_count = 0
            filtered_count = 0
            matched_count = 0

            for entry in entries_to_check:
                checked_count += 1

                # Check if entry is relevant to customer
                title = entry.get('title', '')
                summary = entry.get('summary', '') or entry.get('description', '')

                # Track which keyword matched (if any)
                matched_keyword = self._get_matching_keyword(title, summary)

                if not matched_keyword:
                    filtered_count += 1
                    self.logger.debug(f"  ⊘ Filtered (no keyword match): {title[:80]}...")
                    continue

                matched_count += 1
                self.logger.info(f"  ✓ Matched on '{matched_keyword}': {title[:80]}...")

                item = self._process_entry(entry, source_name)
                if item:
                    items.append(item)

            self.logger.info(f"  📈 Stats: {checked_count} checked, {matched_count} matched ({matched_count/checked_count*100:.1f}%), {filtered_count} filtered")

        except httpx.HTTPError as e:
            self.logger.warning(f"  ⚠️  HTTP error fetching {source_name} RSS from {feed_url}: {e}")
        except Exception as e:
            self.logger.error(f"  ❌ Error processing {source_name} RSS from {feed_url}: {e}")

        return items

    def _process_entry(
        self,
        entry: Any,
        source_name: str
    ) -> IntelligenceItemCreate | None:
        """
        Process an RSS entry into an IntelligenceItemCreate

        Args:
            entry: feedparser entry
            source_name: Source name

        Returns:
            IntelligenceItemCreate or None
        """
        try:
            title = entry.get('title', 'Untitled')
            content = entry.get('summary', '') or entry.get('description', '')

            # Clean HTML from content if present
            if content:
                soup = BeautifulSoup(content, 'html.parser')
                content = soup.get_text(separator='\n', strip=True)

            url = entry.get('link')

            # Parse published date
            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    published_date = datetime(*entry.published_parsed[:6])
                except (TypeError, ValueError):
                    pass

            return self._create_item(
                title=f"[{source_name}] {title}",
                content=content,
                url=url,
                published_date=published_date,
                raw_data={
                    'source': source_name,
                    'author': entry.get('author'),
                    'categories': [tag.get('term') for tag in entry.get('tags', [])],
                    'region': 'Australia'
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing entry from {source_name}: {e}")
            return None

    def _get_matching_keyword(self, title: str, content: str = "") -> str | None:
        """
        Check if an item matches any keywords and return the matching keyword

        Args:
            title: Item title
            content: Item content

        Returns:
            The first matching keyword, or None if no match
        """
        if not self.keywords:
            return "no_keywords_configured"

        # Combine title and content for searching
        text = f"{title} {content}".lower()

        # Check if any keyword appears in the text
        for keyword in self.keywords:
            if keyword.lower() in text:
                return keyword

        return None
