#!/usr/bin/env python3
"""Migrate smart feed settings from old schema to new schema"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import get_db
from app.models.database import PlatformSettings

# Mapping from old category names to new ones
CATEGORY_MIGRATION = {
    'competitive_intel': 'competitor',
    'executive_changes': 'leadership',
    'product_updates': 'product_update',
    'market_trends': 'market_news',
    'risk_alert': 'challenge',
    'opportunity': 'opportunity'
}

# Mapping from old source names to new ones
SOURCE_MIGRATION = {
    'stock': 'yahoo_finance_news'
}

def migrate_smart_feed_settings():
    """Migrate existing settings to new schema"""
    db = next(get_db())

    try:
        # Find existing smart_feed_config
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'smart_feed_config'
        ).first()

        if not setting:
            print("No smart_feed_config found in database")
            return

        config = setting.value
        print("Found existing smart_feed_config")
        print(f"Current categories: {list(config.get('category_preferences', {}).keys())}")
        print(f"Current sources: {list(config.get('source_preferences', {}).keys())}")
        print()

        # Migrate categories
        old_categories = config.get('category_preferences', {})
        new_categories = {
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
        }

        # Map old values to new schema
        for old_key, new_key in CATEGORY_MIGRATION.items():
            if old_key in old_categories:
                new_categories[new_key] = old_categories[old_key]
                print(f"Migrated category: {old_key} → {new_key} = {old_categories[old_key]}")

        config['category_preferences'] = new_categories

        # Migrate sources
        old_sources = config.get('source_preferences', {})
        new_sources = {
            'linkedin': old_sources.get('linkedin', True),
            'press_release': old_sources.get('press_release', True),
            'reddit': old_sources.get('reddit', False),
            'hackernews': old_sources.get('hackernews', False),
            'twitter': old_sources.get('twitter', False),
            'rss': old_sources.get('rss', True),
            'google_news': False,
            'yahoo_finance_news': old_sources.get('stock', True),  # stock → yahoo_finance_news
            'yahoo_news': False,
            'australian_news': False,
            'github': False,
            'news_api': False,
            'web_scraper': False
        }

        if 'stock' in old_sources:
            print(f"Migrated source: stock → yahoo_finance_news = {old_sources['stock']}")

        config['source_preferences'] = new_sources

        # Save updated config
        setting.value = config
        db.commit()

        print()
        print("✓ Smart feed settings migrated successfully!")
        print(f"New categories: {list(new_categories.keys())}")
        print(f"New sources: {list(new_sources.keys())}")
        print()
        print("Please refresh your browser to see the updated settings.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    migrate_smart_feed_settings()
