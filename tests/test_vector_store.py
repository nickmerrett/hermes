#!/usr/bin/env python3
"""
Diagnostic script to test vector store and semantic search
"""
import sys
sys.path.insert(0, 'backend')

from app.core.database import SessionLocal
from app.core.vector_store import get_vector_store
from app.models.database import IntelligenceItem
from datetime import datetime, timedelta


def test_vector_store():
    """Test vector store functionality"""
    print("="*60)
    print("Vector Store Diagnostics")
    print("="*60)

    vector_store = get_vector_store()
    db = SessionLocal()

    try:
        # Check vector store item count
        vector_count = vector_store.get_item_count()
        print(f"\n✅ Vector store contains {vector_count} items")

        # Check database item count
        db_count = db.query(IntelligenceItem).count()
        print(f"✅ Database contains {db_count} intelligence items")

        # Check for discrepancy
        if vector_count != db_count:
            print(f"\n⚠️  WARNING: Vector store has {vector_count} items but database has {db_count} items")
            print(f"   Difference: {db_count - vector_count} items not indexed")
        else:
            print(f"\n✅ Vector store and database are in sync")

        # Get recent items from database
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_items = db.query(IntelligenceItem).filter(
            IntelligenceItem.collected_date >= last_24h
        ).order_by(IntelligenceItem.collected_date.desc()).limit(5).all()

        if recent_items:
            print(f"\n📰 Recent items from last 24 hours:")
            for item in recent_items:
                print(f"   - [{item.id}] {item.title[:60]}...")
                print(f"     Source: {item.source_type}, Collected: {item.collected_date}")

            # Test if recent items are in vector store
            print(f"\n🔍 Checking if recent items are in vector store...")
            for item in recent_items[:3]:
                try:
                    # Try to search for the item by its title
                    results = vector_store.search(query=item.title, n_results=1)
                    if results['ids'] and len(results['ids'][0]) > 0:
                        result_id = int(results['ids'][0][0])
                        similarity = results['similarities'][0][0]
                        if result_id == item.id:
                            print(f"   ✅ Item {item.id} found in vector store (similarity: {similarity:.2f})")
                        else:
                            print(f"   ⚠️  Item {item.id} search returned different item {result_id}")
                    else:
                        print(f"   ❌ Item {item.id} NOT found in vector store")
                except Exception as e:
                    print(f"   ❌ Error searching for item {item.id}: {e}")
        else:
            print(f"\n⚠️  No items collected in the last 24 hours")

        # Test some sample searches
        print(f"\n🔎 Testing sample semantic searches:")
        test_queries = [
            "technology innovation",
            "financial results earnings",
            "product launch announcement",
        ]

        for query in test_queries:
            try:
                results = vector_store.search(query=query, n_results=3)
                if results['ids'] and len(results['ids'][0]) > 0:
                    print(f"\n   Query: '{query}'")
                    print(f"   Found {len(results['ids'][0])} results:")
                    for idx, (item_id, similarity) in enumerate(zip(results['ids'][0][:3], results['similarities'][0][:3])):
                        item = db.query(IntelligenceItem).filter(
                            IntelligenceItem.id == int(item_id)
                        ).first()
                        if item:
                            print(f"      {idx+1}. [{similarity:.2f}] {item.title[:50]}...")
                else:
                    print(f"\n   Query: '{query}' - No results found")
            except Exception as e:
                print(f"\n   Query: '{query}' - Error: {e}")

    finally:
        db.close()

    print("\n" + "="*60)
    print("Diagnostics Complete")
    print("="*60)


if __name__ == "__main__":
    test_vector_store()
