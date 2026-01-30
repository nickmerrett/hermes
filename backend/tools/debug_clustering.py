#!/usr/bin/env python3
"""
Debug clustering issues - check similarity between items

Usage:
    python tools/debug_clustering.py "search term"
    python tools/debug_clustering.py "Rio Tinto"
    python tools/debug_clustering.py  # defaults to recent items
"""
import sys
import argparse
import re
sys.path.insert(0, 'backend')

from app.core.database import SessionLocal
from app.core.vector_store import get_vector_store
from app.models.database import IntelligenceItem, PlatformSettings
from app.utils.clustering import get_clustering_settings, title_similarity
import numpy as np
from datetime import datetime, timedelta

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def debug_clustering(search_term=None, limit=10):
    """Debug why items aren't clustering"""

    print("="*60)
    print("Clustering Debug Tool")
    print("="*60)

    db = SessionLocal()
    vector_store = get_vector_store()

    try:
        # Load current clustering settings
        settings = get_clustering_settings(db)
        print(f"\n⚙️  Current clustering settings:")
        print(f"   Embedding threshold: {settings.get('similarity_threshold', 0.80)}")
        print(f"   Title similarity enabled: {settings.get('title_similarity_enabled', True)}")
        print(f"   Title similarity threshold: {settings.get('title_similarity_threshold', 0.40)}")
        print(f"   Time window: {settings.get('time_window_hours', 96)} hours")
        print(f"   Max cluster size: {settings.get('max_cluster_size', 25)}")
        print(f"   Max cluster age: {settings.get('max_cluster_age_hours', 168)} hours")

        # Search for items
        if search_term:
            print(f"\n🔍 Searching for: '{search_term}'")
            items = db.query(IntelligenceItem).filter(
                IntelligenceItem.title.ilike(f'%{search_term}%')
            ).order_by(IntelligenceItem.collected_date.desc()).limit(limit).all()
        else:
            print(f"\n🔍 Showing {limit} most recent items")
            items = db.query(IntelligenceItem).order_by(
                IntelligenceItem.collected_date.desc()
            ).limit(limit).all()

        print(f"\n📰 Found {len(items)} items:\n")

        for i, item in enumerate(items, 1):
            title_display = item.title[:70] + "..." if len(item.title) > 70 else item.title
            print(f"{i}. [{item.id}] {title_display}")
            print(f"   Source: {item.source_type} | Published: {item.published_date}")
            cluster_display = item.cluster_id[:8] + "..." if item.cluster_id else 'NONE'
            print(f"   Cluster: {cluster_display} | Primary: {item.is_cluster_primary} | Members: {item.cluster_member_count or 1}")

            # Check if item has embedding
            embedding = vector_store.get_embedding(item.id)
            print(f"   Has embedding: {'✅ Yes' if embedding else '❌ No'}")
            print()

        # Calculate similarities between items
        if len(items) >= 2:
            emb_threshold = settings.get('similarity_threshold', 0.80)
            title_threshold = settings.get('title_similarity_threshold', 0.40)

            print("\n" + "="*60)
            print("Pairwise Similarity Analysis")
            print("="*60)
            print(f"Thresholds: embedding >= {emb_threshold}, title >= {title_threshold}")
            print("Both must pass for clustering to occur\n")

            embeddings = []
            items_with_embeddings = []

            for item in items[:8]:  # Check first 8
                emb = vector_store.get_embedding(item.id)
                if emb is not None:
                    embeddings.append(emb)
                    items_with_embeddings.append(item)

            if len(items_with_embeddings) < 2:
                print("⚠️  Not enough items have embeddings to compare")
            else:
                # Pairwise comparison
                for i in range(len(items_with_embeddings)):
                    for j in range(i + 1, len(items_with_embeddings)):
                        item_i = items_with_embeddings[i]
                        item_j = items_with_embeddings[j]
                        emb_i = embeddings[i]
                        emb_j = embeddings[j]

                        emb_sim = cosine_similarity(emb_i, emb_j)
                        title_sim = title_similarity(item_i.title, item_j.title)

                        emb_pass = emb_sim >= emb_threshold
                        title_pass = title_sim >= title_threshold
                        would_cluster = emb_pass and title_pass

                        same_cluster = (item_i.cluster_id and item_j.cluster_id and
                                       item_i.cluster_id == item_j.cluster_id)

                        print(f"[{i+1}] vs [{j+1}]:")
                        print(f"   Embedding: {emb_sim:.3f} {'✅' if emb_pass else '❌'}")
                        print(f"   Title:     {title_sim:.3f} {'✅' if title_pass else '❌'}")

                        if would_cluster:
                            status = "✅ WOULD CLUSTER"
                        else:
                            reasons = []
                            if not emb_pass:
                                reasons.append(f"embedding {emb_sim:.2f} < {emb_threshold}")
                            if not title_pass:
                                reasons.append(f"title {title_sim:.2f} < {title_threshold}")
                            status = f"❌ BLOCKED: {', '.join(reasons)}"

                        print(f"   Result: {status}")
                        if same_cluster:
                            print(f"   Currently: ✅ Same cluster")
                        else:
                            print(f"   Currently: Different clusters")
                        print()

            # Check time windows
            print("\n" + "="*60)
            print(f"Time Windows ({settings.get('time_window_hours', 96)}-hour window)")
            print("="*60 + "\n")

            for i, item in enumerate(items_with_embeddings, 1):
                pub_date = item.published_date or item.collected_date
                try:
                    now = datetime.now(pub_date.tzinfo) if pub_date.tzinfo else datetime.now()
                    hours_ago = (now - pub_date).total_seconds() / 3600
                    print(f"[{i}] {pub_date} ({hours_ago:.1f} hours ago)")
                except Exception as e:
                    print(f"[{i}] {pub_date} (time calc error: {e})")

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
        print(f"Clustered items: {clustered} ({clustered/total*100:.1f}% if total > 0 else 0)")
        print(f"Unique clusters: {cluster_count}")

    finally:
        db.close()

    print("\n" + "="*60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug clustering issues")
    parser.add_argument("search", nargs="?", default=None, help="Search term to filter items (e.g., 'Rio Tinto')")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Number of items to show (default: 10)")
    args = parser.parse_args()

    debug_clustering(search_term=args.search, limit=args.limit)
