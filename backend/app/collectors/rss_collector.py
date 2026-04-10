"""RSS/Atom feed collector for company blogs and news"""

from typing import List, Dict, Any
from datetime import datetime
import feedparser
from dateutil import parser as date_parser
import httpx

from app.collectors.base import BaseCollector
from app.models.schemas import IntelligenceItemCreate


class RSSCollector(BaseCollector):
    """
    Collector for RSS/Atom feeds (company blogs, press releases, etc.)

    This collector reads from configured RSS feeds for each customer
    """

    def __init__(self, customer_config: Dict[str, Any], feed_config: Dict[str, Any]):
        """
        Initialize RSS collector

        Args:
            customer_config: Customer configuration
            feed_config: RSS feed configuration with 'url' and 'name'
        """
        super().__init__(customer_config)
        self.feed_url = feed_config.get('url')
        self.feed_name = feed_config.get('name', 'RSS Feed')
        self.source_id = feed_config.get('source_id')  # Database source ID
        self.is_trusted = feed_config.get('trusted', False)

        if not self.feed_url:
            raise ValueError("RSS feed URL is required")

    def get_source_type(self) -> str:
        return "rss"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect items from RSS feed

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        try:
            self.logger.info(f"Fetching RSS feed: {self.feed_url}")

            # Fetch feed with timeout
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.feed_url)
                response.raise_for_status()
                feed_content = response.text

            # Parse feed
            feed = feedparser.parse(feed_content)

            if feed.bozo:
                # Feed parsing had issues but may still have data
                self.logger.warning(
                    f"Feed parsing warning for {self.feed_url}: {feed.bozo_exception}"
                )

            # Process entries
            entries = feed.entries
            self.logger.info(f"Found {len(entries)} entries in RSS feed")

            for entry in entries:
                item = self._process_entry(entry)
                if item:
                    items.append(item)

        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error fetching RSS feed {self.feed_url}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error processing RSS feed {self.feed_url}: {e}")
            raise

        return items

    def _process_entry(self, entry: Any) -> IntelligenceItemCreate | None:
        """
        Process an RSS entry into an IntelligenceItemCreate

        Args:
            entry: feedparser entry object

        Returns:
            IntelligenceItemCreate or None
        """
        try:
            # Extract title
            title = entry.get('title', 'Untitled')

            # Extract content/description
            content = self._extract_content(entry)

            # Extract URL
            url = entry.get('link')

            # Extract published date
            published_date = self._extract_date(entry)

            # Trusted/official feeds skip keyword filtering (company's own channels)
            if not self.is_trusted and not self._should_collect_item(title, content, title_only=True):
                return None

            # Create item
            return self._create_item(
                title=title,
                content=content,
                url=url,
                published_date=published_date,
                source_id=self.source_id,
                raw_data={
                    'feed_name': self.feed_name,
                    'feed_url': self.feed_url,
                    'author': entry.get('author'),
                    'tags': [tag.term for tag in entry.get('tags', [])],
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing RSS entry: {e}")
            return None

    def _extract_content(self, entry: Any) -> str:
        """
        Extract content from RSS entry (tries multiple fields)

        Args:
            entry: feedparser entry

        Returns:
            Content string
        """
        # Try different content fields in order of preference
        if hasattr(entry, 'content') and entry.content:
            return entry.content[0].get('value', '')

        if hasattr(entry, 'summary'):
            return entry.summary

        if hasattr(entry, 'description'):
            return entry.description

        return ""

    def _extract_date(self, entry: Any) -> datetime | None:
        """
        Extract published date from RSS entry

        Args:
            entry: feedparser entry

        Returns:
            datetime object or None
        """
        # Try different date fields
        date_fields = ['published', 'updated', 'created']

        for field in date_fields:
            if hasattr(entry, field):
                date_str = getattr(entry, field)
                try:
                    # Use dateutil parser for flexible parsing
                    return date_parser.parse(date_str)
                except (ValueError, TypeError):
                    continue

        # Try parsed date from feedparser
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6])
            except (TypeError, ValueError):
                pass

        return None
