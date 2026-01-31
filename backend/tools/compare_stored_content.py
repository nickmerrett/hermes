#!/usr/bin/env python3
"""Compare what's stored in ChromaDB vs what's in the database"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem
from app.core.vector_store import get_vector_store


def compare_content(item_ids: list):
    """Compare stored ChromaDB documents with current DB content"""
    db = SessionLocal()
    vector_store = get_vector_store()

    print(f"\n{'='*80}")
    print("CONTENT COMPARISON: ChromaDB vs Database")
    print(f"{'='*80}\n")

    for item_id in item_ids:
        item = db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()
        if not item:
            print(f"Item {item_id}: NOT FOUND IN DATABASE")
            continue

        # Get stored document from ChromaDB
        try:
            result = vector_store.collection.get(
                ids=[str(item_id)],
                include=['documents', 'metadatas']
            )
            stored_doc = result['documents'][0] if result['documents'] else None
            stored_meta = result['metadatas'][0] if result['metadatas'] else {}
        except Exception as e:
            print(f"Item {item_id}: ERROR getting from ChromaDB: {e}")
            continue

        # What we would embed now
        expected_doc = f"{item.title}\n\n{item.content or ''}"

        print(f"Item {item_id}:")
        print(f"  Title (DB): {item.title[:70]}...")
        print(f"  Source: {item.source_type}")
        print()
        print(f"  DB content length: {len(item.content or '')} chars")
        print(f"  Expected doc length: {len(expected_doc)} chars")
        print(f"  Stored doc length: {len(stored_doc or '')} chars")
        print()

        if stored_doc:
            # Check if they match
            if stored_doc == expected_doc:
                print("  ✓ MATCH: Stored document matches expected")
            else:
                print("  ✗ MISMATCH!")
                print()

                # Show first 200 chars of each
                print("  Expected (first 200 chars):")
                print(f"    '{expected_doc[:200]}...'")
                print()
                print("  Stored (first 200 chars):")
                print(f"    '{stored_doc[:200]}...'")
                print()

                # Try to figure out what's stored
                # Check if it's from a different item
                if "\n\n" in stored_doc:
                    stored_title = stored_doc.split("\n\n")[0]
                    print(f"  Stored title appears to be: '{stored_title[:70]}...'")

                    # Find if this title belongs to a different item
                    other_item = db.query(IntelligenceItem).filter(
                        IntelligenceItem.title == stored_title
                    ).first()
                    if other_item and other_item.id != item_id:
                        print(f"  ⚠️  THIS IS CONTENT FROM ITEM {other_item.id}!")
        else:
            print("  ⚠️  NO DOCUMENT STORED IN CHROMADB")

        print(f"  Stored metadata: {stored_meta}")
        print()
        print("-" * 80)
        print()

    db.close()


if __name__ == "__main__":
    default_ids = [4651, 4650, 4639, 4587, 4582, 4564]

    if len(sys.argv) > 1:
        item_ids = [int(x) for x in sys.argv[1:]]
    else:
        item_ids = default_ids
        print(f"Usage: python {sys.argv[0]} <item_id1> <item_id2> ...")
        print(f"Using default IDs: {default_ids}")

    compare_content(item_ids)
