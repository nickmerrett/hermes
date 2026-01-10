#!/usr/bin/env python3
"""
Clean Australian News Source URLs

Removes trailing/leading whitespace from all feed URLs in the database.
This fixes 406 errors caused by malformed URLs.

Usage:
    cd backend
    python clean_australian_news_urls.py
"""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.database import PlatformSettings


def clean_urls():
    """Clean whitespace from all Australian news feed URLs"""

    db = SessionLocal()

    try:
        # Get current settings
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'australian_news_sources'
        ).first()

        if not setting:
            print("❌ No australian_news_sources found in database")
            return

        sources = setting.value.get('sources', [])
        print(f"Checking {len(sources)} sources for URL issues...")
        print("=" * 60)

        cleaned_count = 0
        total_feeds = 0

        # Clean URLs in each source
        for source in sources:
            source_name = source.get('name', 'Unknown')
            feeds = source.get('feeds', [])

            if not feeds:
                continue

            source_cleaned = False
            cleaned_feeds = []

            for feed_url in feeds:
                total_feeds += 1

                if not isinstance(feed_url, str):
                    cleaned_feeds.append(feed_url)
                    continue

                # Clean the URL
                clean_url = feed_url.strip()

                if feed_url != clean_url:
                    print(f"🧹 Cleaning: {source_name}")
                    print(f"   Before: '{feed_url}'")
                    print(f"   After:  '{clean_url}'")
                    cleaned_count += 1
                    source_cleaned = True

                cleaned_feeds.append(clean_url)

            # Update feeds list
            source['feeds'] = cleaned_feeds

        if cleaned_count > 0:
            # Update database
            setting.value['sources'] = sources
            db.commit()

            print("=" * 60)
            print(f"✅ Cleaned {cleaned_count} URLs out of {total_feeds} total feeds")
            print(f"✅ Updated database successfully")
        else:
            print("=" * 60)
            print(f"✅ All {total_feeds} feed URLs are already clean")
            print(f"✅ No changes needed")

    except Exception as e:
        print(f"❌ Error cleaning URLs: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    print("Cleaning Australian News Feed URLs...")
    print("=" * 60)
    clean_urls()
