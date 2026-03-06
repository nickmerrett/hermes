#!/usr/bin/env python3
"""
Test smart feed filtering through the actual API
Makes real API calls to verify filtering behavior end-to-end
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


def save_smart_feed_config(db, config):
    """Save smart feed configuration to database"""
    setting = db.query(PlatformSettings).filter(
        PlatformSettings.key == 'smart_feed_config'
    ).first()

    if setting:
        setting.value = config
        setting.updated_at = datetime.utcnow()
    else:
        setting = PlatformSettings(
            key='smart_feed_config',
            value=config
        )
        db.add(setting)

    db.commit()
    print("  ✓ Saved configuration to database")


def get_smart_feed_config(db):
    """Get current smart feed configuration"""
    setting = db.query(PlatformSettings).filter(
        PlatformSettings.key == 'smart_feed_config'
    ).first()

    if setting:
        return setting.value
    return None


def get_feed_from_api(clustered=True, limit=200):
    """Call the feed API and return results"""
    try:
        params = {
            'clustered': str(clustered).lower(),
            'limit': limit
        }
        response = requests.get(f"{API_URL}/feed", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ✗ API request failed: {e}")
        return None


def analyze_feed_results(feed_data, db):
    """Analyze feed results and return statistics"""
    if not feed_data:
        return None

    items = feed_data.get('items', [])

    # Get processed intelligence for analysis


    stats = {
        'total_count': len(items),
        'by_source': {},
        'by_category': {},
        'by_priority_range': {
            'very_high_0.8+': 0,
            'high_0.6-0.8': 0,
            'medium_0.4-0.6': 0,
            'low_0.3-0.4': 0,
            'very_low_<0.3': 0
        }
    }

    for item in items:
        # Count by source
        source = item.get('source_type', 'unknown')
        stats['by_source'][source] = stats['by_source'].get(source, 0) + 1

        # Count by category (from processed data if available)
        if item.get('processed'):
            category = item['processed'].get('category', 'unknown')
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

            # Count by priority
            priority = item['processed'].get('priority_score', 0.0)
            if priority >= 0.8:
                stats['by_priority_range']['very_high_0.8+'] += 1
            elif priority >= 0.6:
                stats['by_priority_range']['high_0.6-0.8'] += 1
            elif priority >= 0.4:
                stats['by_priority_range']['medium_0.4-0.6'] += 1
            elif priority >= 0.3:
                stats['by_priority_range']['low_0.3-0.4'] += 1
            else:
                stats['by_priority_range']['very_low_<0.3'] += 1

    return stats


def print_stats(stats, title="Feed Statistics"):
    """Pretty print feed statistics"""
    print(f"\n  {title}:")
    print(f"    Total Items: {stats['total_count']}")

    if stats['by_source']:
        print("\n    By Source:")
        for source, count in sorted(stats['by_source'].items(), key=lambda x: -x[1])[:10]:
            print(f"      {source:25} {count:3} items")

    if stats['by_category']:
        print("\n    By Category:")
        for category, count in sorted(stats['by_category'].items(), key=lambda x: -x[1]):
            print(f"      {category:25} {count:3} items")

    print("\n    By Priority:")
    for range_name, count in stats['by_priority_range'].items():
        if count > 0:
            print(f"      {range_name:25} {count:3} items")


def run_api_scenario_test(scenario_name, config, db, validation_func):
    """Run a test scenario using the actual API"""
    print(f"\n{'='*80}")
    print(f"API TEST: {scenario_name}")
    print(f"{'='*80}")

    # Show configuration
    print("\nConfiguration:")
    print(f"  Min Priority: {config.get('min_priority', 0.3)}")
    print(f"  High Priority Threshold: {config.get('high_priority_threshold', 0.7)}")

    cat_prefs = config.get('category_preferences', {})
    enabled_cats = [k for k, v in cat_prefs.items() if v]
    print(f"  Preferred Categories: {enabled_cats if enabled_cats else 'NONE'}")

    src_prefs = config.get('source_preferences', {})
    enabled_srcs = [k for k, v in src_prefs.items() if v]
    print(f"  Preferred Sources: {enabled_srcs if enabled_srcs else 'NONE'}")

    # Save configuration
    save_smart_feed_config(db, config)

    # Give the server a moment to pick up changes
    time.sleep(0.5)

    # Get baseline (Full Feed)
    print("\n  Fetching Full Feed (clustered=False)...")
    full_feed = get_feed_from_api(clustered=False, limit=200)
    if not full_feed:
        print("  ✗ Failed to fetch full feed")
        return False

    full_stats = analyze_feed_results(full_feed, db)
    print_stats(full_stats, "Full Feed (No Filtering)")

    # Get Smart Feed
    print("\n  Fetching Smart Feed (clustered=True)...")
    smart_feed = get_feed_from_api(clustered=True, limit=200)
    if not smart_feed:
        print("  ✗ Failed to fetch smart feed")
        return False

    smart_stats = analyze_feed_results(smart_feed, db)
    print_stats(smart_stats, "Smart Feed (With Filtering)")

    # Calculate filtering
    full_count = full_stats['total_count']
    smart_count = smart_stats['total_count']
    filtered_count = full_count - smart_count
    filter_percentage = (filtered_count / full_count * 100) if full_count > 0 else 0

    print("\n  Filtering Results:")
    print(f"    Full Feed Items:    {full_count}")
    print(f"    Smart Feed Items:   {smart_count}")
    print(f"    Filtered Out:       {filtered_count} ({filter_percentage:.1f}%)")

    # Run validation
    print("\n  Validation:")
    passed = validation_func(config, full_stats, smart_stats, db)

    if passed:
        print("\n  ✓ TEST PASSED")
    else:
        print("\n  ✗ TEST FAILED")

    return passed


def validate_very_permissive(config, full_stats, smart_stats, db):
    """Validation: Should include ALL items (or nearly all due to clustering)"""
    # Smart feed should include most items (allowing for some clustering)
    full_count = full_stats['total_count']
    smart_count = smart_stats['total_count']

    # With min_priority=0.0, should include at least 95% of items
    if smart_count >= full_count * 0.95:
        print(f"    ✓ Smart feed includes {smart_count}/{full_count} items (95%+ threshold)")
        return True
    else:
        print(f"    ✗ Smart feed only includes {smart_count}/{full_count} items (expected 95%+)")
        return False


def validate_very_restrictive(config, full_stats, smart_stats, db):
    """Validation: Should filter heavily (only high priority >= 0.8)"""
    # Count high priority items in full feed
    high_priority_full = full_stats['by_priority_range'].get('very_high_0.8+', 0)
    smart_count = smart_stats['total_count']

    # Smart feed should have roughly the number of high priority items
    # Allow some variance due to recency boost
    if smart_count <= high_priority_full * 1.2:
        print(f"    ✓ Smart feed filtered heavily: {smart_count} items (expected ~{high_priority_full} high priority)")
        return True
    else:
        print(f"    ✗ Smart feed has {smart_count} items (expected ~{high_priority_full} high priority items)")
        return False


def validate_source_focused(config, full_stats, smart_stats, db):
    """Validation: Should include preferred sources + high priority items"""
    preferred_sources = [k for k, v in config['source_preferences'].items() if v]

    # Count items from preferred sources in smart feed
    preferred_count = sum(smart_stats['by_source'].get(src, 0) for src in preferred_sources)

    # Count high/medium priority items
    high_priority = smart_stats['by_priority_range'].get('very_high_0.8+', 0)
    medium_priority = smart_stats['by_priority_range'].get('high_0.6-0.8', 0)
    med_high_priority = smart_stats['by_priority_range'].get('medium_0.4-0.6', 0)

    total_smart = smart_stats['total_count']

    print(f"    Items from preferred sources: {preferred_count}")
    print(f"    High priority items: {high_priority}")
    print(f"    Medium-high priority items: {medium_priority + med_high_priority}")
    print(f"    Total in smart feed: {total_smart}")

    # Should have preferred sources OR meet priority threshold
    # This is additive, so we expect both
    if preferred_count > 0:
        print("    ✓ Preferred sources are present in smart feed")
        return True
    else:
        print("    ✗ No items from preferred sources found")
        return False


def validate_category_focused(config, full_stats, smart_stats, db):
    """Validation: Should include preferred categories + high priority items"""
    preferred_categories = [k for k, v in config['category_preferences'].items() if v]

    # Count items from preferred categories in smart feed
    preferred_count = sum(smart_stats['by_category'].get(cat, 0) for cat in preferred_categories)

    total_smart = smart_stats['total_count']

    print(f"    Items from preferred categories: {preferred_count}")
    print(f"    Total in smart feed: {total_smart}")

    # Should have items from preferred categories
    if preferred_count > 0:
        print("    ✓ Preferred categories are present in smart feed")
        return True
    else:
        print("    ✗ No items from preferred categories found")
        return False


def validate_priority_only(config, full_stats, smart_stats, db):
    """Validation: Should only include items meeting priority threshold"""
    min_priority = config['min_priority']

    # Count items that should meet threshold
    expected_count = sum([
        full_stats['by_priority_range'].get('very_high_0.8+', 0),
        full_stats['by_priority_range'].get('high_0.6-0.8', 0),
        full_stats['by_priority_range'].get('medium_0.4-0.6', 0),
    ])

    smart_count = smart_stats['total_count']

    # Allow 20% variance due to recency boost and clustering
    lower_bound = expected_count * 0.8
    upper_bound = expected_count * 1.2

    print(f"    Expected items with priority >= {min_priority}: ~{expected_count}")
    print(f"    Smart feed items: {smart_count}")

    if lower_bound <= smart_count <= upper_bound:
        print("    ✓ Smart feed count is within expected range")
        return True
    else:
        print(f"    ✗ Smart feed count outside expected range ({lower_bound:.0f}-{upper_bound:.0f})")
        return False


def main():
    """Run comprehensive API-based smart feed tests"""
    db = next(get_db())

    try:
        print("="*80)
        print("SMART FEED API INTEGRATION TESTS")
        print("="*80)
        print("\nThis will test smart feed filtering through the actual API")
        print("Testing against real data in your database")

        # Check if API is accessible
        try:
            response = requests.get(f"{API_URL}/feed", params={'limit': 1}, timeout=5)
            response.raise_for_status()
            print(f"\n✓ API is accessible at {API_URL}")
        except requests.exceptions.RequestException as e:
            print(f"\n✗ Cannot reach API at {API_URL}")
            print(f"  Error: {e}")
            print("\n  Make sure the backend server is running!")
            return

        # Save original configuration
        original_config = get_smart_feed_config(db)
        print("✓ Saved original configuration")

        # Define test scenarios
        scenarios = []

        # SCENARIO 1: Very Permissive
        scenarios.append({
            'name': 'Very Permissive - Show Everything',
            'config': {
                'enabled': True,
                'min_priority': 0.0,
                'high_priority_threshold': 1.0,
                'recency_boost': {'enabled': True, 'boost_amount': 0.1, 'time_threshold_hours': 24},
                'category_preferences': {k: True for k in ['product_update', 'financial', 'market_news', 'competitor', 'challenge', 'opportunity', 'leadership', 'partnership', 'advertisement', 'unrelated', 'other']},
                'source_preferences': {k: True for k in ['linkedin', 'press_release', 'reddit', 'hackernews', 'twitter', 'rss', 'google_news', 'yahoo_finance_news', 'yahoo_news', 'australian_news', 'github', 'news_api', 'web_scraper']},
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'validation': validate_very_permissive
        })

        # SCENARIO 2: Very Restrictive
        scenarios.append({
            'name': 'Very Restrictive - High Priority Only (0.8+)',
            'config': {
                'enabled': True,
                'min_priority': 0.8,
                'high_priority_threshold': 0.9,
                'recency_boost': {'enabled': False, 'boost_amount': 0.0, 'time_threshold_hours': 24},
                'category_preferences': {k: False for k in ['product_update', 'financial', 'market_news', 'competitor', 'challenge', 'opportunity', 'leadership', 'partnership', 'advertisement', 'unrelated', 'other']},
                'source_preferences': {k: False for k in ['linkedin', 'press_release', 'reddit', 'hackernews', 'twitter', 'rss', 'google_news', 'yahoo_finance_news', 'yahoo_news', 'australian_news', 'github', 'news_api', 'web_scraper']},
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'validation': validate_very_restrictive
        })

        # SCENARIO 3: Source-Focused
        scenarios.append({
            'name': 'Source-Focused - LinkedIn & Press Releases + Medium Priority',
            'config': {
                'enabled': True,
                'min_priority': 0.3,
                'high_priority_threshold': 0.7,
                'recency_boost': {'enabled': True, 'boost_amount': 0.1, 'time_threshold_hours': 24},
                'category_preferences': {k: False for k in ['product_update', 'financial', 'market_news', 'competitor', 'challenge', 'opportunity', 'leadership', 'partnership', 'advertisement', 'unrelated', 'other']},
                'source_preferences': {
                    'linkedin': True,
                    'press_release': True,
                    'reddit': False,
                    'hackernews': False,
                    'twitter': False,
                    'rss': False,
                    'google_news': False,
                    'yahoo_finance_news': False,
                    'yahoo_news': False,
                    'australian_news': False,
                    'github': False,
                    'news_api': False,
                    'web_scraper': False
                },
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'validation': validate_source_focused
        })

        # SCENARIO 4: Category-Focused
        scenarios.append({
            'name': 'Category-Focused - Business Intel Categories',
            'config': {
                'enabled': True,
                'min_priority': 0.3,
                'high_priority_threshold': 0.7,
                'recency_boost': {'enabled': True, 'boost_amount': 0.1, 'time_threshold_hours': 24},
                'category_preferences': {
                    'product_update': False,
                    'financial': True,
                    'market_news': False,
                    'competitor': True,
                    'challenge': True,
                    'opportunity': True,
                    'leadership': False,
                    'partnership': False,
                    'advertisement': False,
                    'unrelated': False,
                    'other': False
                },
                'source_preferences': {k: False for k in ['linkedin', 'press_release', 'reddit', 'hackernews', 'twitter', 'rss', 'google_news', 'yahoo_finance_news', 'yahoo_news', 'australian_news', 'github', 'news_api', 'web_scraper']},
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'validation': validate_category_focused
        })

        # SCENARIO 5: Priority-Only
        scenarios.append({
            'name': 'Priority-Only - No Preferences, Just Threshold (0.4+)',
            'config': {
                'enabled': True,
                'min_priority': 0.4,
                'high_priority_threshold': 0.7,
                'recency_boost': {'enabled': False, 'boost_amount': 0.0, 'time_threshold_hours': 24},
                'category_preferences': {k: False for k in ['product_update', 'financial', 'market_news', 'competitor', 'challenge', 'opportunity', 'leadership', 'partnership', 'advertisement', 'unrelated', 'other']},
                'source_preferences': {k: False for k in ['linkedin', 'press_release', 'reddit', 'hackernews', 'twitter', 'rss', 'google_news', 'yahoo_finance_news', 'yahoo_news', 'australian_news', 'github', 'news_api', 'web_scraper']},
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'validation': validate_priority_only
        })

        # Run scenarios
        results = []
        for scenario in scenarios:
            passed = run_api_scenario_test(
                scenario['name'],
                scenario['config'],
                db,
                scenario['validation']
            )
            results.append({'name': scenario['name'], 'passed': passed})

            # Brief pause between tests
            time.sleep(1)

        # Summary
        print(f"\n\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")

        passed_count = sum(1 for r in results if r['passed'])
        failed_count = len(results) - passed_count

        for result in results:
            status = "✓ PASS" if result['passed'] else "✗ FAIL"
            print(f"{status}: {result['name']}")

        print(f"\n{passed_count}/{len(results)} scenarios passed")

        if failed_count == 0:
            print("\n✓ All API tests passed! Smart feed filtering is working correctly.")
        else:
            print(f"\n⚠️  {failed_count} scenario(s) failed.")

        # Restore original configuration
        if original_config:
            save_smart_feed_config(db, original_config)
            print("\n✓ Restored original configuration")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    main()
