"""Collection orchestration - coordinates data gathering from all sources"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, List
import yaml
import os

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.vector_store import get_vector_store
from app.models.database import Customer, Source, IntelligenceItem, ProcessedIntelligence, CollectionJob, CollectionStatus
from app.utils.deduplication import normalize_url, is_similar_title
from app.utils.clustering import cluster_item
from app.utils.rate_limiter import GlobalRateLimiter, TaskQueue
from app.collectors.news_collector import NewsAPICollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.yahoo_finance_news_collector import YahooFinanceNewsCollector
from app.collectors.reddit_collector import RedditCollector
from app.collectors.hackernews_collector import HackerNewsCollector
from app.collectors.github_collector import GitHubCollector
from app.collectors.twitter_collector import TwitterCollector
from app.collectors.linkedin_collector import LinkedInCollector, LinkedInUserCollector

# Try to import Playwright collector (optional)
try:
    from app.collectors.linkedin_playwright_collector import PlaywrightLinkedInCollector, get_linkedin_settings
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightLinkedInCollector = None
    get_linkedin_settings = None
from app.collectors.pressrelease_collector import PressReleaseCollector
from app.collectors.australian_news_collector import AustralianNewsCollector
from app.collectors.web_scraper_collector import WebScraperCollector
from app.collectors.google_news_collector import GoogleNewsCollector
from app.processors.ai_processor import get_ai_processor
from app.config.settings import settings

logger = logging.getLogger(__name__)


def update_collection_status(
    db: Session,
    customer_id: int,
    source_type: str,
    success: bool,
    error_message: Optional[str] = None
):
    """
    Update or create collection status for a source

    Args:
        db: Database session
        customer_id: Customer ID
        source_type: Source type (reddit, linkedin_user, etc.)
        success: Whether the collection succeeded
        error_message: Error message if failed
    """
    try:
        # Find existing status or create new
        status = db.query(CollectionStatus).filter(
            CollectionStatus.customer_id == customer_id,
            CollectionStatus.source_type == source_type
        ).first()

        now = datetime.utcnow()

        if not status:
            status = CollectionStatus(
                customer_id=customer_id,
                source_type=source_type,
                status='success' if success else 'error',
                last_run=now,
                last_success=now if success else None,
                error_message=error_message,
                error_count=0 if success else 1
            )
            db.add(status)
        else:
            status.last_run = now
            status.updated_at = now

            if success:
                status.status = 'success'
                status.last_success = now
                status.error_count = 0
                status.error_message = None
            else:
                # Check if error is auth-related
                if error_message and ('auth' in error_message.lower() or
                                     'login' in error_message.lower() or
                                     'credential' in error_message.lower() or
                                     'forbidden' in error_message.lower() or
                                     '401' in error_message or
                                     '403' in error_message):
                    status.status = 'auth_required'
                else:
                    status.status = 'error'

                status.error_message = error_message
                status.error_count = (status.error_count or 0) + 1

        db.commit()

    except Exception as e:
        logger.error(f"Error updating collection status: {e}")
        db.rollback()


def load_customers_from_config() -> List[dict]:
    """Load customer configurations from YAML file"""
    config_path = settings.customers_config_path

    if not os.path.exists(config_path):
        logger.warning(f"Customer config file not found: {config_path}")
        return []

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('customers', [])
    except Exception as e:
        logger.error(f"Error loading customer config: {e}")
        return []


def export_customers_to_yaml(db: Session, output_path: Optional[str] = None):
    """
    Export all customers from database to YAML file

    Args:
        db: Database session
        output_path: Optional path to write YAML (defaults to customers_config_path)

    Returns:
        str: Path where YAML was written
    """
    if output_path is None:
        output_path = settings.customers_config_path

    # Get all customers from database
    customers = db.query(Customer).all()

    yaml_customers = []

    for customer in customers:
        config = customer.config or {}

        # Build YAML structure (nested format)
        yaml_customer = {
            'name': customer.name,
            'domain': customer.domain,
            'description': config.get('description'),
            'keywords': customer.keywords or [],
            'competitors': customer.competitors or [],
            'stock_symbol': customer.stock_symbol,
            'rss_feeds': config.get('rss_feeds', []),
            'twitter_handle': config.get('twitter_handle'),
            'linkedin_company_id': config.get('linkedin_company_id'),
            'linkedin_company_url': config.get('linkedin_company_url'),
            'linkedin_user_profiles': config.get('linkedin_user_profiles', []),
            'github_org': config.get('github_org'),
            'github_repos': config.get('github_repos', []),
            'collection_config': {
                'news_enabled': config.get('news_enabled', True),
                'yahoo_finance_news_enabled': config.get('yahoo_finance_news_enabled', False),
                'rss_enabled': config.get('rss_enabled', True),
                'australian_news_enabled': config.get('australian_news_enabled', True),
                'google_news_enabled': config.get('google_news_enabled', True),
                'reddit_enabled': config.get('reddit_enabled', False),
                'hackernews_enabled': config.get('hackernews_enabled', False),
                'github_enabled': config.get('github_enabled', False),
                'twitter_enabled': config.get('twitter_enabled', False),
                'linkedin_enabled': config.get('linkedin_enabled', False),
                'linkedin_user_enabled': config.get('linkedin_user_enabled', False),
                'pressrelease_enabled': config.get('pressrelease_enabled', False),
                'reddit_subreddits': config.get('reddit_subreddits', []),
                'priority_keywords': config.get('priority_keywords', []),
                'web_scrape_sources': config.get('web_scrape_sources', [])
            },
            'notes': config.get('notes')
        }

        # Remove None values for cleaner YAML
        yaml_customer = {k: v for k, v in yaml_customer.items() if v is not None}

        yaml_customers.append(yaml_customer)

    # Write to YAML
    yaml_data = {'customers': yaml_customers}

    with open(output_path, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info(f"Exported {len(yaml_customers)} customers to {output_path}")
    return output_path


def sync_customers_to_db(db: Session):
    """
    Sync customers from config file to database

    Data Structure:
    - YAML: Nested structure with 'collection_config' as a separate section
    - Database: Flat structure - all fields stored at top level of customer.config JSON
    - Example DB structure:
      customer.config = {
          # Collection source toggles
          "news_enabled": true,
          "reddit_enabled": true,
          "priority_keywords": [...],
          "web_scrape_sources": [...],
          # Additional config fields
          "description": "...",
          "notes": "...",
          "twitter_handle": "@company",
          "linkedin_user_profiles": [...]
      }
    """
    config_customers = load_customers_from_config()

    for cust_config in config_customers:
        # Check if customer exists
        existing = db.query(Customer).filter(
            Customer.name == cust_config['name']
        ).first()

        # Prepare full config - merge collection_config with other top-level config fields
        # This creates a flat structure with all config fields at the same level
        full_config = cust_config.get('collection_config', {}).copy()

        # Add all other config fields from YAML
        config_fields = [
            'description', 'notes', 'twitter_handle', 'linkedin_company_url',
            'linkedin_company_id', 'github_org', 'github_repos', 'rss_feeds',
            'linkedin_user_profiles'
        ]
        for field in config_fields:
            if field in cust_config:
                full_config[field] = cust_config[field]

        if existing:
            # Update existing customer
            customer = existing
            customer.domain = cust_config.get('domain')
            customer.keywords = cust_config.get('keywords', [])
            customer.competitors = cust_config.get('competitors', [])
            customer.stock_symbol = cust_config.get('stock_symbol')
            customer.config = full_config
            logger.info(f"Updated customer from config: {customer.name}")
        else:
            # Create new customer
            customer = Customer(
                name=cust_config['name'],
                domain=cust_config.get('domain'),
                keywords=cust_config.get('keywords', []),
                competitors=cust_config.get('competitors', []),
                stock_symbol=cust_config.get('stock_symbol'),
                config=full_config
            )
            db.add(customer)
            logger.info(f"Added customer from config: {customer.name}")

        db.commit()
        db.refresh(customer)

        # Sync RSS feed sources
        config_feeds = {feed['url']: feed for feed in cust_config.get('rss_feeds', [])}

        # Get existing RSS sources for this customer
        existing_sources = db.query(Source).filter(
            Source.customer_id == customer.id,
            Source.type == 'rss'
        ).all()

        # Delete sources not in config
        for source in existing_sources:
            if source.url not in config_feeds:
                logger.info(f"Removing RSS source not in config: {source.name} ({source.url})")
                db.delete(source)

        # Add or update sources from config
        existing_urls = {s.url for s in existing_sources}
        for feed_url, feed_data in config_feeds.items():
            if feed_url not in existing_urls:
                source = Source(
                    customer_id=customer.id,
                    type='rss',
                    name=feed_data.get('name', 'RSS Feed'),
                    url=feed_url,
                    enabled=True
                )
                db.add(source)
                logger.info(f"Added RSS source: {source.name} ({feed_url})")

        db.commit()


async def collect_for_customer(customer: Customer, db: Session) -> dict:
    """
    Collect intelligence for a single customer

    Returns:
        Dict with collection statistics including failed AI processing count
    """
    logger.info(f"Starting collection for customer: {customer.name}")

    items_collected = 0
    items_failed_processing = 0
    errors = []

    # Prepare customer config for collectors
    customer_config = {
        'id': customer.id,
        'name': customer.name,
        'domain': customer.domain,
        'keywords': customer.keywords,
        'competitors': customer.competitors,
        'stock_symbol': customer.stock_symbol,
        'config': customer.config or {}
    }

    collection_config = customer.config or {}

    # Collect from NewsAPI
    if collection_config.get('news_enabled', True):
        try:
            if settings.news_api_key:
                collector = NewsAPICollector(customer_config)
                items, error = await collector.safe_collect()
                if items:
                    failed = await save_and_process_items(items, customer, db)
                    items_collected += len(items)
                    items_failed_processing += failed
                if error:
                    errors.append(error)
        except Exception as e:
            error_msg = f"NewsAPI collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Collect from Yahoo Finance news
    if collection_config.get('yahoo_finance_news_enabled', False) and customer.stock_symbol:
        try:
            collector = YahooFinanceNewsCollector(customer_config)
            items, error = await collector.safe_collect()
            if items:
                await save_and_process_items(items, customer, db)
                items_collected += len(items)
            if error:
                errors.append(error)
        except Exception as e:
            error_msg = f"Yahoo Finance news collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Collect from RSS feeds
    if collection_config.get('rss_enabled', True):
        rss_sources = db.query(Source).filter(
            Source.customer_id == customer.id,
            Source.type == 'rss',
            Source.enabled == True
        ).all()

        for source in rss_sources:
            try:
                feed_config = {
                    'url': source.url,
                    'name': source.name,
                    'source_id': source.id
                }
                collector = RSSCollector(customer_config, feed_config)
                items, error = await collector.safe_collect()

                if items:
                    failed = await save_and_process_items(items, customer, db)
                    items_collected += len(items)
                    items_failed_processing += failed

                # Update source status
                source.last_run = datetime.utcnow()
                source.last_status = 'success' if not error else 'failed'
                db.commit()

                if error:
                    errors.append(error)

            except Exception as e:
                error_msg = f"RSS collection error for {source.name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

    # Collect from Reddit
    if collection_config.get('reddit_enabled', False):
        try:
            if settings.reddit_client_id and settings.reddit_client_secret:
                collector = RedditCollector(customer_config, db=db)
                items, error = await collector.safe_collect()

                # Update collection status
                update_collection_status(
                    db=db,
                    customer_id=customer.id,
                    source_type='reddit',
                    success=(error is None),
                    error_message=error
                )

                if items:
                    failed = await save_and_process_items(items, customer, db)
                    items_collected += len(items)
                    items_failed_processing += failed
                if error:
                    errors.append(error)
        except Exception as e:
            error_msg = f"Reddit collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

            # Update collection status for exception
            update_collection_status(
                db=db,
                customer_id=customer.id,
                source_type='reddit',
                success=False,
                error_message=error_msg
            )

    # Collect from Hacker News
    if collection_config.get('hackernews_enabled', False):
        try:
            collector = HackerNewsCollector(customer_config)
            items, error = await collector.safe_collect()
            if items:
                await save_and_process_items(items, customer, db)
                items_collected += len(items)
            if error:
                errors.append(error)
        except Exception as e:
            error_msg = f"Hacker News collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Collect from GitHub
    if collection_config.get('github_enabled', False):
        try:
            collector = GitHubCollector(customer_config)
            items, error = await collector.safe_collect()
            if items:
                await save_and_process_items(items, customer, db)
                items_collected += len(items)
            if error:
                errors.append(error)
        except Exception as e:
            error_msg = f"GitHub collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Collect from Twitter/X
    if collection_config.get('twitter_enabled', False):
        try:
            if settings.twitter_bearer_token:
                collector = TwitterCollector(customer_config)
                items, error = await collector.safe_collect()
                if items:
                    failed = await save_and_process_items(items, customer, db)
                    items_collected += len(items)
                    items_failed_processing += failed
                if error:
                    errors.append(error)
        except Exception as e:
            error_msg = f"Twitter collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Collect from LinkedIn (company pages)
    if collection_config.get('linkedin_enabled', False):
        try:
            collector = LinkedInCollector(customer_config)
            items, error = await collector.safe_collect()
            if items:
                await save_and_process_items(items, customer, db)
                items_collected += len(items)
            if error:
                errors.append(error)
        except Exception as e:
            error_msg = f"LinkedIn collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Collect from LinkedIn (individual user profiles)
    if collection_config.get('linkedin_user_enabled', False):
        try:
            # Use Playwright collector if available, otherwise fall back to basic collector
            if PLAYWRIGHT_AVAILABLE and PlaywrightLinkedInCollector:
                logger.info("Using Playwright-based LinkedIn collector with incremental processing")
                collector = PlaywrightLinkedInCollector(customer_config, db=db)

                # Define callback for incremental item processing (items show up immediately in UI)
                async def process_linkedin_items_callback(items: List):
                    """Process and save items immediately after each profile is collected"""
                    if items:
                        await save_and_process_items(items, customer, db)
                        nonlocal items_collected
                        items_collected += len(items)
                        logger.info(f"✅ Saved {len(items)} LinkedIn items to database (visible in UI now)")

                # Collect with callback - items are processed as they're collected
                items, error = await collector.safe_collect(process_items_callback=process_linkedin_items_callback)

            else:
                logger.warning("Playwright not available, using basic LinkedIn collector (limited functionality)")
                collector = LinkedInUserCollector(customer_config)
                items, error = await collector.safe_collect()

                # For basic collector, save items in bulk (no incremental support)
                if items:
                    await save_and_process_items(items, customer, db)
                    items_collected += len(items)

            # Update collection status
            update_collection_status(
                db=db,
                customer_id=customer.id,
                source_type='linkedin_user',
                success=(error is None),
                error_message=error
            )

            if error:
                errors.append(error)

            # CRITICAL: Add delay after LinkedIn collection to avoid rate limiting across customers
            # LinkedIn tracks requests globally, not per-customer
            # Load configured delays from database
            if get_linkedin_settings:
                linkedin_settings = get_linkedin_settings(db)
                delay_min = linkedin_settings.get('delay_between_customers_min', 300.0)
                delay_max = linkedin_settings.get('delay_between_customers_max', 600.0)
            else:
                # Fallback to old aggressive timing if Playwright not available
                delay_min, delay_max = 10.0, 15.0

            delay = random.uniform(delay_min, delay_max)
            logger.info(f"⏰ LinkedIn collection complete. Waiting {delay:.1f}s ({delay/60:.1f} min) before next customer to avoid rate limits")
            await asyncio.sleep(delay)

        except Exception as e:
            error_msg = f"LinkedIn user profile collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

            # Update collection status for exception
            update_collection_status(
                db=db,
                customer_id=customer.id,
                source_type='linkedin_user',
                success=False,
                error_message=error_msg
            )

            # Still add delay even on error to avoid hammering LinkedIn
            # Use 30% of configured delay for errors
            if get_linkedin_settings:
                linkedin_settings = get_linkedin_settings(db)
                error_delay_min = linkedin_settings.get('delay_between_customers_min', 300.0) * 0.3
                error_delay_max = linkedin_settings.get('delay_between_customers_max', 600.0) * 0.3
            else:
                error_delay_min, error_delay_max = 5.0, 10.0

            error_delay = random.uniform(error_delay_min, error_delay_max)
            logger.info(f"⏰ Error occurred. Waiting {error_delay:.1f}s before continuing")
            await asyncio.sleep(error_delay)

    # Collect from Press Release Services
    if collection_config.get('pressrelease_enabled', False):
        try:
            collector = PressReleaseCollector(customer_config)
            items, error = await collector.safe_collect()
            if items:
                await save_and_process_items(items, customer, db)
                items_collected += len(items)
            if error:
                errors.append(error)
        except Exception as e:
            error_msg = f"Press release collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Collect from Australian News Sites
    if collection_config.get('australian_news_enabled', True):  # Enabled by default
        try:
            collector = AustralianNewsCollector(customer_config)
            items, error = await collector.safe_collect()
            if items:
                await save_and_process_items(items, customer, db)
                items_collected += len(items)
            if error:
                errors.append(error)
        except Exception as e:
            error_msg = f"Australian news collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Collect from Google News
    if collection_config.get('google_news_enabled', True):  # Enabled by default
        try:
            collector = GoogleNewsCollector(customer_config)
            items, error = await collector.safe_collect()
            if items:
                await save_and_process_items(items, customer, db)
                items_collected += len(items)
            if error:
                errors.append(error)
        except Exception as e:
            error_msg = f"Google News collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Collect from Web Scraper Sources
    if collection_config.get('web_scrape_sources'):
        try:
            collector = WebScraperCollector(customer_config)
            items, error = await collector.safe_collect()
            if items:
                await save_and_process_items(items, customer, db)
                items_collected += len(items)
            if error:
                errors.append(error)
        except Exception as e:
            error_msg = f"Web scraper collection error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    logger.info(f"Completed collection for {customer.name}: {items_collected} items ({items_failed_processing} failed AI processing)")

    return {
        'customer_id': customer.id,
        'items_collected': items_collected,
        'items_failed_processing': items_failed_processing,
        'errors': errors
    }


async def save_and_process_items(items: List, customer: Customer, db: Session) -> int:
    """
    Save items to database and process with AI

    Args:
        items: List of IntelligenceItemCreate objects
        customer: Customer object
        db: Database session

    Returns:
        Number of items that failed AI processing
    """
    ai_processor = get_ai_processor()
    vector_store = get_vector_store()
    failed_processing_count = 0

    for item_create in items:
        # Level 1 Deduplication: Check by normalized URL
        if item_create.url:
            normalized_url = normalize_url(item_create.url)

            # Check for exact URL match first
            existing = db.query(IntelligenceItem).filter(
                IntelligenceItem.url == item_create.url
            ).first()

            if existing:
                logger.debug(f"Duplicate URL (exact): {item_create.url}")
                continue

            # Check for normalized URL match (catches tracking params, AMP, etc.)
            if normalized_url != item_create.url:
                existing_normalized = db.query(IntelligenceItem).filter(
                    IntelligenceItem.url == normalized_url
                ).first()

                if existing_normalized:
                    logger.debug(f"Duplicate URL (normalized): {item_create.url} -> {normalized_url}")
                    continue

        # Level 2 Deduplication: Check for similar title within 24 hours
        # This catches duplicate stories from different sources
        if item_create.title and item_create.published_date:
            # Look for similar articles published within 24 hours
            time_window_start = item_create.published_date - timedelta(hours=24)
            time_window_end = item_create.published_date + timedelta(hours=24)

            recent_items = db.query(IntelligenceItem).filter(
                IntelligenceItem.customer_id == item_create.customer_id,
                IntelligenceItem.published_date >= time_window_start,
                IntelligenceItem.published_date <= time_window_end
            ).all()

            # Check if any existing item has a similar title
            is_duplicate = False
            for existing_item in recent_items:
                if is_similar_title(item_create.title, existing_item.title, threshold=0.85):
                    logger.debug(
                        f"Duplicate title (similarity): '{item_create.title}' "
                        f"similar to existing '{existing_item.title}'"
                    )
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

        # Create intelligence item
        db_item = IntelligenceItem(
            customer_id=item_create.customer_id,
            source_id=item_create.source_id,
            source_type=item_create.source_type,
            title=item_create.title,
            content=item_create.content,
            url=item_create.url,
            published_date=item_create.published_date,
            raw_data=item_create.raw_data
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)

        # Process with AI (with retry logic)
        processing_succeeded = False
        processing_error = None
        processed_data = None
        max_retries = 3

        # Extract customer context for better AI processing
        customer_config = customer.config or {}
        keywords = customer.keywords or []
        competitors = customer.competitors or []
        priority_keywords = customer_config.get('priority_keywords', [])

        for attempt in range(max_retries):
            try:
                # Exponential backoff: wait 2^attempt seconds between retries
                if attempt > 0:
                    import asyncio
                    import time
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying AI processing for item {db_item.id} (attempt {attempt + 1}/{max_retries}) after {wait_time}s...")
                    await asyncio.sleep(wait_time)

                processed_data = await ai_processor.process_item(
                    title=db_item.title,
                    content=db_item.content or "",
                    customer_name=customer.name,
                    source_type=db_item.source_type,
                    keywords=keywords,
                    competitors=competitors,
                    priority_keywords=priority_keywords
                )

                # If we got here, processing succeeded
                processing_succeeded = True
                break

            except Exception as e:
                processing_error = str(e)
                logger.warning(f"AI processing attempt {attempt + 1}/{max_retries} failed for item {db_item.id}: {e}")
                if attempt == max_retries - 1:
                    # Last attempt failed
                    logger.error(f"All {max_retries} AI processing attempts failed for item {db_item.id}: {e}")
                    failed_processing_count += 1

        # Handle successful or failed processing
        if processing_succeeded and processed_data:
            # Check if item is relevant
            if not processed_data.get('is_relevant', True):
                # Item is not relevant - mark as "unrelated" instead of deleting
                logger.info(f"Marking item as unrelated: {db_item.title[:50]}...")
                processed_data['category'] = 'unrelated'
                # Keep low priority for unrelated items
                processed_data['priority_score'] = min(processed_data.get('priority_score', 0.1), 0.3)

            # Save processed data (successful processing)
            processed = ProcessedIntelligence(
                item_id=db_item.id,
                summary=processed_data['summary'],
                category=processed_data['category'],
                sentiment=processed_data['sentiment'],
                priority_score=processed_data['priority_score'],
                entities=processed_data['entities'],
                tags=processed_data['tags'],
                needs_reprocessing=False,
                processing_attempts=max_retries if max_retries > 1 else 1,
                last_processing_attempt=datetime.utcnow()
            )
            db.add(processed)
            db.commit()

            # Add to vector store for semantic search
            embedding_added = False
            item_embedding = None
            try:
                text_for_embedding = f"{db_item.title}\n\n{db_item.content or ''}"
                vector_store.add_item(
                    item_id=db_item.id,
                    text=text_for_embedding,
                    metadata={
                        'customer_id': customer.id,
                        'source_type': db_item.source_type,
                        'category': processed_data['category'],
                        'priority': processed_data['priority_score']
                    }
                )
                embedding_added = True

                # Get the embedding we just created for clustering
                item_embedding = vector_store.get_embedding(db_item.id)
            except Exception as e:
                logger.error(f"Error adding item {db_item.id} to vector store: {e}")

            # Story clustering - group similar items from different sources
            # Settings (threshold, time window, enabled) are loaded from database
            if embedding_added and item_embedding:
                try:
                    cluster_id = cluster_item(
                        item=db_item,
                        item_embedding=item_embedding,
                        db=db
                    )
                    logger.debug(f"Item {db_item.id} assigned to cluster {cluster_id}")
                except Exception as e:
                    logger.error(f"Error clustering item {db_item.id}: {e}")

            logger.debug(f"Processed and saved item: {db_item.title[:50]}...")

        else:
            # Processing failed after all retries - save with default values and mark for reprocessing
            logger.error(f"Saving item {db_item.id} with default values due to AI processing failure")

            # Use minimal default summary
            default_summary = db_item.title[:200] if db_item.title else (db_item.content or "")[:200]

            processed = ProcessedIntelligence(
                item_id=db_item.id,
                summary=default_summary,
                category='other',
                sentiment='neutral',
                priority_score=0.5,
                entities={'companies': [], 'technologies': [], 'people': []},
                tags=[],
                needs_reprocessing=True,
                processing_attempts=max_retries,
                last_processing_error=processing_error,
                last_processing_attempt=datetime.utcnow()
            )
            db.add(processed)
            db.commit()

    return failed_processing_count


async def collect_customer_wrapper(customer_id: int, customer_name: str, global_rate_limiter: GlobalRateLimiter) -> dict:
    """
    Wrapper for collecting a single customer with its own DB session.

    This wrapper ensures each parallel task has its own database session
    since SQLAlchemy sessions are not thread-safe.

    Args:
        customer_id: ID of customer to collect for
        customer_name: Name of customer (for logging)
        global_rate_limiter: Shared rate limiter instance

    Returns:
        Dict with collection results
    """
    db = SessionLocal()

    try:
        logger.info(f"Starting parallel collection for customer: {customer_name} (ID: {customer_id})")

        # Load customer in this session (not shared across sessions)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()

        if not customer:
            logger.error(f"Customer {customer_id} not found in database")
            return {
                'items_collected': 0,
                'items_failed_processing': 0,
                'errors': [f"Customer {customer_id} not found"]
            }

        # Collect for this customer (pass rate limiter for future use)
        result = await collect_for_customer(customer, db)

        logger.info(
            f"Completed collection for {customer.name}: "
            f"{result['items_collected']} items, "
            f"{len(result['errors'])} errors"
        )

        return result

    except Exception as e:
        logger.error(f"Error collecting for customer {customer_name}: {e}", exc_info=True)
        return {
            'items_collected': 0,
            'items_failed_processing': 0,
            'errors': [f"Collection failed for {customer_name}: {str(e)}"]
        }
    finally:
        db.close()


async def run_collection_async(customer_id: Optional[int] = None, max_concurrent: int = 4):
    """
    Run collection job with parallel execution using TaskQueue

    Args:
        customer_id: If provided, collect only for this customer.
                    Otherwise, collect for all customers.
        max_concurrent: Maximum number of customers to collect concurrently

    Note: Uses GlobalRateLimiter to coordinate rate limits across all sources
          and TaskQueue for parallel execution of customer collections.
    """
    db = SessionLocal()

    try:
        # Get customers to collect for (from database - source of truth)
        query = db.query(Customer)
        if customer_id:
            query = query.filter(Customer.id == customer_id)

        customers = query.all()

        if not customers:
            logger.warning("No customers found for collection")
            return

        logger.info(f"Starting parallel collection for {len(customers)} customer(s) "
                   f"with max {max_concurrent} concurrent workers")

        # Create collection job record
        job = CollectionJob(
            job_type='manual' if customer_id else 'scheduled',
            customer_id=customer_id,
            status='running'
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Initialize global rate limiter
        global_rate_limiter = GlobalRateLimiter()

        # Initialize task queue with worker pool
        task_queue = TaskQueue(max_concurrent=max_concurrent)
        await task_queue.start_workers()

        # Enqueue all customer collections
        # Pass customer ID and name instead of object to avoid session conflicts
        for customer in customers:
            await task_queue.add_task(
                collect_customer_wrapper,
                customer.id,
                customer.name,
                global_rate_limiter
            )

        # Wait for all collections to complete
        await task_queue.wait_completion()

        # Stop workers
        await task_queue.stop_workers()

        # Aggregate results from all customer collections
        results = task_queue.get_results()
        total_items = sum(r['items_collected'] for r in results)
        total_failed_processing = sum(r.get('items_failed_processing', 0) for r in results)
        all_errors = []
        for r in results:
            all_errors.extend(r['errors'])

        # Add any task-level errors
        all_errors.extend(task_queue.get_errors())

        # Log rate limiter statistics
        stats = await global_rate_limiter.get_stats()
        logger.info("Rate limiter statistics:")
        for source, stat in stats.items():
            if stat['current_requests'] > 0:
                logger.info(
                    f"  {source}: {stat['current_requests']}/{stat['max_requests']} "
                    f"requests ({stat['utilization']:.1%} utilization)"
                )

        # Update job status
        job.status = 'completed' if not all_errors else 'completed_with_errors'
        job.completed_at = datetime.utcnow()
        job.items_collected = total_items
        job.items_failed_processing = total_failed_processing
        if all_errors:
            job.error_message = '; '.join(all_errors[:5])  # Store first 5 errors
        db.commit()

        logger.info(
            f"Parallel collection completed: {total_items} items collected "
            f"({total_failed_processing} failed AI processing), {len(all_errors)} errors"
        )

    except Exception as e:
        logger.error(f"Collection job failed: {e}", exc_info=True)
        if 'job' in locals():
            job.status = 'failed'
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            db.commit()

    finally:
        db.close()


def run_collection(customer_id: Optional[int] = None):
    """
    Run collection job (synchronous wrapper for async implementation)

    Args:
        customer_id: If provided, collect only for this customer.
                    Otherwise, collect for all customers.

    Note: Database is the source of truth. Customers are managed via UI.
          Use './hermes-diag sync-config' to import from YAML if needed.
    """
    import asyncio

    # Determine concurrent workers based on whether single customer or all
    max_concurrent = 1 if customer_id else 4

    # Run the async collection
    asyncio.run(run_collection_async(customer_id, max_concurrent))


def purge_old_items(retention_days: int = None):
    """
    Purge intelligence items older than retention_days

    Args:
        retention_days: Number of days to retain items.
                       If None, uses settings.intelligence_retention_days
    """
    if retention_days is None:
        retention_days = settings.intelligence_retention_days

    db = SessionLocal()

    try:
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        logger.info(f"Starting purge of items older than {retention_days} days (before {cutoff_date})")

        # Find old items
        old_items = db.query(IntelligenceItem).filter(
            IntelligenceItem.created_at < cutoff_date
        ).all()

        if not old_items:
            logger.info("No items to purge")
            return

        logger.info(f"Found {len(old_items)} items to purge")

        # Get vector store
        vector_store = get_vector_store()

        # Delete each item
        deleted_count = 0
        for item in old_items:
            try:
                # Delete from vector store first
                try:
                    vector_store.delete_item(item.id)
                except Exception as e:
                    logger.debug(f"Error deleting item {item.id} from vector store: {e}")

                # Delete from database (cascade will delete ProcessedIntelligence)
                db.delete(item)
                deleted_count += 1

            except Exception as e:
                logger.error(f"Error deleting item {item.id}: {e}")
                continue

        # Commit all deletions
        db.commit()

        logger.info(f"Successfully purged {deleted_count} items older than {retention_days} days")

    except Exception as e:
        logger.error(f"Purge job failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
