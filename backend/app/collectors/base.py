"""Base collector interface for data sources"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from app.models.schemas import IntelligenceItemCreate

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    Abstract base class for all data collectors

    Each collector is responsible for:
    1. Fetching data from a specific source
    2. Transforming it into IntelligenceItemCreate objects
    3. Handling rate limiting and errors
    """

    def __init__(self, customer_config: Dict[str, Any]):
        """
        Initialize collector with customer configuration

        Args:
            customer_config: Customer-specific configuration including
                            keywords, domain, competitors, etc.
        """
        self.customer_config = customer_config
        self.customer_id = customer_config.get('id')
        self.customer_name = customer_config.get('name')
        self.keywords = customer_config.get('keywords', [])
        self.domain = customer_config.get('domain')
        self.excluded_keywords = customer_config.get('excluded_keywords', [])
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @staticmethod
    def is_url_blacklisted(url: Optional[str], blacklist_config: Dict[str, Any]) -> bool:
        """
        Check if a URL contains a blacklisted domain

        Args:
            url: URL to check
            blacklist_config: Domain blacklist configuration from collection_config

        Returns:
            True if URL is blacklisted, False otherwise
        """
        if not url or not blacklist_config.get('enabled', True):
            return False

        blacklisted_domains = blacklist_config.get('domains', [])
        url_lower = url.lower()

        for domain in blacklisted_domains:
            if domain.lower() in url_lower:
                logger.info(f"URL blocked by blacklist: {url} (contains {domain})")
                return True

        return False

    @abstractmethod
    async def collect(self) -> List[IntelligenceItemCreate]:
        """
        Collect intelligence items from the source

        Returns:
            List of IntelligenceItemCreate objects
        """
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """
        Get the source type identifier

        Returns:
            Source type string (e.g., 'news_api', 'rss', 'stock')
        """
        pass

    def _create_item(
        self,
        title: str,
        content: Optional[str],
        url: Optional[str],
        published_date: Optional[datetime],
        raw_data: Optional[Dict[str, Any]] = None,
        source_id: Optional[int] = None
    ) -> IntelligenceItemCreate:
        """
        Helper method to create an IntelligenceItemCreate object

        Args:
            title: Item title
            content: Item content/description
            url: Source URL
            published_date: Publication date
            raw_data: Original data from source
            source_id: Database source ID

        Returns:
            IntelligenceItemCreate object
        """
        return IntelligenceItemCreate(
            customer_id=self.customer_id,
            source_id=source_id,
            source_type=self.get_source_type(),
            title=title,
            content=content,
            url=url,
            published_date=published_date,
            raw_data=raw_data or {}
        )

    def _should_collect_item(self, title: str, content: str = "", title_only: bool = False) -> bool:
        """
        Check if an item is relevant based on keywords and excluded_keywords.

        Args:
            title: Item title
            content: Item content
            title_only: If True, only check the title (ignores content).
                        Use this for sources like Google News where the
                        description is often HTML noise or untrustworthy.

        Returns:
            True if item should be collected
        """
        title_lower = title.lower()
        text = title_lower if title_only else f"{title_lower} {content.lower()}"

        # Negative keyword check — runs regardless of positive keyword config
        for excluded in self.excluded_keywords:
            if excluded.lower() in title_lower:
                self.logger.debug(f"Excluded by negative keyword '{excluded}': {title[:80]}")
                return False

        # Positive keyword check — if no keywords configured, allow everything
        if not self.keywords:
            return True

        for keyword in self.keywords:
            if keyword.lower() in text:
                return True

        return False

    async def safe_collect(self, **kwargs) -> tuple[List[IntelligenceItemCreate], Optional[str]]:
        """
        Safely collect items with error handling

        Args:
            **kwargs: Additional arguments to pass to collect() (e.g., process_items_callback)

        Returns:
            Tuple of (items, error_message)
        """
        try:
            items = await self.collect(**kwargs)
            self.logger.info(
                f"Collected {len(items)} items from {self.get_source_type()} "
                f"for customer {self.customer_name}"
            )
            return items, None
        except Exception as e:
            error_msg = f"Error collecting from {self.get_source_type()}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return [], error_msg


class RateLimitedCollector(BaseCollector):
    """
    Base class for collectors that need rate limiting
    """

    def __init__(self, customer_config: Dict[str, Any], rate_limit: int = 60):
        """
        Initialize rate-limited collector

        Args:
            customer_config: Customer configuration
            rate_limit: Maximum requests per minute
        """
        super().__init__(customer_config)
        self.rate_limit = rate_limit
        self.request_count = 0
        self.last_reset = datetime.now()

    def _check_rate_limit(self) -> bool:
        """
        Check if rate limit has been exceeded

        Returns:
            True if within rate limit
        """
        now = datetime.now()
        elapsed = (now - self.last_reset).total_seconds()

        # Reset counter after 60 seconds
        if elapsed >= 60:
            self.request_count = 0
            self.last_reset = now

        # Check if under limit
        if self.request_count >= self.rate_limit:
            self.logger.warning(f"Rate limit exceeded for {self.get_source_type()}")
            return False

        self.request_count += 1
        return True
