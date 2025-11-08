#!/usr/bin/env python3
"""
Add platform_settings table for storing platform-wide configuration

Run this script to create the platform_settings table
"""

from app.core.database import SessionLocal, engine
from app.models.database import Base, PlatformSettings
from sqlalchemy import inspect

def migrate():
    """Create platform_settings table if it doesn't exist"""

    print("Checking if platform_settings table exists...")

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if 'platform_settings' in existing_tables:
        print("✅ platform_settings table already exists")
        return

    print("Creating platform_settings table...")

    # Create only the platform_settings table
    PlatformSettings.__table__.create(engine, checkfirst=True)

    print("✅ platform_settings table created successfully!")

    # Initialize with default settings
    db = SessionLocal()
    try:
        print("Adding default settings...")

        # Check if settings already exist
        existing = db.query(PlatformSettings).first()
        if not existing:
            # Add default daily briefing settings
            daily_briefing = PlatformSettings(
                key='daily_briefing',
                value={
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
                    'prompt': """Generate a concise daily briefing summarizing the key intelligence collected today. Focus on:
- Most important developments
- Emerging trends and patterns
- Notable competitor activities
- Strategic opportunities and risks

Keep the summary professional, actionable, and under 300 words."""
                }
            )
            db.add(daily_briefing)

            # Add default AI config
            ai_config = PlatformSettings(
                key='ai_config',
                value={
                    'model': 'claude-3-5-sonnet-20241022',
                    'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2'
                }
            )
            db.add(ai_config)

            # Add default collection config
            collection_config = PlatformSettings(
                key='collection_config',
                value={
                    'hourly_enabled': True,
                    'daily_enabled': True,
                    'daily_hour': 10,
                    'retention_days': 90
                }
            )
            db.add(collection_config)

            # Add default clustering config
            clustering_config = PlatformSettings(
                key='clustering_config',
                value={
                    'enabled': True,
                    'similarity_threshold': 0.50,
                    'time_window_hours': 96
                }
            )
            db.add(clustering_config)

            # Add default collector config
            collector_config = PlatformSettings(
                key='collector_config',
                value={
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
            )
            db.add(collector_config)

            db.commit()
            print("✅ Default settings added")
        else:
            print("✅ Settings already exist, skipping initialization")

    except Exception as e:
        print(f"❌ Error adding default settings: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    migrate()
