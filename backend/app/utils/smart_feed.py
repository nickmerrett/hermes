"""Smart feed filtering utilities"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.database import PlatformSettings, IntelligenceItem, ProcessedIntelligence
import logging

logger = logging.getLogger(__name__)


def get_smart_feed_settings(db: Session) -> Dict[str, Any]:
    """
    Get smart feed configuration from database

    Returns default settings if not configured in database
    """
    try:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'smart_feed_config'
        ).first()

        if setting and setting.value:
            return setting.value
    except Exception as e:
        logger.warning(f"Error loading smart feed settings from database: {e}")

    # Return defaults if not configured
    return {
        'enabled': True,
        'min_priority': 0.3,
        'high_priority_threshold': 0.7,
        'recency_boost': {
            'enabled': True,
            'boost_amount': 0.1,
            'time_threshold_hours': 24
        },
        'category_preferences': {
            'product_update': False,
            'financial': True,
            'market_news': False,
            'competitor': True,
            'challenge': True,
            'opportunity': True,
            'leadership': True,
            'partnership': True,
            'advertisement': False,
            'unrelated': False,
            'other': False
        },
        'source_preferences': {
            'linkedin': True,
            'press_release': True,
            'reddit': False,
            'twitter': False,
            'rss': True,
            'google_news': False,
            'yahoo_finance_news': True,
            'yahoo_news': False,
            'australian_news': False,
            'news_api': False,
            'web_scraper': False
        },
        'diversity': {
            'enabled': True,
            'max_consecutive_same_source': 3
        }
    }


def calculate_effective_priority(
    item: IntelligenceItem,
    processed: Optional[ProcessedIntelligence],
    smart_config: Dict[str, Any]
) -> float:
    """
    Calculate effective priority with recency boost applied

    Args:
        item: The intelligence item
        processed: Processed intelligence data (may be None for unprocessed items)
        smart_config: Smart feed configuration

    Returns:
        Effective priority score (0.0 to 1.0+)
    """
    # Start with base priority
    base_priority = processed.priority_score if processed else 0.0

    # Apply recency boost if enabled
    recency_config = smart_config.get('recency_boost', {})
    if recency_config.get('enabled', True):
        boost_amount = recency_config.get('boost_amount', 0.1)
        time_threshold_hours = recency_config.get('time_threshold_hours', 24)

        # Use published_date or collected_date
        item_date = item.published_date or item.collected_date
        if item_date:
            time_since = datetime.utcnow() - item_date
            if time_since.total_seconds() < (time_threshold_hours * 3600):
                # Item is recent - apply boost
                base_priority += boost_amount
                logger.debug(f"Applied recency boost of {boost_amount} to item {item.id}")

    return base_priority


def should_include_item(
    item: IntelligenceItem,
    processed: Optional[ProcessedIntelligence],
    effective_priority: float,
    smart_config: Dict[str, Any]
) -> bool:
    """
    Determine if an item should be included in smart feed

    Args:
        item: The intelligence item
        processed: Processed intelligence data (may be None)
        effective_priority: Priority with recency boost applied
        smart_config: Smart feed configuration

    Returns:
        True if item should be included
    """
    min_priority = smart_config.get('min_priority', 0.3)
    high_priority_threshold = smart_config.get('high_priority_threshold', 0.7)

    # Check source preferences (always include if source is preferred)
    source_preferences = smart_config.get('source_preferences', {})
    if source_preferences.get(item.source_type, False):
        logger.debug(f"✓ Item {item.id} INCLUDED - preferred source: {item.source_type}")
        return True

    # Check category preferences (always include if category is preferred)
    if processed:
        category_preferences = smart_config.get('category_preferences', {})
        if category_preferences.get(processed.category, False):
            logger.debug(f"✓ Item {item.id} INCLUDED - preferred category: {processed.category}")
            return True

    # High priority items always show
    if effective_priority >= high_priority_threshold:
        logger.debug(f"Including item {item.id} - high priority: {effective_priority:.2f}")
        return True

    # Check against minimum priority threshold
    if effective_priority >= min_priority:
        logger.debug(f"✓ Item {item.id} INCLUDED - meets min priority {effective_priority:.2f} >= {min_priority}")
        return True

    # Log why item was filtered out
    category = processed.category if processed else 'unknown'
    logger.debug(f"✗ Item {item.id} FILTERED OUT - source:{item.source_type} category:{category} priority:{effective_priority:.2f} < {min_priority}")
    return False


def apply_diversity_control(
    items: List[IntelligenceItem],
    smart_config: Dict[str, Any]
) -> List[IntelligenceItem]:
    """
    Apply diversity control to prevent feed domination by single source

    This reorders items to ensure variety while maintaining overall priority order

    Args:
        items: List of items (already sorted by priority/date)
        smart_config: Smart feed configuration

    Returns:
        Reordered list with diversity applied
    """
    diversity_config = smart_config.get('diversity', {})
    if not diversity_config.get('enabled', True):
        return items

    max_consecutive = diversity_config.get('max_consecutive_same_source', 3)

    if len(items) <= max_consecutive:
        # Not enough items to need diversity control
        return items

    result = []
    source_count = {}
    consecutive_count = 0
    last_source = None

    # Create a working copy we can pop from
    remaining = list(items)

    while remaining:
        # Try to find next item that maintains diversity
        found = False

        for i, item in enumerate(remaining):
            source = item.source_type

            # If this is a different source, reset consecutive count
            if source != last_source:
                consecutive_count = 1
                last_source = source
                result.append(item)
                remaining.pop(i)
                found = True
                break

            # Same source - check if we're within limit
            if consecutive_count < max_consecutive:
                consecutive_count += 1
                result.append(item)
                remaining.pop(i)
                found = True
                break

        # If we couldn't find a suitable item (all remaining are same source and we hit limit)
        # Just take the next one anyway to avoid infinite loop
        if not found:
            item = remaining.pop(0)
            result.append(item)
            last_source = item.source_type
            consecutive_count = 1

    logger.debug(f"Applied diversity control: {len(items)} items")
    return result
