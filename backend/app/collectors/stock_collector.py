"""Stock market data collector using Playwright web scraping"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from pathlib import Path

from app.collectors.base import BaseCollector
from app.models.schemas import IntelligenceItemCreate
from app.collectors.yahoo_news_scraper import YahooNewsScraper, YahooNewsScraperError


class StockCollector(BaseCollector):
    """
    Collector for company news from Yahoo Finance

    Provides:
    - Company news articles from Yahoo Finance (scraped with Playwright)
    - News publisher information
    - Article summaries and publication dates

    Uses Playwright to scrape news articles directly from Yahoo Finance pages.
    Implements aggressive caching (24 hours) to minimize scraping overhead.
    """

    def __init__(self, customer_config: Dict[str, Any]):
        super().__init__(customer_config)
        self.stock_symbol = customer_config.get('stock_symbol')

        if not self.stock_symbol:
            raise ValueError(f"Stock symbol not configured for {self.customer_name}")

        # Cache settings - cache for 24 hours since we don't need real-time data
        self.cache_dir = Path("data/cache/stock")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_duration_hours = 24

    def get_source_type(self) -> str:
        return "stock"

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key"""
        safe_symbol = self.stock_symbol.replace('.', '_')
        return self.cache_dir / f"{safe_symbol}_{cache_key}.json"

    def _read_cache(self, cache_key: str) -> Optional[Any]:
        """Read data from cache if it exists and is fresh"""
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)

            # Check if cache is still fresh
            cached_time = datetime.fromisoformat(cache_data['timestamp'])
            age_hours = (datetime.now() - cached_time).total_seconds() / 3600

            if age_hours < self.cache_duration_hours:
                self.logger.info(f"Using cached {cache_key} for {self.stock_symbol} (age: {age_hours:.1f}h)")
                return cache_data['data']
            else:
                self.logger.info(f"Cache expired for {cache_key} (age: {age_hours:.1f}h)")
                return None

        except Exception as e:
            self.logger.warning(f"Error reading cache for {cache_key}: {e}")
            return None

    def _write_cache(self, cache_key: str, data: Any) -> None:
        """Write data to cache"""
        cache_path = self._get_cache_path(cache_key)

        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }

            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, default=str)

            self.logger.info(f"Cached {cache_key} for {self.stock_symbol}")

        except Exception as e:
            self.logger.warning(f"Error writing cache for {cache_key}: {e}")

    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect company news from Yahoo Finance

        Returns:
            List of IntelligenceItemCreate objects
        """
        items = []

        try:
            # Get company news from Yahoo Finance (using Playwright scraper)
            news_items = await self._collect_news()
            items.extend(news_items)

        except Exception as e:
            self.logger.warning(
                f"News collection failed for {self.stock_symbol}: {e}. "
                f"Continuing with other data sources..."
            )
            # Return empty list - don't raise exception
            return []

        if not items:
            self.logger.info(
                f"No news articles collected for {self.stock_symbol}. "
                f"The scraper may be temporarily unavailable or no news is available."
            )

        return items

    async def _collect_news(self) -> List[IntelligenceItemCreate]:
        """
        Collect news from Yahoo Finance for the stock using Playwright scraper

        Returns:
            List of intelligence items
        """
        items = []
        cache_key = "news"

        # Try to get from cache first
        cached_news = self._read_cache(cache_key)
        if cached_news is not None:
            # Process cached news articles
            for article in cached_news:
                item = self._process_news_article(article)
                if item:
                    items.append(item)
            return items

        # Cache miss - scrape from Yahoo Finance with Playwright
        try:
            scraper = YahooNewsScraper(headless=True)
            news = await scraper.scrape_news(self.stock_symbol, max_articles=20)

            if not news:
                self.logger.info(f"No news found for {self.stock_symbol}")
                return items

            self.logger.info(f"Scraped {len(news)} news items for {self.stock_symbol}")

            # Cache the raw news data
            self._write_cache(cache_key, news)

            # Process news articles
            for article in news:
                item = self._process_news_article(article)
                if item:
                    items.append(item)

        except YahooNewsScraperError as e:
            self.logger.error(f"Error scraping news for {self.stock_symbol}: {e}")
            # Don't raise - return empty list so collection can continue with price data
        except Exception as e:
            self.logger.error(f"Unexpected error scraping news for {self.stock_symbol}: {e}")
            # Don't raise - return empty list so collection can continue with price data

        return items

    def _process_news_article(self, article: Dict[str, Any]) -> IntelligenceItemCreate | None:
        """
        Process a Yahoo Finance news article from Playwright scraper

        Args:
            article: News article dict from YahooNewsScraper with keys:
                - title: Article headline
                - url: Link to article
                - publisher: News source
                - published_date: datetime object
                - summary: Article description (optional)
                - thumbnail_url: Image URL (optional)

        Returns:
            IntelligenceItemCreate or None
        """
        try:
            title = article.get('title', 'Untitled')

            # Get publisher and construct content
            publisher = article.get('publisher', 'Unknown')
            content = f"Source: {publisher}"

            # Add summary if available
            summary = article.get('summary')
            if summary:
                content += f"\n\n{summary}"

            # Get URL (from scraper it's 'url', from old yfinance cache it was 'link')
            url = article.get('url') or article.get('link')

            # Get published date (already a datetime object from scraper)
            published_date = article.get('published_date')

            # Handle old cached data that might have timestamp instead
            if published_date is None and 'providerPublishTime' in article:
                published_date = datetime.fromtimestamp(article['providerPublishTime'])

            # Convert string datetime back to object if it was serialized in cache
            if isinstance(published_date, str):
                try:
                    published_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                except:
                    published_date = None

            return self._create_item(
                title=f"[{self.stock_symbol}] {title}",
                content=content,
                url=url,
                published_date=published_date,
                raw_data={
                    'stock_symbol': self.stock_symbol,
                    'publisher': publisher,
                    'type': 'news',
                    'thumbnail_url': article.get('thumbnail_url'),
                }
            )

        except Exception as e:
            self.logger.error(f"Error processing news article: {e}")
            return None
