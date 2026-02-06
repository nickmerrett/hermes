#!/usr/bin/env python3
"""Regenerate all embeddings in ChromaDB from current item content"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem
from app.core.vector_store import get_vector_store
from app.utils.text_cleaning import clean_text_for_embedding
from sqlalchemy import desc
import argparse


def regenerate_embeddings(hours: int = None, item_ids: list = None, batch_size: int = 100):
    """Regenerate embeddings for items"""
    db = SessionLocal()
    vector_store = get_vector_store()

    # Build query
    query = db.query(IntelligenceItem)

    if item_ids:
        query = query.filter(IntelligenceItem.id.in_(item_ids))
        print(f"Regenerating embeddings for {len(item_ids)} specific items")
    elif hours:
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = query.filter(IntelligenceItem.collected_date >= cutoff)
        print(f"Regenerating embeddings for items from last {hours} hours")
    else:
        print("Regenerating ALL embeddings (this may take a while)")

    query = query.order_by(desc(IntelligenceItem.id))
    items = query.all()
    total = len(items)

    print(f"Found {total} items to process")
    print(f"Current ChromaDB count: {vector_store.get_item_count()}")
    print()

    success = 0
    errors = 0

    for i, item in enumerate(items):
        try:
            # Delete existing embedding
            try:
                vector_store.collection.delete(ids=[str(item.id)])
            except Exception:
                pass  # May not exist

            # Generate new embedding (strip HTML/markdown/URLs from content)
            text_for_embedding = clean_text_for_embedding(item.title, item.content)
            embedding = vector_store.embedding_model.encode(text_for_embedding).tolist()

            # Store new embedding
            vector_store.collection.add(
                ids=[str(item.id)],
                embeddings=[embedding],
                metadatas=[{
                    'customer_id': item.customer_id,
                    'source_type': item.source_type or '',
                }],
                documents=[text_for_embedding]
            )
            success += 1

            if (i + 1) % 50 == 0:
                print(f"Progress: {i + 1}/{total} ({success} success, {errors} errors)")

        except Exception as e:
            print(f"Error processing item {item.id}: {e}")
            errors += 1

    print()
    print(f"{'='*60}")
    print("COMPLETE")
    print(f"{'='*60}")
    print(f"Total processed: {total}")
    print(f"Success: {success}")
    print(f"Errors: {errors}")
    print(f"Final ChromaDB count: {vector_store.get_item_count()}")

    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Regenerate embeddings in ChromaDB')
    parser.add_argument('--hours', type=int, help='Regenerate items from last N hours')
    parser.add_argument('--ids', type=int, nargs='+', help='Specific item IDs to regenerate')
    parser.add_argument('--all', action='store_true', help='Regenerate ALL embeddings')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing')

    args = parser.parse_args()

    if not args.hours and not args.ids and not args.all:
        print("Usage:")
        print("  python regenerate_embeddings.py --hours 48     # Last 48 hours")
        print("  python regenerate_embeddings.py --ids 4651 4650 4639  # Specific items")
        print("  python regenerate_embeddings.py --all          # Everything")
        sys.exit(1)

    regenerate_embeddings(
        hours=args.hours,
        item_ids=args.ids,
        batch_size=args.batch_size
    )
