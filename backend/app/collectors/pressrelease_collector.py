"""Press release collector from major distribution services"""

from typing import List, Dict, Any
from datetime import datetime
import httpx
import feedparser

from app.collectors.base import BaseCollector
from app.models.schemas import IntelligenceItemCreate


class PressReleaseCollector(BaseCollector):
    """
    Collector for press releases from major distribution services

    Sources:
    - PR Newswire RSS
    - Business Wire RSS
    - GlobeNewswire RSS
    - PRWeb
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config)

        # RSS feed endpoints for major PR services
        self.pr_feeds = {
            'prnewswire': 'https://www.prnewswire.com/rss/news-releases-list.rss',
            'businesswire': 'https://www.businesswire.com/portal/site/home/news/',
            'globenewswire': 'https://www.globenewswire.com/RssFeed/subjectcode/14-Corporate%20News/feedTitle/GlobeNewswire%20-%20Corporate%20News',
        }

        self.headers = {
            'User-Agent': 'CustomerIntelligenceTool/1.0 (Press Release Aggregator)',
        }

    def get_source_type(self) -> str:
        return "press_release"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect press releases mentioning the customer

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
                # Collect from each PR service
                for service_name, feed_url in self.pr_feeds.items():
                    service_items = await self._collect_from_feed(
                        client,
                        service_name,
                        feed_url
                    )
                    items.extend(service_items)

            self.logger.info(f"Collected {len(items)} press releases")

        except Exception as e:
            self.logger.error(f"Error collecting press releases: {e}")
            raise

        return items

    async def _collect_from_feed(
        self,
        client: httpx.AsyncClient,
        service_name: str,
        feed_url: str
    ) -> List[IntelligenceItemCreate]:
        """
        Collect from a specific PR service RSS feed

        Args:
            client: HTTP client
            service_name: Name of the service
            feed_url: RSS feed URL

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        try:
            response = await client.get(feed_url)
            response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.text)

            for entry in feed.entries[:50]:  # Check last 50 entries
                # Check if entry is relevant to customer
                title = entry.get('title', '')
                summary = entry.get('summary', '') or entry.get('description', '')

                if not self._should_collect_item(title, summary):
                    continue

                item = self._process_entry(entry, service_name)
                if item:
                    items.append(item)

        except httpx.HTTPError as e:
            self.logger.warning(f"Error fetching {service_name} feed: {e}")
        except Exception as e:
            self.logger.error(f"Error processing {service_name} feed: {e}")

        return items

    def _process_entry(
        self,
        entry: Any,
        service_name: str
    ) -> IntelligenceItemCreate | None:
        """
        Process an RSS entry into an IntelligenceItemCreate

        Args:
            entry: feedparser entry
            service_name: Source service name

        Returns:
            IntelligenceItemCreate or None
        """
        try:
            title = entry.get('title', 'Untitled Press Release')
            content = entry.get('summary', '') or entry.get('description', '')
            url = entry.get('link')

            # Parse published date
            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    published_date = datetime(*entry.published_parsed[:6])
                except (TypeError, ValueError):
                    pass

            return self._create_item(
                title=f"[Press Release - {service_name.upper()}] {title}",
                content=content,
                url=url,
                published_date=published_date,
                raw_data={
                    'service': service_name,
                    'author': entry.get('author'),
                    'categories': [tag.get('term') for tag in entry.get('tags', [])],
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing press release entry: {e}")
            return None
