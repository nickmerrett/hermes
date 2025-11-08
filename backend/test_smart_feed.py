#!/usr/bin/env python3
"""Test script to verify Smart Feed filtering is working correctly"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.database import IntelligenceItem, ProcessedIntelligence, PlatformSettings
from app.utils.smart_feed import (
    get_smart_feed_settings,
    calculate_effective_priority,
    should_include_item,
    apply_diversity_control
)
from datetime import datetime, timedelta
from sqlalchemy import desc


def test_smart_feed():
    """Test smart feed filtering"""

    # Get database session
    db = next(get_db())

    print("=" * 80)
    print("SMART FEED FILTER TEST")
    print("=" * 80)
    print()

    # Load smart feed settings
    print("1. LOADING SMART FEED SETTINGS")
    print("-" * 80)
    smart_config = get_smart_feed_settings(db)
    print(f"Smart Feed Enabled: {smart_config.get('enabled', True)}")
    print(f"Min Priority: {smart_config.get('min_priority', 0.3):.2f}")
    print(f"High Priority Threshold: {smart_config.get('high_priority_threshold', 0.7):.2f}")
    print()

    recency = smart_config.get('recency_boost', {})
    print(f"Recency Boost Enabled: {recency.get('enabled', True)}")
    print(f"Recency Boost Amount: +{recency.get('boost_amount', 0.1):.2f}")
    print(f"Recency Time Threshold: {recency.get('time_threshold_hours', 24)} hours")
    print()

    cat_prefs = smart_config.get('category_preferences', {})
    print("Category Preferences (always show):")
    for cat, enabled in cat_prefs.items():
        if enabled:
            print(f"  ✓ {cat}")
    print()

    src_prefs = smart_config.get('source_preferences', {})
    print("Source Preferences (always show):")
    for src, enabled in src_prefs.items():
        if enabled:
            print(f"  ✓ {src}")
    print()

    diversity = smart_config.get('diversity', {})
    print(f"Diversity Control Enabled: {diversity.get('enabled', True)}")
    print(f"Max Consecutive Same Source: {diversity.get('max_consecutive_same_source', 3)}")
    print()

    # Query items like the feed API does
    print("2. QUERYING DATABASE")
    print("-" * 80)

    # Get primary items only (clustered view)
    query = db.query(IntelligenceItem).filter(
        IntelligenceItem.is_cluster_primary == True
    ).order_by(desc(IntelligenceItem.published_date))

    all_items = query.limit(100).all()
    print(f"Found {len(all_items)} primary items (clustered view)")
    print()

    # Get processed intelligence data
    item_ids = [item.id for item in all_items]
    processed_map = {}
    if item_ids:
        processed_list = db.query(ProcessedIntelligence).filter(
            ProcessedIntelligence.item_id.in_(item_ids)
        ).all()
        processed_map = {p.item_id: p for p in processed_list}

    print(f"Found processed data for {len(processed_map)} items")
    print()

    # Apply smart filtering
    print("3. APPLYING SMART FEED FILTERING")
    print("-" * 80)

    filtered_items = []
    filtered_out = []

    for item in all_items:
        processed = processed_map.get(item.id)

        # Calculate effective priority
        base_priority = processed.priority_score if processed else 0.0
        effective_priority = calculate_effective_priority(item, processed, smart_config)
        recency_boost_applied = effective_priority - base_priority

        # Check if should include
        include = should_include_item(item, processed, effective_priority, smart_config)

        item_info = {
            'item': item,
            'processed': processed,
            'base_priority': base_priority,
            'effective_priority': effective_priority,
            'recency_boost': recency_boost_applied,
            'include': include
        }

        if include:
            filtered_items.append(item_info)
        else:
            filtered_out.append(item_info)

    print(f"Items INCLUDED: {len(filtered_items)}")
    print(f"Items FILTERED OUT: {len(filtered_out)}")
    print()

    # Show why items were filtered out
    if filtered_out:
        print("4. ITEMS FILTERED OUT (first 10):")
        print("-" * 80)
        for info in filtered_out[:10]:
            item = info['item']
            processed = info['processed']
            print(f"\nID: {item.id}")
            print(f"  Title: {item.title[:60]}...")
            print(f"  Source: {item.source_type}")
            print(f"  Category: {processed.category if processed else 'N/A'}")
            print(f"  Base Priority: {info['base_priority']:.2f}")
            print(f"  Effective Priority: {info['effective_priority']:.2f}")
            if info['recency_boost'] > 0:
                print(f"  Recency Boost: +{info['recency_boost']:.2f}")
            print(f"  Published: {item.published_date}")

            # Determine why filtered
            reasons = []
            if info['effective_priority'] < smart_config.get('min_priority', 0.3):
                reasons.append(f"Priority {info['effective_priority']:.2f} < min {smart_config.get('min_priority', 0.3):.2f}")
            if processed and not cat_prefs.get(processed.category, False) and info['effective_priority'] < smart_config.get('high_priority_threshold', 0.7):
                reasons.append(f"Category '{processed.category}' not preferred")
            if not src_prefs.get(item.source_type, False) and info['effective_priority'] < smart_config.get('high_priority_threshold', 0.7):
                reasons.append(f"Source '{item.source_type}' not preferred")

            if reasons:
                print(f"  Reason: {', '.join(reasons)}")
        print()

    # Show included items breakdown
    print("5. ITEMS INCLUDED - BREAKDOWN:")
    print("-" * 80)

    # By source
    source_counts = {}
    for info in filtered_items:
        src = info['item'].source_type
        source_counts[src] = source_counts.get(src, 0) + 1

    print("By Source:")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")
    print()

    # By category
    category_counts = {}
    for info in filtered_items:
        cat = info['processed'].category if info['processed'] else 'Unknown'
        category_counts[cat] = category_counts.get(cat, 0) + 1

    print("By Category:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print()

    # Priority distribution
    print("Priority Distribution (Included Items):")
    priority_ranges = {
        '0.0-0.3': 0,
        '0.3-0.5': 0,
        '0.5-0.7': 0,
        '0.7-1.0': 0,
        '1.0+': 0
    }
    for info in filtered_items:
        p = info['effective_priority']
        if p < 0.3:
            priority_ranges['0.0-0.3'] += 1
        elif p < 0.5:
            priority_ranges['0.3-0.5'] += 1
        elif p < 0.7:
            priority_ranges['0.5-0.7'] += 1
        elif p < 1.0:
            priority_ranges['0.7-1.0'] += 1
        else:
            priority_ranges['1.0+'] += 1

    for range_name, count in priority_ranges.items():
        print(f"  {range_name}: {count}")
    print()

    # Recency boost stats
    boosted_count = sum(1 for info in filtered_items if info['recency_boost'] > 0)
    print(f"Items with Recency Boost Applied: {boosted_count}")
    print()

    # Apply diversity control
    print("6. APPLYING DIVERSITY CONTROL")
    print("-" * 80)
    items_only = [info['item'] for info in filtered_items]
    diversified = apply_diversity_control(items_only, smart_config)

    # Check if order changed
    order_changed = False
    for i, item in enumerate(diversified[:20]):
        if i < len(items_only) and item.id != items_only[i].id:
            order_changed = True
            break

    print(f"Order changed by diversity control: {order_changed}")
    if order_changed:
        print("\nFirst 10 items after diversity control:")
        consecutive_count = 0
        last_source = None
        for i, item in enumerate(diversified[:10]):
            if item.source_type == last_source:
                consecutive_count += 1
            else:
                consecutive_count = 1
                last_source = item.source_type
            print(f"  {i+1}. {item.source_type} (consecutive: {consecutive_count})")
    print()

    # Summary
    print("7. SUMMARY")
    print("=" * 80)
    print(f"Total Primary Items: {len(all_items)}")
    print(f"Items After Smart Filter: {len(filtered_items)} ({len(filtered_items)/len(all_items)*100:.1f}%)")
    print(f"Items Filtered Out: {len(filtered_out)} ({len(filtered_out)/len(all_items)*100:.1f}%)")
    print()

    if len(filtered_items) == len(all_items):
        print("⚠️  WARNING: No items were filtered out!")
        print("   This suggests either:")
        print("   - All items meet the minimum priority threshold")
        print("   - Most items are from preferred sources/categories")
        print("   - Settings are too permissive")
        print()
        print("   Try making settings more strict in Platform Settings:")
        print("   - Increase Minimum Priority to 0.7+")
        print("   - Disable most category/source preferences")
    elif len(filtered_out) > len(all_items) * 0.7:
        print("⚠️  WARNING: More than 70% of items filtered out!")
        print("   Settings might be too strict.")
    else:
        print("✓ Smart Feed filtering is working as expected!")

    db.close()


if __name__ == '__main__':
    try:
        test_smart_feed()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
