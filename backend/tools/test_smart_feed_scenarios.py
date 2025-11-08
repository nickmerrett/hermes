#!/usr/bin/env python3
"""
Comprehensive test suite for smart feed filtering
Tests multiple configuration scenarios and validates filtering behavior
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import get_db
from app.models.database import PlatformSettings
from datetime import datetime


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


def get_smart_feed_config(db):
    """Get current smart feed configuration"""
    setting = db.query(PlatformSettings).filter(
        PlatformSettings.key == 'smart_feed_config'
    ).first()

    if setting:
        return setting.value
    return None


def simulate_filtering(config, test_items):
    """Simulate smart feed filtering logic"""
    min_priority = config.get('min_priority', 0.3)
    high_priority = config.get('high_priority_threshold', 0.7)
    cat_prefs = config.get('category_preferences', {})
    src_prefs = config.get('source_preferences', {})

    results = []
    for item in test_items:
        src = item['source_type']
        cat = item['category']
        pri = item['priority']

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
            reasons.append(f"high priority")

        # Check minimum priority
        if pri >= min_priority:
            include = True
            if "high priority" not in reasons and not reasons:
                reasons.append("meets min priority")

        results.append({
            'item': item,
            'included': include,
            'reasons': reasons
        })

    return results


def run_scenario_test(scenario_name, config, test_items, expected_included_count):
    """Run a test scenario with specific configuration"""
    print(f"\n{'='*80}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'='*80}")

    # Show configuration
    print(f"\nConfiguration:")
    print(f"  Min Priority: {config.get('min_priority', 0.3)}")
    print(f"  High Priority Threshold: {config.get('high_priority_threshold', 0.7)}")

    cat_prefs = config.get('category_preferences', {})
    enabled_cats = [k for k, v in cat_prefs.items() if v]
    print(f"  Preferred Categories: {enabled_cats if enabled_cats else 'NONE'}")

    src_prefs = config.get('source_preferences', {})
    enabled_srcs = [k for k, v in src_prefs.items() if v]
    print(f"  Preferred Sources: {enabled_srcs if enabled_srcs else 'NONE'}")

    # Run filtering
    results = simulate_filtering(config, test_items)

    # Count results
    included = [r for r in results if r['included']]
    filtered = [r for r in results if not r['included']]

    print(f"\nResults:")
    print(f"  Included: {len(included)}/{len(test_items)}")
    print(f"  Filtered Out: {len(filtered)}/{len(test_items)}")

    # Show included items
    if included:
        print(f"\n  Included Items:")
        for r in included:
            item = r['item']
            reasons = ', '.join(r['reasons'])
            print(f"    • {item['source_type']:20} | {item['category']:15} | pri={item['priority']:.1f} | {reasons}")

    # Show filtered items
    if filtered:
        print(f"\n  Filtered Out:")
        for r in filtered:
            item = r['item']
            print(f"    • {item['source_type']:20} | {item['category']:15} | pri={item['priority']:.1f}")

    # Validate expectation
    test_passed = len(included) == expected_included_count
    if test_passed:
        print(f"\n✓ TEST PASSED: Expected {expected_included_count} included, got {len(included)}")
        return True
    else:
        print(f"\n✗ TEST FAILED: Expected {expected_included_count} included, got {len(included)}")
        return False


def main():
    """Run comprehensive smart feed scenario tests"""
    db = next(get_db())

    try:
        print("="*80)
        print("SMART FEED CONFIGURATION SCENARIO TESTS")
        print("="*80)
        print("\nThis will test various smart feed configurations and validate filtering")
        print("Original settings will be restored at the end")

        # Save original configuration
        original_config = get_smart_feed_config(db)
        print(f"\n✓ Saved original configuration")

        # Define test items covering various scenarios
        test_items = [
            # High priority items (should always show unless filtering is very strict)
            {'source_type': 'reddit', 'category': 'other', 'priority': 0.9},
            {'source_type': 'hackernews', 'category': 'advertisement', 'priority': 0.8},

            # Medium priority items
            {'source_type': 'twitter', 'category': 'market_news', 'priority': 0.5},
            {'source_type': 'google_news', 'category': 'product_update', 'priority': 0.4},

            # Low priority items
            {'source_type': 'reddit', 'category': 'unrelated', 'priority': 0.2},
            {'source_type': 'hackernews', 'category': 'other', 'priority': 0.15},

            # Preferred sources (linkedin, press_release)
            {'source_type': 'linkedin', 'category': 'other', 'priority': 0.1},
            {'source_type': 'press_release', 'category': 'advertisement', 'priority': 0.05},

            # Preferred categories (financial, competitor, challenge, etc.)
            {'source_type': 'reddit', 'category': 'financial', 'priority': 0.1},
            {'source_type': 'twitter', 'category': 'competitor', 'priority': 0.15},
            {'source_type': 'hackernews', 'category': 'challenge', 'priority': 0.2},
            {'source_type': 'google_news', 'category': 'opportunity', 'priority': 0.1},

            # Mixed scenarios
            {'source_type': 'yahoo_finance_news', 'category': 'financial', 'priority': 0.3},
            {'source_type': 'rss', 'category': 'leadership', 'priority': 0.25},
        ]

        print(f"\nUsing {len(test_items)} test items for validation")

        # Define test scenarios
        scenarios = []

        # SCENARIO 1: Very Permissive (everything enabled)
        scenarios.append({
            'name': 'Very Permissive - Everything Enabled',
            'config': {
                'enabled': True,
                'min_priority': 0.0,
                'high_priority_threshold': 1.0,
                'recency_boost': {'enabled': True, 'boost_amount': 0.1, 'time_threshold_hours': 24},
                'category_preferences': {k: True for k in ['product_update', 'financial', 'market_news', 'competitor', 'challenge', 'opportunity', 'leadership', 'partnership', 'advertisement', 'unrelated', 'other']},
                'source_preferences': {k: True for k in ['linkedin', 'press_release', 'reddit', 'hackernews', 'twitter', 'rss', 'google_news', 'yahoo_finance_news']},
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'expected_included': 14  # All items
        })

        # SCENARIO 2: Very Restrictive (high priority only)
        scenarios.append({
            'name': 'Very Restrictive - High Priority Only (0.7+)',
            'config': {
                'enabled': True,
                'min_priority': 0.7,
                'high_priority_threshold': 0.9,
                'recency_boost': {'enabled': False, 'boost_amount': 0.0, 'time_threshold_hours': 24},
                'category_preferences': {k: False for k in ['product_update', 'financial', 'market_news', 'competitor', 'challenge', 'opportunity', 'leadership', 'partnership', 'advertisement', 'unrelated', 'other']},
                'source_preferences': {k: False for k in ['linkedin', 'press_release', 'reddit', 'hackernews', 'twitter', 'rss', 'google_news', 'yahoo_finance_news']},
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'expected_included': 2  # Only 2 items with priority >= 0.7
        })

        # SCENARIO 3: Source-Focused (only preferred sources)
        scenarios.append({
            'name': 'Source-Focused - Only LinkedIn & Press Releases',
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
                    'yahoo_finance_news': False
                },
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'expected_included': 4  # 2 high priority + 2 preferred sources
        })

        # SCENARIO 4: Category-Focused (business intelligence categories)
        scenarios.append({
            'name': 'Category-Focused - Business Intel Only',
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
                'source_preferences': {k: False for k in ['linkedin', 'press_release', 'reddit', 'hackernews', 'twitter', 'rss', 'google_news', 'yahoo_finance_news']},
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'expected_included': 6  # 2 high priority + 4 preferred categories
        })

        # SCENARIO 5: Balanced (realistic production settings)
        scenarios.append({
            'name': 'Balanced - Realistic Production Settings',
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
                    'leadership': True,
                    'partnership': True,
                    'advertisement': False,
                    'unrelated': False,
                    'other': False
                },
                'source_preferences': {
                    'linkedin': True,
                    'press_release': True,
                    'reddit': False,
                    'hackernews': False,
                    'twitter': False,
                    'rss': True,
                    'google_news': False,
                    'yahoo_finance_news': True
                },
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'expected_included': 9  # Mix of high priority, preferred sources, and categories
        })

        # SCENARIO 6: Priority-Only (no preferences, just priority threshold)
        scenarios.append({
            'name': 'Priority-Only - No Category/Source Preferences',
            'config': {
                'enabled': True,
                'min_priority': 0.4,
                'high_priority_threshold': 0.7,
                'recency_boost': {'enabled': False, 'boost_amount': 0.0, 'time_threshold_hours': 24},
                'category_preferences': {k: False for k in ['product_update', 'financial', 'market_news', 'competitor', 'challenge', 'opportunity', 'leadership', 'partnership', 'advertisement', 'unrelated', 'other']},
                'source_preferences': {k: False for k in ['linkedin', 'press_release', 'reddit', 'hackernews', 'twitter', 'rss', 'google_news', 'yahoo_finance_news']},
                'diversity': {'enabled': True, 'max_consecutive_same_source': 3}
            },
            'expected_included': 4  # Only items with priority >= 0.4
        })

        # Run all scenarios
        results = []
        for scenario in scenarios:
            # Update configuration in database
            save_smart_feed_config(db, scenario['config'])

            # Run test
            passed = run_scenario_test(
                scenario['name'],
                scenario['config'],
                test_items,
                scenario['expected_included']
            )

            results.append({'name': scenario['name'], 'passed': passed})

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
            print("\n✓ All scenarios passed! Smart feed filtering is working correctly.")
        else:
            print(f"\n⚠️  {failed_count} scenario(s) failed. There may be issues with the filtering logic.")

        # Restore original configuration
        if original_config:
            save_smart_feed_config(db, original_config)
            print(f"\n✓ Restored original configuration")
        else:
            print(f"\n⚠️  No original configuration to restore")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    main()
