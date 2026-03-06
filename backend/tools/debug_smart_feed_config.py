#!/usr/bin/env python3
"""Debug script to check smart feed configuration"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import get_db
from app.utils.smart_feed import get_smart_feed_settings
from app.models.database import PlatformSettings

def debug_smart_feed():
    """Check smart feed configuration"""
    db = next(get_db())

    try:
        # Check raw database value
        print("1. CHECKING RAW DATABASE VALUE")
        print("=" * 80)
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'smart_feed_config'
        ).first()

        if setting:
            print("✓ Found smart_feed_config in database")
            print(f"Updated: {setting.updated_at}")
            print()
            print("Category Preferences:")
            for cat, enabled in setting.value.get('category_preferences', {}).items():
                print(f"  {cat}: {enabled}")
            print()
            print("Source Preferences:")
            for src, enabled in setting.value.get('source_preferences', {}).items():
                print(f"  {src}: {enabled}")
        else:
            print("✗ No smart_feed_config found in database")
            print("Will use hardcoded defaults")

        print()
        print("2. CHECKING get_smart_feed_settings() OUTPUT")
        print("=" * 80)

        # Check what the utility function returns
        config = get_smart_feed_settings(db)

        print(f"Enabled: {config.get('enabled')}")
        print(f"Min Priority: {config.get('min_priority')}")
        print(f"High Priority Threshold: {config.get('high_priority_threshold')}")
        print()

        print("Category Preferences (TRUE only):")
        for cat, enabled in config.get('category_preferences', {}).items():
            if enabled:
                print(f"  ✓ {cat}")
        print()

        print("Source Preferences (TRUE only):")
        for src, enabled in config.get('source_preferences', {}).items():
            if enabled:
                print(f"  ✓ {src}")
        print()

        print("3. TESTING FILTER SCENARIOS")
        print("=" * 80)

        min_priority = config.get('min_priority', 0.3)
        high_priority = config.get('high_priority_threshold', 0.7)
        cat_prefs = config.get('category_preferences', {})
        src_prefs = config.get('source_preferences', {})

        print(f"Min priority threshold: {min_priority}")
        print(f"High priority threshold: {high_priority}")
        print()

        # Comprehensive test scenarios
        test_scenarios = [
            # Scenario 1: Preferred source, low priority
            {
                'name': 'Preferred source (LinkedIn) with LOW priority',
                'source_type': 'linkedin',
                'category': 'other',
                'priority': 0.1,
                'expected': 'INCLUDE',
                'reason': 'Preferred sources always show'
            },
            # Scenario 2: Preferred category, low priority
            {
                'name': 'Preferred category (financial) with LOW priority',
                'source_type': 'reddit',
                'category': 'financial',
                'priority': 0.1,
                'expected': 'INCLUDE',
                'reason': 'Preferred categories always show'
            },
            # Scenario 3: High priority, non-preferred source/category
            {
                'name': 'HIGH priority, non-preferred source/category',
                'source_type': 'reddit',
                'category': 'other',
                'priority': 0.8,
                'expected': 'INCLUDE',
                'reason': 'High priority items always show'
            },
            # Scenario 4: Medium priority, non-preferred source/category
            {
                'name': 'MEDIUM priority (0.5), non-preferred',
                'source_type': 'reddit',
                'category': 'other',
                'priority': 0.5,
                'expected': 'INCLUDE',
                'reason': 'Meets minimum priority threshold'
            },
            # Scenario 5: Low priority, non-preferred (should filter)
            {
                'name': 'LOW priority, non-preferred source/category',
                'source_type': 'reddit',
                'category': 'other',
                'priority': 0.2,
                'expected': 'FILTER OUT',
                'reason': 'Below minimum priority, not preferred'
            },
            # Scenario 6: Press release (preferred source)
            {
                'name': 'Press release with any priority',
                'source_type': 'press_release',
                'category': 'product_update',
                'priority': 0.1,
                'expected': 'INCLUDE',
                'reason': 'Press releases are preferred sources'
            },
            # Scenario 7: Competitor category (preferred)
            {
                'name': 'Competitor news from any source',
                'source_type': 'hackernews',
                'category': 'competitor',
                'priority': 0.15,
                'expected': 'INCLUDE',
                'reason': 'Competitor is a preferred category'
            },
            # Scenario 8: Challenge/risk (preferred category)
            {
                'name': 'Challenge/problem from non-preferred source',
                'source_type': 'twitter',
                'category': 'challenge',
                'priority': 0.2,
                'expected': 'INCLUDE',
                'reason': 'Challenge is a preferred category'
            },
            # Scenario 9: Advertisement (not preferred)
            {
                'name': 'Advertisement with medium priority',
                'source_type': 'google_news',
                'category': 'advertisement',
                'priority': 0.5,
                'expected': 'INCLUDE',
                'reason': 'Meets minimum priority threshold'
            },
            # Scenario 10: Unrelated content (not preferred)
            {
                'name': 'Unrelated content, low priority',
                'source_type': 'hackernews',
                'category': 'unrelated',
                'priority': 0.2,
                'expected': 'FILTER OUT',
                'reason': 'Below minimum priority, not preferred'
            },
            # Scenario 11: Yahoo Finance (preferred source)
            {
                'name': 'Yahoo Finance financial news',
                'source_type': 'yahoo_finance_news',
                'category': 'financial',
                'priority': 0.1,
                'expected': 'INCLUDE',
                'reason': 'Both preferred source AND category'
            },
            # Scenario 12: RSS feed (preferred source)
            {
                'name': 'RSS feed with low priority',
                'source_type': 'rss',
                'category': 'market_news',
                'priority': 0.15,
                'expected': 'INCLUDE',
                'reason': 'RSS is a preferred source'
            },
        ]

        passed = 0
        failed = 0

        for i, scenario in enumerate(test_scenarios, 1):
            src = scenario['source_type']
            cat = scenario['category']
            pri = scenario['priority']

            # Apply filtering logic
            reasons = []
            include = False

            # Check source preference
            if src_prefs.get(src, False):
                include = True
                reasons.append("preferred source")

            # Check category preference
            if cat_prefs.get(cat, False):
                include = True
                reasons.append("preferred category")

            # Check high priority
            if pri >= high_priority:
                include = True
                reasons.append(f"high priority ({pri} >= {high_priority})")

            # Check minimum priority
            if pri >= min_priority:
                if not include or not reasons:
                    reasons.append(f"priority {pri} >= {min_priority}")
                include = True

            # Determine result
            actual_result = "INCLUDE" if include else "FILTER OUT"
            expected_result = scenario['expected']
            test_passed = actual_result == expected_result

            if test_passed:
                passed += 1
                status_icon = "✓ PASS"
            else:
                failed += 1
                status_icon = "✗ FAIL"

            print(f"Test {i}: {scenario['name']}")
            print(f"  Source: {src} | Category: {cat} | Priority: {pri}")
            print(f"  Expected: {expected_result} ({scenario['reason']})")
            print(f"  Actual: {actual_result} ({', '.join(reasons) if reasons else 'no criteria met'})")
            print(f"  {status_icon}")
            print()

        print("=" * 80)
        print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_scenarios)} tests")
        print("=" * 80)
        print()

        if failed > 0:
            print("⚠️  Some tests failed! The filtering logic may not be working as expected.")
            print("   Check your smart_feed_config in the database.")
        else:
            print("✓ All tests passed! Smart feed filtering is working correctly.")
            print()
            print("Summary of what gets included:")
            print(f"  • All items from preferred sources: {[k for k,v in src_prefs.items() if v]}")
            print(f"  • All items from preferred categories: {[k for k,v in cat_prefs.items() if v]}")
            print(f"  • High priority items (>= {high_priority})")
            print(f"  • Medium priority items (>= {min_priority})")
            print()
            print("What gets filtered out:")
            print(f"  • Low priority items (< {min_priority}) that are NOT from preferred sources/categories")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    debug_smart_feed()
