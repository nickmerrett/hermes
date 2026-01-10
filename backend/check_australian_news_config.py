#!/usr/bin/env python3
"""
Check Australian News Sources Configuration

Query the database to see what's actually configured for australian_news_sources
"""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.database import PlatformSettings
import json


def check_config():
    """Check current australian_news_sources configuration"""

    db = SessionLocal()

    try:
        # Query the setting
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'australian_news_sources'
        ).first()

        if not setting:
            print("❌ NO australian_news_sources found in database")
            print("   This is why the fallback is being used!")
            print("\n   Solutions:")
            print("   1. Run: python init_australian_news_settings.py")
            print("   2. Or access Platform Settings UI to initialize")
            print("   3. Or make a GET request to /api/settings/platform (initializes defaults)")
            return

        print("✅ Found australian_news_sources in database")
        print("\n" + "=" * 60)
        print("Configuration:")
        print("=" * 60)
        print(json.dumps(setting.value, indent=2))
        print("=" * 60)

        sources = setting.value.get('sources', [])
        print(f"\n📊 Total sources configured: {len(sources)}")

        enabled_count = sum(1 for s in sources if s.get('enabled', True))
        print(f"📊 Enabled sources: {enabled_count}")

        print("\n📋 Source Details:")
        for source in sources:
            name = source.get('name', 'Unknown')
            enabled = source.get('enabled', True)
            feeds = source.get('feeds', [])
            status = "✅ ENABLED" if enabled else "❌ DISABLED"
            print(f"   {status} {name} ({len(feeds)} feeds)")
            for feed in feeds:
                print(f"      - {feed}")

    except Exception as e:
        print(f"❌ Error checking configuration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    check_config()
