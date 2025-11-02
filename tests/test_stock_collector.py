#!/usr/bin/env python3
"""
Test script for updated StockCollector with Playwright scraper
"""
import asyncio
import sys
sys.path.insert(0, 'backend')

from app.collectors.stock_collector import StockCollector


async def test_stock_collector():
    """Test the stock collector with ANZ.AX"""

    # Mock customer config
    customer_config = {
        'name': 'Test Customer',
        'stock_symbol': 'ANZ.AX',
        'collection_config': {
            'stock_enabled': True
        }
    }

    print("="*60)
    print("Testing StockCollector with ANZ.AX")
    print("="*60)

    collector = StockCollector(customer_config)

    print(f"\nCollecting data for {collector.stock_symbol}...")
    print(f"Source type: {collector.get_source_type()}\n")

    try:
        items = await collector.collect()

        print(f"\n{'='*60}")
        print(f"Collected {len(items)} intelligence items")
        print(f"{'='*60}\n")

        for i, item in enumerate(items, 1):
            print(f"{i}. {item.title}")
            print(f"   URL: {item.url}")
            print(f"   Published: {item.published_date}")
            print(f"   Content preview: {item.content[:100]}...")
            if item.raw_data:
                print(f"   Publisher: {item.raw_data.get('publisher', 'N/A')}")
                print(f"   Type: {item.raw_data.get('type', 'N/A')}")
            print()

        print(f"{'='*60}")
        print("Test completed successfully!")
        print(f"{'='*60}")

    except Exception as e:
        print(f"\n❌ Error during collection: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_stock_collector())
