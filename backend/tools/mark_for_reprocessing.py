#!/usr/bin/env python3
"""Mark items with missing AI processing for reprocessing"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import get_db
from app.models.database import ProcessedIntelligence, IntelligenceItem
from datetime import datetime

def mark_items_for_reprocessing():
    """Mark items with missing/incomplete AI processing for reprocessing"""

    db = next(get_db())

    print("=" * 80)
    print("MARKING ITEMS FOR AI REPROCESSING")
    print("=" * 80)

    # Find items with missing AI processing data
    # Items are considered incomplete if they have empty/null summary or entities
    query = db.query(ProcessedIntelligence).filter(
        (ProcessedIntelligence.summary.is_(None)) |
        (ProcessedIntelligence.summary == '') |
        (ProcessedIntelligence.entities.is_(None)) |
        (ProcessedIntelligence.entities == '{}') |
        (ProcessedIntelligence.entities == '{"companies": [], "technologies": [], "people": []}')
    )

    incomplete_items = query.all()

    print(f"\n📊 Found {len(incomplete_items)} items with incomplete AI processing")

    if not incomplete_items:
        print("\n✓ All items appear to have complete AI processing!")
        return

    # Show some examples
    print("\n📋 Sample items that will be reprocessed:")
    for i, item in enumerate(incomplete_items[:5], 1):
        intel_item = db.query(IntelligenceItem).filter(
            IntelligenceItem.id == item.item_id
        ).first()
        if intel_item:
            print(f"  {i}. {intel_item.title[:60]}...")
            print(f"     Summary: {item.summary[:50] if item.summary else 'MISSING'}...")
            print(f"     Entities: {item.entities if item.entities else 'MISSING'}")

    if len(incomplete_items) > 5:
        print(f"  ... and {len(incomplete_items) - 5} more")

    # Ask for confirmation
    print(f"\n⚠️  This will mark {len(incomplete_items)} items for reprocessing.")
    response = input("Continue? (yes/no): ")

    if response.lower() not in ['yes', 'y']:
        print("\n❌ Cancelled")
        return

    # Mark items for reprocessing
    marked_count = 0
    for item in incomplete_items:
        item.needs_reprocessing = True
        item.last_processing_attempt = datetime.utcnow()
        item.processing_error = "Marked for reprocessing - incomplete AI data"
        marked_count += 1

    db.commit()

    print(f"\n✓ Marked {marked_count} items for reprocessing!")
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\n1. Items are now marked with needs_reprocessing = True")
    print("\n2. To reprocess them, call the API endpoint:")
    print(f"   curl -X POST 'http://localhost:8000/api/jobs/reprocess-failed?max_items={marked_count}'")
    print("\n   Or reprocess in batches of 100:")
    print("   curl -X POST 'http://localhost:8000/api/jobs/reprocess-failed?max_items=100'")
    print("\n3. The items will be processed in the background using the new AI config")
    print("=" * 80)

if __name__ == "__main__":
    try:
        mark_items_for_reprocessing()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
