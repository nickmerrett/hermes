#!/usr/bin/env python3
"""
Initialize Australian News Sources in Platform Settings

Run this script to populate the database with proper Australian news source configuration.
This will enable collection from multiple business/tech-focused RSS feeds.

Usage:
    cd backend
    python init_australian_news_settings.py
"""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.database import PlatformSettings


def init_australian_news_sources():
    """Initialize Australian news sources in platform settings"""

    db = SessionLocal()

    try:
        # Check if already exists
        existing = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'australian_news_sources'
        ).first()

        if existing:
            print("⚠️  Australian news sources already configured in database")
            print(f"   Found {len(existing.value.get('sources', []))} sources")
            print("\n   To update, delete the existing setting first or update via API")
            return

        # Create new setting with business/tech focused feeds
        sources_config = {
            'sources': [
                {
                    'name': 'ABC News Business',
                    'enabled': True,
                    'feeds': [
                        'https://www.abc.net.au/news/feed/45924/rss.xml',  # Business
                        'https://www.abc.net.au/news/feed/5789070/rss.xml'  # Technology
                    ]
                },
                {
                    'name': 'The Guardian Australia Business',
                    'enabled': True,
                    'feeds': [
                        'https://www.theguardian.com/australia-news/business/rss',
                        'https://www.theguardian.com/technology/rss'
                    ]
                },
                {
                    'name': 'Sydney Morning Herald Business',
                    'enabled': True,
                    'feeds': [
                        'https://www.smh.com.au/rss/business.xml',
                        'https://www.smh.com.au/rss/technology.xml'
                    ]
                },
                {
                    'name': 'The Age Business',
                    'enabled': True,
                    'feeds': [
                        'https://www.theage.com.au/rss/business.xml',
                        'https://www.theage.com.au/rss/technology.xml'
                    ]
                },
                {
                    'name': 'ITNews Australia',
                    'enabled': True,
                    'feeds': [
                        'https://www.itnews.com.au/rss.xml'
                    ]
                },
                {
                    'name': 'Australian Financial Review',
                    'enabled': True,
                    'feeds': [
                        'https://www.afr.com/rss'
                    ]
                }
            ]
        }

        # Create setting
        setting = PlatformSettings(
            key='australian_news_sources',
            value=sources_config
        )

        db.add(setting)
        db.commit()

        print("✅ Successfully initialized Australian news sources")
        print(f"   Configured {len(sources_config['sources'])} sources:")

        for source in sources_config['sources']:
            print(f"   - {source['name']} ({len(source['feeds'])} feeds)")

        print("\n   Next collection will use these sources instead of fallback")

    except Exception as e:
        print(f"❌ Error initializing settings: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    print("Initializing Australian News Sources in Database...")
    print("=" * 60)
    init_australian_news_sources()
    print("=" * 60)
