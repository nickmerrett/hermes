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
            }
        }

    if 'ai_config' not in settings:
        settings['ai_config'] = {
            'model': 'claude-3-5-sonnet-20241022',
            'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2'
        }

    if 'collection_config' not in settings:
        settings['collection_config'] = {
            'hourly_enabled': True,
            'daily_enabled': True,
            'daily_hour': 10,
            'retention_days': 90
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
            }
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
