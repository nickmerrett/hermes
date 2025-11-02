"""Hacker News collector for tech community discussions"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import httpx
import asyncio

from app.collectors.base import BaseCollector
from app.models.schemas import IntelligenceItemCreate
from app.config.settings import settings


class HackerNewsCollector(BaseCollector):
    """
    Collector for Hacker News mentions and discussions

    Uses Algolia HN Search API (free, no auth required)
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config)
        self.api_base = settings.hackernews_api_base_url
        self.lookback_days = 7

    def get_source_type(self) -> str:
        return "hackernews"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect Hacker News posts mentioning the customer

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Search for each keyword
                for keyword in self.keywords[:5]:  # Limit to avoid too many requests
                    search_items = await self._search_hackernews(client, keyword)
                    items.extend(search_items)

            self.logger.info(f"Collected {len(items)} items from Hacker News")

        except Exception as e:
            self.logger.error(f"Error collecting from Hacker News: {e}")
            raise

        return items

    async def _search_hackernews(
        self,
        client: httpx.AsyncClient,
        keyword: str
    ) -> List[IntelligenceItemCreate]:
        """
        Search Hacker News for a keyword

        Args:
            client: HTTP client
            keyword: Search keyword

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        try:
            # Calculate timestamp for lookback period
            since_timestamp = int(
                (datetime.now() - timedelta(days=self.lookback_days)).timestamp()
            )

            # Search using Algolia API
            params = {
                'query': keyword,
                'tags': 'story',  # Only stories, not comments
                'numericFilters': f'created_at_i>{since_timestamp}',
                'hitsPerPage': 20
            }

            response = await client.get(f"{self.api_base}/search", params=params)
            response.raise_for_status()
            data = response.json()

            # Process results
            for hit in data.get('hits', []):
                item = self._process_hit(hit)
                if item:
                    items.append(item)

        except httpx.HTTPError as e:
            self.logger.error(f"Error searching Hacker News for '{keyword}': {e}")

        return items

    def _process_hit(self, hit: Dict[str, Any]) -> IntelligenceItemCreate | None:
        """
        Process a Hacker News search result

        Args:
            hit: Hit object from Algolia

        Returns:
            IntelligenceItemCreate or None
        """
        try:
            title = hit.get('title', '')
            story_text = hit.get('story_text', '')

            # Check relevance
            if not self._should_collect_item(title, story_text):
                return None

            # Build content from story text and top comments
            content_parts = []
            if story_text:
                content_parts.append(story_text)

            # Add info about comments if any
            num_comments = hit.get('num_comments', 0)
            points = hit.get('points', 0)
            if num_comments > 0:
                content_parts.append(
                    f"\n{num_comments} comments, {points} points on Hacker News"
                )

            content = '\n'.join(content_parts)

            # Parse date
            created_at = hit.get('created_at')
            published_date = None
            if created_at:
                try:
                    published_date = datetime.fromisoformat(
                        created_at.replace('Z', '+00:00')
                    )
                except (ValueError, AttributeError):
                    pass

            # Build URL
            object_id = hit.get('objectID')
            url = f"https://news.ycombinator.com/item?id={object_id}" if object_id else None

            # Original URL if available
            story_url = hit.get('url')

            return self._create_item(
                title=f"[HN] {title}",
                content=content,
                url=url,
                published_date=published_date,
                raw_data={
                    'story_url': story_url,
                    'author': hit.get('author'),
                    'points': points,
                    'num_comments': num_comments,
                    'created_at_i': hit.get('created_at_i'),
                    'story_id': object_id,
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing Hacker News hit: {e}")
            return None
