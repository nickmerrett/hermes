#!/usr/bin/env python3
"""
Migrate Stock Collector to Yahoo Finance News Collector

This script:
1. Updates source_type from 'stock' to 'yahoo_finance_news' in intelligence_items
2. Updates source_type from 'stock' to 'yahoo_finance_news' in collection_status
3. Prints statistics about the migration

Run this after renaming StockCollector to YahooFinanceNewsCollector
"""

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem, CollectionStatus
from sqlalchemy import update

def migrate():
    """Migrate stock source_type to yahoo_finance_news"""

    db = SessionLocal()

    try:
        print("=" * 70)
        print("Migrating Stock Collector → Yahoo Finance News Collector")
        print("=" * 70)
        print()

        # Count existing 'stock' items
        stock_items_count = db.query(IntelligenceItem).filter(
            IntelligenceItem.source_type == 'stock'
        ).count()

        stock_status_count = db.query(CollectionStatus).filter(
            CollectionStatus.source_type == 'stock'
        ).count()

        print("Found:")
        print(f"  • {stock_items_count} intelligence items with source_type='stock'")
        print(f"  • {stock_status_count} collection status records with source_type='stock'")
        print()

        if stock_items_count == 0 and stock_status_count == 0:
            print("✅ No migration needed - no 'stock' records found")
            return

        # Confirm migration
        response = input("Proceed with migration? (y/n): ")
        if response.lower() != 'y':
            print("❌ Migration cancelled")
            return

        print()
        print("Migrating...")

        # Migrate intelligence_items
        if stock_items_count > 0:
            db.execute(
                update(IntelligenceItem)
                .where(IntelligenceItem.source_type == 'stock')
                .values(source_type='yahoo_finance_news')
            )
            db.commit()
            print(f"✅ Updated {stock_items_count} intelligence items")

        # Migrate collection_status
        if stock_status_count > 0:
            db.execute(
                update(CollectionStatus)
                .where(CollectionStatus.source_type == 'stock')
                .values(source_type='yahoo_finance_news')
            )
            db.commit()
            print(f"✅ Updated {stock_status_count} collection status records")

        print()
        print("=" * 70)
        print("✅ Migration Complete!")
        print("=" * 70)
        print()
        print("Summary:")
        print(f"  • Intelligence items: stock → yahoo_finance_news ({stock_items_count} items)")
        print(f"  • Collection status: stock → yahoo_finance_news ({stock_status_count} records)")
        print()
        print("Next steps:")
        print("  1. Restart the backend container")
        print("  2. Update customer configs to use 'yahoo_finance_news_enabled'")
        print("  3. Old 'stock_enabled' configs will automatically migrate to 'yahoo_finance_news_enabled'")
        print()

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    migrate()
