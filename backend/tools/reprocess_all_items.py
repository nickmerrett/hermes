#!/usr/bin/env python3
"""Find and reprocess all items with missing AI data"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import get_db
from app.models.database import ProcessedIntelligence, IntelligenceItem, Customer
from app.processors.ai_processor import get_ai_processor
from app.core.vector_store import get_vector_store
from app.utils.text_cleaning import clean_text_for_embedding
from datetime import datetime

async def reprocess_all_incomplete_items():
    """Find and reprocess all items with incomplete AI processing"""

    db = next(get_db())

    print("=" * 80)
    print("AI REPROCESSING - FINDING INCOMPLETE ITEMS")
    print("=" * 80)

    # Find items with missing AI processing data
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
    print("\n📋 Sample items:")
    for i, proc_item in enumerate(incomplete_items[:5], 1):
        intel_item = db.query(IntelligenceItem).filter(
            IntelligenceItem.id == proc_item.item_id
        ).first()
        if intel_item:
            print(f"  {i}. [{intel_item.customer_id}] {intel_item.title[:60]}...")

    if len(incomplete_items) > 5:
        print(f"  ... and {len(incomplete_items) - 5} more")

    # Ask for confirmation
    print(f"\n⚠️  This will reprocess {len(incomplete_items)} items with AI.")
    print("   This may take a while and will use API credits.")
    response = input("\nContinue? (yes/no): ")

    if response.lower() not in ['yes', 'y']:
        print("\n❌ Cancelled")
        return

    print("\n" + "=" * 80)
    print("STARTING REPROCESSING")
    print("=" * 80)

    # Initialize AI processor and vector store
    ai_processor = get_ai_processor(db)
    vector_store = get_vector_store()

    print(f"\n✓ AI Processor initialized: {ai_processor.provider} - {ai_processor.model}")

    success_count = 0
    error_count = 0

    for i, proc_item in enumerate(incomplete_items, 1):
        try:
            # Get the intelligence item
            item = db.query(IntelligenceItem).filter(
                IntelligenceItem.id == proc_item.item_id
            ).first()

            if not item:
                print(f"  [{i}/{len(incomplete_items)}] ❌ Item {proc_item.item_id} not found")
                error_count += 1
                continue

            # Get customer
            customer = db.query(Customer).filter(Customer.id == item.customer_id).first()

            if not customer:
                print(f"  [{i}/{len(incomplete_items)}] ❌ Customer {item.customer_id} not found")
                error_count += 1
                continue

            # Process with AI
            result = await ai_processor.process_item(
                title=item.title,
                content=item.content or "",
                customer_name=customer.name,
                source_type=item.source_type,
                keywords=customer.keywords or [],
                competitors=customer.competitors or [],
                priority_keywords=customer.priority_keywords or []
            )

            # Update processed intelligence
            proc_item.summary = result.get('summary', '')
            proc_item.category = result.get('category', 'other')
            proc_item.sentiment = result.get('sentiment', 'neutral')
            proc_item.entities = result.get('entities', {})
            proc_item.tags = result.get('tags', [])
            proc_item.priority_score = result.get('priority_score', 0.5)
            proc_item.is_relevant = result.get('is_relevant', True)
            proc_item.needs_reprocessing = False
            proc_item.processing_error = None
            proc_item.last_processing_attempt = datetime.utcnow()

            # Update vector store
            try:
                vector_store.add_item(
                    item_id=str(item.id),
                    text=clean_text_for_embedding(item.title, item.content),
                    metadata={
                        'customer_id': item.customer_id,
                        'source_type': item.source_type,
                        'category': proc_item.category,
                        'sentiment': proc_item.sentiment,
                        'published_timestamp': int(
                            (item.published_date or item.collected_date or datetime.utcnow()).timestamp()
                        ),
                    }
                )
            except Exception as ve:
                print(f"  [{i}/{len(incomplete_items)}] ⚠️  Vector store update failed: {ve}")

            db.commit()

            print(f"  [{i}/{len(incomplete_items)}] ✓ {item.title[:60]}...")
            success_count += 1

        except Exception as e:
            print(f"  [{i}/{len(incomplete_items)}] ❌ Error: {e}")
            proc_item.needs_reprocessing = True
            proc_item.processing_error = str(e)
            proc_item.last_processing_attempt = datetime.utcnow()
            db.commit()
            error_count += 1

        # Commit every 10 items
        if i % 10 == 0:
            db.commit()

    print("\n" + "=" * 80)
    print("REPROCESSING COMPLETE")
    print("=" * 80)
    print(f"\n✓ Successfully processed: {success_count}")
    print(f"❌ Failed: {error_count}")
    print(f"📊 Total: {len(incomplete_items)}")
    print("\n" + "=" * 80)

if __name__ == "__main__":
    try:
        asyncio.run(reprocess_all_incomplete_items())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
