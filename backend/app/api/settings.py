"""Platform settings API endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from pydantic import BaseModel

from app.core.database import get_db
from app.models.database import PlatformSettings

router = APIRouter()


class PlatformSettingsUpdate(BaseModel):
    """Platform settings update request"""
    daily_briefing: Dict[str, Any] | None = None
    ai_config: Dict[str, Any] | None = None
    collection_config: Dict[str, Any] | None = None
    clustering_config: Dict[str, Any] | None = None
    collector_config: Dict[str, Any] | None = None
    smart_feed_config: Dict[str, Any] | None = None
    source_intervals: Dict[str, Any] | None = None
    australian_news_sources: Dict[str, Any] | None = None


@router.get("/settings/platform")
def get_platform_settings(db: Session = Depends(get_db)):
    """
    Get all platform settings

    Returns settings organized by key (daily_briefing, ai_config, etc.)
    """
    # Get all settings from database
    settings_rows = db.query(PlatformSettings).all()

    # Convert to dictionary
    settings = {}
    for row in settings_rows:
        settings[row.key] = row.value

    # Return empty objects if not configured
    if 'daily_briefing' not in settings:
        settings['daily_briefing'] = {
            'template': 'standard',
            'length': 'standard',
            'tone': 'professional',
            'focus_areas': {
                'competitive_intel': True,
                'opportunities': True,
                'risks': True,
                'trends': True,
                'product_updates': True,
                'market_changes': True
            },
            'schedule': {
                'enabled': False,
                'hour': 8,  # 8 AM local time
                'minute': 0
            }
        }

    if 'ai_config' not in settings:
        settings['ai_config'] = {
            'model': 'claude-sonnet-4-5-20250929',
            'model_cheap': 'claude-haiku-4-5-20250929',
            'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2'
        }

    if 'collection_config' not in settings:
        settings['collection_config'] = {
            'hourly_enabled': True,
            'daily_enabled': True,
            'daily_hour': 10,
            'retention_days': 90,
            'domain_blacklist': {
                'enabled': True,
                'domains': [
                    # Common low-quality/spammy domains often returned by aggregators
                    'yahoo.com',  # Yahoo articles (not yahoo finance)
                    'msn.com',
                    'aol.com',
                    'bing.com',
                    'pinterest.com',
                    'tumblr.com',
                ]
            }
        }

    if 'clustering_config' not in settings:
        settings['clustering_config'] = {
            'enabled': True,
            'similarity_threshold': 0.50,
            'time_window_hours': 96
        }

    if 'collector_config' not in settings:
        settings['collector_config'] = {
            'reddit': {
                'min_upvotes': 5,
                'min_comments': 3,
                'large_thread_threshold': 10,
                'max_comments_analyze': 15,
                'posts_per_subreddit': 10,
                'lookback_days': 7
            },
            'linkedin': {
                'scraping_strategy': 'conservative',  # conservative (1hr), moderate (30min), aggressive (15min)
                'delay_between_profiles_min': 60.0,  # 1 minute (conservative)
                'delay_between_profiles_max': 120.0,  # 2 minutes (conservative)
                'delay_between_customers_min': 300.0,  # 5 minutes (conservative)
                'delay_between_customers_max': 600.0   # 10 minutes (conservative)
            }
        }

    if 'smart_feed_config' not in settings:
        settings['smart_feed_config'] = {
            'enabled': True,
            'min_priority': 0.3,
            'high_priority_threshold': 0.7,  # Single-source items above this always show
            'recency_boost': {
                'enabled': True,
                'boost_amount': 0.1,  # Add to priority for items < 24h
                'time_threshold_hours': 24
            },
            'category_preferences': {
                'product_update': False,
                'financial': True,  # Always show
                'market_news': False,
                'competitor': True,  # Always show
                'challenge': True,  # Always show
                'opportunity': True,  # Always show
                'leadership': True,  # Always show
                'partnership': True,  # Always show
                'advertisement': False,
                'unrelated': False,
                'other': False
            },
            'source_preferences': {
                'linkedin': True,  # Always show LinkedIn posts
                'press_release': True,  # Always show press releases
                'reddit': False,
                'twitter': False,
                'rss': True,
                'google_news': False,
                'yahoo_finance_news': True,  # Always show financial news
                'yahoo_news': False,
                'australian_news': False,
                'news_api': False,
                'web_scraper': False
            },
            'diversity': {
                'enabled': True,
                'max_consecutive_same_source': 3  # Limit consecutive items from same source
            }
        }

    if 'source_intervals' not in settings:
        settings['source_intervals'] = {
            # Interval in hours - determines how often each source is collected
            'news_api': 1,              # Every 1 hour - fast-updating news
            'rss': 1,                   # Every 1 hour - RSS feeds
            'yahoo_finance_news': 1,    # Every 1 hour - financial news
            'australian_news': 6,       # Every 6 hours - regional news
            'google_news': 6,           # Every 6 hours - aggregated news
            'twitter': 3,               # Every 3 hours - social media
            'youtube': 12,              # Every 12 hours - video content
            'reddit': 24,               # Every 24 hours - community discussions
            'linkedin': 24,             # Every 24 hours - rate limited
            'linkedin_user': 24,        # Every 24 hours - heavily rate limited
            'pressrelease': 12,         # Every 12 hours - official releases
            'web_scrape': 12            # Every 12 hours - custom sources
        }

    if 'australian_news_sources' not in settings:
        settings['australian_news_sources'] = {
            'sources': [
                {
                    'name': 'ABC News',
                    'enabled': True,
                    'feeds': [
                        'https://www.abc.net.au/news/feed/51120/rss.xml'
                    ]
                },
                {
                    'name': 'The Guardian Australia',
                    'enabled': True,
                    'feeds': [
                        'https://www.theguardian.com/australia-news/rss'
                    ]
                },
                {
                    'name': 'The Australian',
                    'enabled': True,
                    'feeds': [
                        'https://www.theaustralian.com.au/feed/'
                    ]
                },
                {
                    'name': 'Sydney Morning Herald',
                    'enabled': True,
                    'feeds': [
                        'https://www.smh.com.au/rss/feed.xml'
                    ]
                },
                {
                    'name': 'The Age',
                    'enabled': True,
                    'feeds': [
                        'https://www.theage.com.au/rss/feed.xml'
                    ]
                },
                {
                    'name': 'News.com.au',
                    'enabled': True,
                    'feeds': [
                        'https://www.news.com.au/feed/'
                    ]
                }
            ]
        }

    return settings


@router.put("/settings/platform")
def update_platform_settings(
    settings_update: PlatformSettingsUpdate,
    db: Session = Depends(get_db)
):
    """
    Update platform settings

    Accepts partial updates - only provided sections will be updated
    """
    updated_keys = []

    # Update daily briefing settings
    if settings_update.daily_briefing:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'daily_briefing'
        ).first()

        if setting:
            setting.value = settings_update.daily_briefing
        else:
            setting = PlatformSettings(
                key='daily_briefing',
                value=settings_update.daily_briefing
            )
            db.add(setting)

        updated_keys.append('daily_briefing')

    # Update AI config settings
    if settings_update.ai_config:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'ai_config'
        ).first()

        if setting:
            setting.value = settings_update.ai_config
        else:
            setting = PlatformSettings(
                key='ai_config',
                value=settings_update.ai_config
            )
            db.add(setting)

        updated_keys.append('ai_config')

    # Update collection config settings
    if settings_update.collection_config:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'collection_config'
        ).first()

        if setting:
            setting.value = settings_update.collection_config
        else:
            setting = PlatformSettings(
                key='collection_config',
                value=settings_update.collection_config
            )
            db.add(setting)

        updated_keys.append('collection_config')

    # Update clustering config settings
    if settings_update.clustering_config:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'clustering_config'
        ).first()

        if setting:
            setting.value = settings_update.clustering_config
        else:
            setting = PlatformSettings(
                key='clustering_config',
                value=settings_update.clustering_config
            )
            db.add(setting)

        updated_keys.append('clustering_config')

    # Update collector config settings
    if settings_update.collector_config:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'collector_config'
        ).first()

        if setting:
            setting.value = settings_update.collector_config
        else:
            setting = PlatformSettings(
                key='collector_config',
                value=settings_update.collector_config
            )
            db.add(setting)

        updated_keys.append('collector_config')

    # Update smart feed config settings
    if settings_update.smart_feed_config:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'smart_feed_config'
        ).first()

        if setting:
            setting.value = settings_update.smart_feed_config
        else:
            setting = PlatformSettings(
                key='smart_feed_config',
                value=settings_update.smart_feed_config
            )
            db.add(setting)

        updated_keys.append('smart_feed_config')

    # Update source intervals settings
    if settings_update.source_intervals:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'source_intervals'
        ).first()

        if setting:
            setting.value = settings_update.source_intervals
        else:
            setting = PlatformSettings(
                key='source_intervals',
                value=settings_update.source_intervals
            )
            db.add(setting)

        updated_keys.append('source_intervals')

    # Update Australian news sources settings
    if settings_update.australian_news_sources:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'australian_news_sources'
        ).first()

        if setting:
            setting.value = settings_update.australian_news_sources
        else:
            setting = PlatformSettings(
                key='australian_news_sources',
                value=settings_update.australian_news_sources
            )
            db.add(setting)

        updated_keys.append('australian_news_sources')

    db.commit()

    return {
        'message': f'Updated settings: {", ".join(updated_keys)}',
        'updated_keys': updated_keys
    }


@router.get("/settings/daily-briefing-prompt")
def get_daily_briefing_prompt(db: Session = Depends(get_db)):
    """
    Get the current daily briefing prompt configuration

    This is used by the daily summary generation job
    """
    setting = db.query(PlatformSettings).filter(
        PlatformSettings.key == 'daily_briefing'
    ).first()

    if not setting:
        # Return default prompt
        return {
            'template': 'standard',
            'prompt': """Generate a concise daily briefing summarizing the key intelligence collected today. Focus on:
- Most important developments
- Emerging trends and patterns
- Notable competitor activities
- Strategic opportunities and risks

Keep the summary professional, actionable, and under 300 words.""",
            'length': 'standard',
            'tone': 'professional'
        }

    return setting.value


@router.get("/settings/ai-config-status")
def get_ai_config_status():
    """
    Get AI configuration status including whether UI override is enabled
    and current env var values
    """
    from app.config.settings import settings

    return {
        "model_override_enabled": settings.model_override_in_ui,
        "env_values": {
            "ai_model": settings.ai_model,
            "ai_model_cheap": settings.ai_model_cheap,
            "ai_provider": settings.ai_provider,
            "ai_provider_cheap": settings.ai_provider_cheap
        }
    }
