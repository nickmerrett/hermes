#!/usr/bin/env python3
"""
Simple diagnostic to check if smart feed filtering is working
Sets a very restrictive config and checks API results
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import get_db
from app.models.database import PlatformSettings
from datetime import datetime
import requests
import time


API_URL = "http://127.0.0.1:8000/api"


def main():
    db = next(get_db())

    try:
        print("="*80)
        print("SMART FEED SIMPLE DIAGNOSTIC")
        print("="*80)

        # Save original config
        original_setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'smart_feed_config'
        ).first()

        original_config = original_setting.value if original_setting else None
        print("\n✓ Saved original configuration")

        # Set VERY restrictive config
        restrictive_config = {
            'enabled': True,
            'min_priority': 0.8,  # Very high threshold
            'high_priority_threshold': 0.9,
            'recency_boost': {'enabled': False, 'boost_amount': 0.0, 'time_threshold_hours': 24},
            'category_preferences': {k: False for k in ['product_update', 'financial', 'market_news', 'competitor', 'challenge', 'opportunity', 'leadership', 'partnership', 'advertisement', 'unrelated', 'other']},
            'source_preferences': {k: False for k in ['linkedin', 'press_release', 'reddit', 'hackernews', 'twitter', 'rss', 'google_news', 'yahoo_finance_news', 'yahoo_news', 'australian_news', 'github', 'news_api', 'web_scraper']},
            'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
        }

        print("\n" + "="*80)
        print("SETTING VERY RESTRICTIVE CONFIG")
        print("="*80)
        print("min_priority: 0.8 (VERY HIGH)")
        print("high_priority_threshold: 0.9")
        print("ALL category preferences: DISABLED")
        print("ALL source preferences: DISABLED")
        print("\nWith this config, ONLY items with priority >= 0.8 should appear!")

        # Save to database
        if original_setting:
            original_setting.value = restrictive_config
            original_setting.updated_at = datetime.utcnow()
        else:
            original_setting = PlatformSettings(
                key='smart_feed_config',
                value=restrictive_config
            )
            db.add(original_setting)

        db.commit()
        print("\n✓ Saved restrictive config to database")

        # Wait a moment
        print("\nWaiting 2 seconds for server to pick up changes...")
        time.sleep(2)

        # Call API
        print("\nCalling API: GET /feed?clustered=true&limit=50")
        response = requests.get(
            f"{API_URL}/feed",
            params={'clustered': 'true', 'limit': 50},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        items = data.get('items', [])
        print(f"\n✓ API returned {len(items)} items")

        # Analyze results
        print("\n" + "="*80)
        print("ANALYSIS OF RETURNED ITEMS")
        print("="*80)

        priority_counts = {
            '0.9+': 0,
            '0.8-0.9': 0,
            '0.7-0.8': 0,
            '0.6-0.7': 0,
            '0.5-0.6': 0,
            '0.4-0.5': 0,
            '0.3-0.4': 0,
            '<0.3': 0,
        }

        violations = []

        for item in items:
            if item.get('processed'):
                priority = item['processed'].get('priority_score', 0.0)

                # Categorize
                if priority >= 0.9:
                    priority_counts['0.9+'] += 1
                elif priority >= 0.8:
                    priority_counts['0.8-0.9'] += 1
                elif priority >= 0.7:
                    priority_counts['0.7-0.8'] += 1
                    violations.append(item)
                elif priority >= 0.6:
                    priority_counts['0.6-0.7'] += 1
                    violations.append(item)
                elif priority >= 0.5:
                    priority_counts['0.5-0.6'] += 1
                    violations.append(item)
                elif priority >= 0.4:
                    priority_counts['0.4-0.5'] += 1
                    violations.append(item)
                elif priority >= 0.3:
                    priority_counts['0.3-0.4'] += 1
                    violations.append(item)
                else:
                    priority_counts['<0.3'] += 1
                    violations.append(item)

        print("\nPriority Distribution:")
        for range_name, count in priority_counts.items():
            if count > 0:
                status = "✓" if range_name in ['0.9+', '0.8-0.9'] else "✗ VIOLATION"
                print(f"  {status} {range_name:10} {count:3} items")

        # Check for violations
        print("\n" + "="*80)
        if violations:
            print("❌ FILTERING IS BROKEN!")
            print("="*80)
            print(f"\n{len(violations)} items with priority < 0.8 were returned!")
            print("\nThese items should have been filtered out:")
            print("\nFirst 10 violations:")
            for i, item in enumerate(violations[:10], 1):
                priority = item['processed'].get('priority_score', 0.0)
                source = item.get('source_type', 'unknown')
                category = item['processed'].get('category', 'unknown')
                title = item.get('title', 'No title')[:60]
                print(f"\n  {i}. Priority: {priority:.2f} | Source: {source} | Category: {category}")
                print(f"     Title: {title}...")

            print("\n" + "="*80)
            print("DIAGNOSIS: Smart feed filtering is NOT working correctly")
            print("="*80)
            print("\nPossible causes:")
            print("  1. Server hasn't picked up the new configuration")
            print("  2. Bug in should_include_item() function")
            print("  3. Filtering logic is being bypassed")
            print("\nRecommendations:")
            print("  1. Check server logs for 'Smart Feed min_priority: 0.8'")
            print("  2. Restart the backend server")
            print("  3. Check app/utils/smart_feed.py for bugs")

        else:
            print("✅ FILTERING IS WORKING CORRECTLY!")
            print("="*80)
            print(f"\nAll {len(items)} items have priority >= 0.8")
            print("\nThe smart feed filtering is working as expected!")

        # Restore original config
        print("\n\nRestoring original configuration...")
        if original_config:
            original_setting.value = original_config
            original_setting.updated_at = datetime.utcnow()
            db.commit()
            print("✓ Restored original configuration")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ API Error: {e}")
        print("\nMake sure the backend server is running at http://127.0.0.1:8000")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    main()
