#!/usr/bin/env python3
"""
Analyze items marked as 'unrelated' or 'other' to identify patterns
and potential AI categorization issues.

This helps identify:
- Common characteristics of miscategorized items
- Source types that get marked as irrelevant
- Patterns in titles/content that confuse the AI
- Potential false positives that should be relevant
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from collections import Counter
import re

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem, ProcessedIntelligence, Customer


def analyze_irrelevant_items(days: int = 30, limit: int = 50, customer_id: int = None):
    """
    Analyze items marked as unrelated or other

    Args:
        days: Number of days to look back
        limit: Max items to display per category
        customer_id: Optionally filter to specific customer
    """

    db = SessionLocal()
    try:
        # Get date threshold
        since_date = datetime.utcnow() - timedelta(days=days)

        print(f"\n{'='*80}")
        print("IRRELEVANT ITEMS ANALYSIS")
        print(f"{'='*80}")
        print(f"Period: Last {days} days (since {since_date.strftime('%Y-%m-%d')})")

        # Get customer info if filtering
        if customer_id:
            customer = db.query(Customer).filter(Customer.id == customer_id).first()
            if customer:
                print(f"Customer: {customer.name}")
            else:
                print(f"ERROR: Customer ID {customer_id} not found")
                return
        else:
            print("Customer: All customers")
        print(f"{'='*80}\n")

        # Build base query
        query = db.query(IntelligenceItem).join(
            ProcessedIntelligence,
            IntelligenceItem.id == ProcessedIntelligence.item_id
        ).filter(
            IntelligenceItem.collected_date >= since_date
        )

        if customer_id:
            query = query.filter(IntelligenceItem.customer_id == customer_id)

        # Get counts by category
        print("📊 CATEGORY DISTRIBUTION")
        print("-" * 80)

        category_counts = db.query(
            ProcessedIntelligence.category,
            func.count(ProcessedIntelligence.id)
        ).join(
            IntelligenceItem,
            IntelligenceItem.id == ProcessedIntelligence.item_id
        ).filter(
            IntelligenceItem.collected_date >= since_date
        )

        if customer_id:
            category_counts = category_counts.filter(IntelligenceItem.customer_id == customer_id)

        category_counts = category_counts.group_by(
            ProcessedIntelligence.category
        ).all()

        total_items = sum(count for _, count in category_counts)
        category_dict = {cat: count for cat, count in category_counts if cat}

        # Sort by count
        for category, count in sorted(category_dict.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_items * 100) if total_items > 0 else 0
            indicator = "⚠️ " if category in ['unrelated', 'other', 'advertisement'] else "   "
            print(f"{indicator}{category:20s}: {count:5d} ({percentage:5.1f}%)")

        print(f"\nTotal items: {total_items}")

        # Calculate problematic items
        problematic = category_dict.get('unrelated', 0) + category_dict.get('other', 0) + category_dict.get('advertisement', 0)
        problematic_pct = (problematic / total_items * 100) if total_items > 0 else 0
        print(f"Potentially problematic: {problematic} ({problematic_pct:.1f}%)")

        # Analyze 'unrelated' items
        print(f"\n\n🔍 ITEMS MARKED AS 'UNRELATED' (up to {limit} items)")
        print("-" * 80)

        unrelated_items = query.filter(
            ProcessedIntelligence.category == 'unrelated'
        ).options(
            joinedload(IntelligenceItem.processed)
        ).order_by(
            IntelligenceItem.collected_date.desc()
        ).limit(limit).all()

        analyze_category_items(db, unrelated_items, "unrelated")

        # Analyze 'other' items
        print(f"\n\n🔍 ITEMS MARKED AS 'OTHER' (up to {limit} items)")
        print("-" * 80)

        other_items = query.filter(
            ProcessedIntelligence.category == 'other'
        ).options(
            joinedload(IntelligenceItem.processed)
        ).order_by(
            IntelligenceItem.collected_date.desc()
        ).limit(limit).all()

        analyze_category_items(db, other_items, "other")

        # Analyze 'advertisement' items
        print(f"\n\n🔍 ITEMS MARKED AS 'ADVERTISEMENT' (up to {limit} items)")
        print("-" * 80)

        advertisement_items = query.filter(
            ProcessedIntelligence.category == 'advertisement'
        ).options(
            joinedload(IntelligenceItem.processed)
        ).order_by(
            IntelligenceItem.collected_date.desc()
        ).limit(limit).all()

        analyze_category_items(db, advertisement_items, "advertisement")

        # Source analysis
        print("\n\n📡 SOURCE ANALYSIS FOR PROBLEMATIC ITEMS")
        print("-" * 80)

        source_counts = db.query(
            IntelligenceItem.source_type,
            func.count(IntelligenceItem.id)
        ).join(
            ProcessedIntelligence,
            IntelligenceItem.id == ProcessedIntelligence.item_id
        ).filter(
            IntelligenceItem.collected_date >= since_date,
            ProcessedIntelligence.category.in_(['unrelated', 'other', 'advertisement'])
        )

        if customer_id:
            source_counts = source_counts.filter(IntelligenceItem.customer_id == customer_id)

        source_counts = source_counts.group_by(
            IntelligenceItem.source_type
        ).order_by(
            func.count(IntelligenceItem.id).desc()
        ).all()

        for source, count in source_counts:
            print(f"{source:25s}: {count:5d} problematic items")

        # Priority score analysis
        print("\n\n📈 PRIORITY SCORE ANALYSIS FOR PROBLEMATIC ITEMS")
        print("-" * 80)

        problematic_with_scores = query.filter(
            ProcessedIntelligence.category.in_(['unrelated', 'other', 'advertisement'])
        ).options(
            joinedload(IntelligenceItem.processed)
        ).all()

        if problematic_with_scores:
            scores = [item.processed.priority_score for item in problematic_with_scores if item.processed]

            if scores:
                avg_score = sum(scores) / len(scores)
                min_score = min(scores)
                max_score = max(scores)

                print(f"Average priority score: {avg_score:.3f}")
                print(f"Min priority score: {min_score:.3f}")
                print(f"Max priority score: {max_score:.3f}")

                # Distribution
                high = sum(1 for s in scores if s >= 0.7)
                medium = sum(1 for s in scores if 0.5 <= s < 0.7)
                low = sum(1 for s in scores if s < 0.5)

                print("\nScore distribution:")
                print(f"  High (≥0.7):   {high:5d} ({high/len(scores)*100:5.1f}%)")
                print(f"  Medium (≥0.5): {medium:5d} ({medium/len(scores)*100:5.1f}%)")
                print(f"  Low (<0.5):    {low:5d} ({low/len(scores)*100:5.1f}%)")

                # Items with high priority but marked as problematic
                high_priority_problematic = [item for item in problematic_with_scores
                                            if item.processed and item.processed.priority_score >= 0.7]

                if high_priority_problematic:
                    print(f"\n⚠️  HIGH PRIORITY BUT MARKED AS PROBLEMATIC ({len(high_priority_problematic)} items):")
                    print("    These may be false positives!")
                    for item in high_priority_problematic[:10]:
                        customer = db.query(Customer).filter(Customer.id == item.customer_id).first()
                        print(f"\n    • {item.title[:80]}")
                        print(f"      Customer: {customer.name if customer else 'Unknown'}")
                        print(f"      Source: {item.source_type}")
                        print(f"      Priority: {item.processed.priority_score:.3f}")
                        print(f"      Category: {item.processed.category}")
                        print(f"      Sentiment: {item.processed.sentiment}")

    finally:
        db.close()


def analyze_category_items(db, items, category_name):
    """Analyze items in a specific category"""

    if not items:
        print(f"No items found in '{category_name}' category")
        return

    print(f"Found {len(items)} items\n")

    # Source breakdown
    sources = Counter(item.source_type for item in items)
    print("Sources:")
    for source, count in sources.most_common():
        print(f"  {source:20s}: {count:3d}")

    # Keyword analysis - common words in titles
    print("\nCommon words in titles:")
    all_words = []
    for item in items:
        # Extract words (alphanumeric, 3+ chars)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', item.title.lower())
        all_words.extend(words)

    # Filter out common stop words
    stop_words = {'the', 'and', 'for', 'with', 'from', 'that', 'this', 'are', 'was',
                  'has', 'have', 'but', 'not', 'can', 'will', 'more', 'about', 'than',
                  'been', 'how', 'what', 'when', 'where', 'who', 'why', 'their', 'said'}

    filtered_words = [w for w in all_words if w not in stop_words]
    word_counts = Counter(filtered_words)

    for word, count in word_counts.most_common(15):
        print(f"  {word:15s}: {count:3d}")

    # Sample items
    print("\nSample items (first 10):\n")

    for idx, item in enumerate(items[:10], 1):
        customer = db.query(Customer).filter(Customer.id == item.customer_id).first()

        print(f"{idx}. {item.title}")
        print(f"   Customer: {customer.name if customer else 'Unknown'}")
        print(f"   Source: {item.source_type}")
        print(f"   Date: {item.published_date or item.collected_date}")

        if item.processed:
            print(f"   Priority: {item.processed.priority_score:.3f}")
            print(f"   Sentiment: {item.processed.sentiment}")
            if item.processed.summary:
                summary = item.processed.summary[:150].replace('\n', ' ')
                print(f"   Summary: {summary}...")

        # Show snippet of content
        if item.content:
            content_snippet = item.content[:200].replace('\n', ' ')
            print(f"   Content: {content_snippet}...")

        print(f"   URL: {item.url}")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze items marked as unrelated/other to identify AI categorization issues"
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to look back (default: 30)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Max items to display per category (default: 50)'
    )
    parser.add_argument(
        '--customer-id',
        type=int,
        help='Filter to specific customer ID'
    )

    args = parser.parse_args()

    analyze_irrelevant_items(
        days=args.days,
        limit=args.limit,
        customer_id=args.customer_id
    )
