#!/usr/bin/env python3
"""
Debug clustering issues - check similarity between items
"""
import sys
sys.path.insert(0, 'backend')

from app.core.database import SessionLocal
from app.core.vector_store import get_vector_store
from app.models.database import IntelligenceItem
import numpy as np
from datetime import datetime, timedelta

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def debug_clustering():
    """Debug why items aren't clustering"""

    print("="*60)
    print("Clustering Debug Tool")
    print("="*60)

    db = SessionLocal()
    vector_store = get_vector_store()

    try:
        # Find items with "ANZ" and "profit" or "$1.1" in title
        anz_profit_items = db.query(IntelligenceItem).filter(
            IntelligenceItem.title.like('%ANZ%'),
            (IntelligenceItem.title.like('%profit%')) |
            (IntelligenceItem.title.like('%$1.1%')) |
            (IntelligenceItem.title.like('%1.1b%'))
        ).order_by(IntelligenceItem.collected_date.desc()).limit(10).all()

        print(f"\n📰 Found {len(anz_profit_items)} ANZ profit-related items:\n")

        # If no profit items found, search all ANZ items
        if len(anz_profit_items) == 0:
            anz_profit_items = db.query(IntelligenceItem).filter(
                IntelligenceItem.title.like('%ANZ%')
            ).order_by(IntelligenceItem.collected_date.desc()).limit(10).all()
            print(f"(No profit items found, showing all ANZ items)\n")

        anz_items = anz_profit_items

        for i, item in enumerate(anz_items, 1):
            print(f"{i}. [{item.id}] {item.title[:70]}...")
            print(f"   Source: {item.source_type} | Published: {item.published_date}")
            print(f"   Cluster: {item.cluster_id or 'NOT CLUSTERED'} | Primary: {item.is_cluster_primary}")

            # Check if item has embedding
            embedding = vector_store.get_embedding(item.id)
            print(f"   Has embedding: {'✅ Yes' if embedding else '❌ No'}")
            print()

        # Calculate similarities between the ANZ items
        if len(anz_items) >= 2:
            print("\n" + "="*60)
            print("Similarity Matrix (Cosine Similarity)")
            print("="*60 + "\n")

            embeddings = []
            items_with_embeddings = []

            for item in anz_items[:5]:  # Check first 5
                emb = vector_store.get_embedding(item.id)
                if emb:
                    embeddings.append(emb)
                    items_with_embeddings.append(item)

            if len(embeddings) < 2:
                print("⚠️  Not enough items have embeddings to compare")
                return

            # Print header
            print(f"{'':50s}", end="")
            for j, item in enumerate(items_with_embeddings):
                print(f" [{j+1}]  ", end="")
            print()

            # Calculate and print similarity matrix
            for i, (item_i, emb_i) in enumerate(zip(items_with_embeddings, embeddings)):
                print(f"[{i+1}] {item_i.title[:45]:45s}", end="")

                for j, emb_j in enumerate(embeddings):
                    if i == j:
                        print("  -   ", end="")
                    else:
                        sim = cosine_similarity(emb_i, emb_j)
                        color = "🟢" if sim >= 0.60 else "🟡" if sim >= 0.50 else "🔴"
                        print(f" {color}{sim:.2f}", end="")
                print()

            print("\n🟢 >= 0.60 (should cluster - current threshold)")
            print("🟡 0.50-0.59 (close but won't cluster)")
            print("🔴 < 0.50 (too different)")

            # Check time windows
            print("\n" + "="*60)
            print("Time Windows (96-hour window for clustering)")
            print("="*60 + "\n")

            for i, item in enumerate(items_with_embeddings, 1):
                pub_date = item.published_date or item.collected_date
                hours_ago = (datetime.now(pub_date.tzinfo) - pub_date).total_seconds() / 3600
                print(f"[{i}] {pub_date} ({hours_ago:.1f} hours ago)")

        # Show clustering statistics
        print("\n" + "="*60)
        print("Overall Clustering Statistics")
        print("="*60 + "\n")

        total = db.query(IntelligenceItem).count()
        clustered = db.query(IntelligenceItem).filter(
            IntelligenceItem.cluster_id.isnot(None)
        ).count()

        from sqlalchemy import func
        cluster_count = db.query(func.count(func.distinct(IntelligenceItem.cluster_id))).filter(
            IntelligenceItem.cluster_id.isnot(None)
        ).scalar()

        print(f"Total items: {total}")
        print(f"Clustered items: {clustered} ({clustered/total*100:.1f}%)")
        print(f"Unique clusters: {cluster_count}")
        print(f"Items without embeddings: {total - clustered}")

        # Find items without embeddings
        all_items = db.query(IntelligenceItem).all()
        no_embedding_count = 0
        for item in all_items:
            if not vector_store.get_embedding(item.id):
                no_embedding_count += 1

        print(f"\n⚠️  Items missing embeddings: {no_embedding_count}")

        if no_embedding_count > 0:
            print("\n💡 This might explain why clustering isn't working!")
            print("   Items need embeddings to be clustered.")
            print("   New items should get embeddings during collection.")

    finally:
        db.close()

    print("\n" + "="*60)


if __name__ == "__main__":
    debug_clustering()
