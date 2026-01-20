#!/usr/bin/env python3
"""
Test script for story clustering functionality
"""
import sys
sys.path.insert(0, 'backend')

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem
from sqlalchemy import func

def test_clustering():
    """Test that clustering is working"""

    print("="*60)
    print("Story Clustering Test")
    print("="*60)

    db = SessionLocal()

    try:
        # Check if clustering columns exist
        print("\n1. Checking database schema...")
        try:
            # Try to query the new columns
            result = db.query(IntelligenceItem.cluster_id).first()
            print("   ✅ Clustering columns exist in database")
        except Exception as e:
            print(f"   ❌ Clustering columns not found: {e}")
            print("\n   Run migration first: python3 migrate_clustering.py")
            return

        # Get total item count
        total_items = db.query(IntelligenceItem).count()
        print(f"\n2. Total intelligence items: {total_items}")

        if total_items == 0:
            print("   ⚠️  No items in database yet - clustering will happen during collection")
            return

        # Check clustered items
        clustered_items = db.query(IntelligenceItem).filter(
            IntelligenceItem.cluster_id.isnot(None)
        ).count()

        print(f"\n3. Clustered items: {clustered_items}")

        if clustered_items == 0:
            print("   ⚠️  No items have been clustered yet")
            print("   This is normal for existing data - clustering happens on new collections")
            print("\n   To test clustering:")
            print("   1. Wait for next scheduled collection, OR")
            print("   2. Manually trigger collection via API")
        else:
            print(f"   ✅ {clustered_items}/{total_items} items are clustered")

            # Get cluster statistics
            cluster_count = db.query(func.count(func.distinct(IntelligenceItem.cluster_id))).filter(
                IntelligenceItem.cluster_id.isnot(None)
            ).scalar()

            print(f"\n4. Total clusters: {cluster_count}")

            # Find clusters with multiple items
            multi_item_clusters = db.query(
                IntelligenceItem.cluster_id,
                func.count(IntelligenceItem.id).label('count')
            ).filter(
                IntelligenceItem.cluster_id.isnot(None)
            ).group_by(
                IntelligenceItem.cluster_id
            ).having(
                func.count(IntelligenceItem.id) > 1
            ).all()

            if multi_item_clusters:
                print("\n5. Multi-source stories (same story from different sources):")
                print(f"   Found {len(multi_item_clusters)} stories covered by multiple sources\n")

                for cluster_id, count in multi_item_clusters[:5]:  # Show top 5
                    # Get items in this cluster
                    items = db.query(IntelligenceItem).filter(
                        IntelligenceItem.cluster_id == cluster_id
                    ).all()

                    primary = next((i for i in items if i.is_cluster_primary), items[0])
                    sources = [f"{i.source_type}" for i in items]

                    print(f"   📰 {primary.title[:70]}...")
                    print(f"      {count} sources: {', '.join(set(sources))}")
                    print(f"      Cluster ID: {cluster_id}")
                    print()

            # Show source tier distribution
            print("\n6. Source tier distribution:")
            tiers = db.query(
                IntelligenceItem.source_tier,
                func.count(IntelligenceItem.id)
            ).filter(
                IntelligenceItem.source_tier.isnot(None)
            ).group_by(
                IntelligenceItem.source_tier
            ).all()

            if tiers:
                for tier, count in tiers:
                    print(f"   {tier}: {count} items")
            else:
                print("   No source tier data yet")

            # Show primary items
            primary_count = db.query(IntelligenceItem).filter(
                IntelligenceItem.is_cluster_primary == True
            ).count()

            print(f"\n7. Primary items (cluster representatives): {primary_count}")

            if primary_count > 0:
                print("\n   Example primary items:")
                primaries = db.query(IntelligenceItem).filter(
                    IntelligenceItem.is_cluster_primary == True
                ).limit(3).all()

                for item in primaries:
                    print(f"   - [{item.source_tier}] {item.title[:60]}...")
                    print(f"     Cluster size: {item.cluster_member_count} items")

    finally:
        db.close()

    print("\n" + "="*60)
    print("Test Complete")
    print("="*60)
    print("\n✅ Clustering is configured and ready!")
    print("\nNext steps:")
    print("- New items will be automatically clustered during collection")
    print("- Check feed UI to see clustered items (once frontend is updated)")


if __name__ == "__main__":
    test_clustering()
