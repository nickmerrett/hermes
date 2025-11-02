"""NewsAPI collector for gathering news articles"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from newsapi import NewsApiClient
from newsapi.newsapi_exception import NewsAPIException

from app.collectors.base import RateLimitedCollector
from app.models.schemas import IntelligenceItemCreate
from app.config.settings import settings


class NewsAPICollector(RateLimitedCollector):
    """
    Collector for NewsAPI.org - aggregates news from various sources

    Free tier limits:
    - 100 requests per day
    - 500 results per request
    - Only last 30 days of articles
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config, rate_limit=settings.news_api_rate_limit)

        if not settings.news_api_key:
            raise ValueError("NEWS_API_KEY not configured")

        self.client = NewsApiClient(api_key=settings.news_api_key)
        self.lookback_days = 7  # Search last 7 days by default

    def get_source_type(self) -> str:
        return "news_api"

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect news articles about the customer

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        # Check rate limit
        if not self._check_rate_limit():
            self.logger.warning("Rate limit exceeded, skipping NewsAPI collection")
            return items

        # Build search query from keywords
        query = self._build_query()
        if not query:
            self.logger.warning(f"No keywords configured for {self.customer_name}")
            return items

        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=self.lookback_days)

        try:
            self.logger.info(f"Searching NewsAPI for: {query}")

            # Search for articles
            response = self.client.get_everything(
                q=query,
                from_param=from_date.strftime('%Y-%m-%d'),
                to=to_date.strftime('%Y-%m-%d'),
                language='en',
                sort_by='publishedAt',
                page_size=100  # Max per request
            )

            # Process articles
            if response.get('status') == 'ok':
                articles = response.get('articles', [])
                self.logger.info(f"Found {len(articles)} articles from NewsAPI")

                for article in articles:
                    item = self._process_article(article)
                    if item:
                        items.append(item)

        except NewsAPIException as e:
            self.logger.error(f"NewsAPI error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching from NewsAPI: {e}")
            raise

        return items

    def _build_query(self) -> str:
        """
        Build search query from customer keywords

        Returns:
            Query string for NewsAPI
        """
        if not self.keywords:
            return ""

        # Use OR logic for keywords
        # Wrap multi-word phrases in quotes
        query_parts = []
        for keyword in self.keywords[:5]:  # Limit to 5 keywords to avoid too complex queries
            if ' ' in keyword:
                query_parts.append(f'"{keyword}"')
            else:
                query_parts.append(keyword)

        return ' OR '.join(query_parts)

    def _process_article(self, article: Dict[str, Any]) -> IntelligenceItemCreate | None:
        """
        Process a NewsAPI article into an IntelligenceItemCreate

        Args:
            article: Article dict from NewsAPI

        Returns:
            IntelligenceItemCreate or None if article should be filtered
        """
        try:
            title = article.get('title', '')
            description = article.get('description', '')
            content = article.get('content', '')

            # Combine description and content
            full_content = f"{description}\n\n{content}" if content else description

            # Check if relevant
            if not self._should_collect_item(title, full_content):
                return None

            # Parse published date
            published_at = article.get('publishedAt')
            published_date = None
            if published_at:
                try:
                    published_date = datetime.fromisoformat(
                        published_at.replace('Z', '+00:00')
                    )
                except (ValueError, AttributeError):
                    pass

            # Create item
            return self._create_item(
                title=title,
                content=full_content,
                url=article.get('url'),
                published_date=published_date,
                raw_data={
                    'source': article.get('source', {}).get('name'),
                    'author': article.get('author'),
                    'url_to_image': article.get('urlToImage'),
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing article: {e}")
            return None
