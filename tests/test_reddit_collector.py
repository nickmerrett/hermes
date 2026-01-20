#!/usr/bin/env python3
"""
Test script for Reddit collector
"""
import sys
import asyncio
sys.path.insert(0, 'backend')

from app.collectors.reddit_collector import RedditCollector
from app.config.settings import settings


async def test_reddit_collector():
    """Test Reddit collector with IBM customer config"""

    print("="*60)
    print("Reddit Collector Test")
    print("="*60)

    # Check credentials
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        print("\n❌ ERROR: Reddit API credentials not configured")
        print("\nTo test Reddit collector:")
        print("1. Get credentials at https://www.reddit.com/prefs/apps")
        print("2. Create a 'script' app")
        print("3. Add to .env:")
        print("   REDDIT_CLIENT_ID=your_client_id")
        print("   REDDIT_CLIENT_SECRET=your_client_secret")
        print("   REDDIT_USER_AGENT=CustomerIntelligenceTool/1.0")
        return

    print("\n✅ Reddit credentials found")
    print(f"   Client ID: {settings.reddit_client_id[:10]}...")
    print(f"   User Agent: {settings.reddit_user_agent}")

    # Test with IBM customer config
    customer_config = {
        'id': 3,
        'name': 'IBM',
        'keywords': ['IBM', 'Big Blue', 'Watson', 'Red Hat'],
        'config': {
            'reddit_subreddits': ['technology', 'programming', 'artificial', 'IBM']
        }
    }

    print(f"\n🔍 Testing with customer: {customer_config['name']}")
    print(f"   Keywords: {customer_config['keywords'][:3]}")
    print(f"   Subreddits: {customer_config['config']['reddit_subreddits']}")

    try:
        collector = RedditCollector(customer_config)

        print("\n📊 Collector settings:")
        print(f"   Min upvotes: {collector.MIN_UPVOTES}")
        print(f"   Min comments: {collector.MIN_COMMENTS}")
        print(f"   Large thread threshold: {collector.LARGE_THREAD_THRESHOLD} comments")
        print(f"   Max comments to analyze: {collector.MAX_COMMENTS_TO_ANALYZE}")

        print("\n⏳ Collecting Reddit posts...")
        print("   (This may take 30-60 seconds)")

        items = await collector.collect()

        print("\n✅ Collection complete!")
        print(f"   Found {len(items)} items")

        if items:
            print("\n📰 Sample items:")
            for i, item in enumerate(items[:5], 1):
                print(f"\n{i}. {item.title[:80]}")
                print(f"   URL: {item.url}")
                print(f"   Published: {item.published_date}")
                print(f"   Content length: {len(item.content)} chars")

                # Show if it was AI-summarized
                if item.raw_data and item.raw_data.get('ai_summarized'):
                    print(f"   🤖 AI-summarized thread ({item.raw_data['num_comments']} comments)")
                elif item.raw_data:
                    print(f"   💬 {item.raw_data.get('num_comments', 0)} comments, {item.raw_data.get('score', 0)} upvotes")

                # Show content preview
                content_preview = item.content[:300]
                print(f"   Preview: {content_preview}...")
        else:
            print("\n⚠️  No items collected. This could mean:")
            print("   - No recent posts match the keywords")
            print("   - Posts didn't meet engagement thresholds")
            print("   - Subreddits don't have relevant content")
            print("\n💡 Try:")
            print("   - Lower MIN_UPVOTES or MIN_COMMENTS thresholds")
            print("   - Add more relevant subreddits")
            print("   - Increase lookback_days from 7 to 14")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("Test Complete")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_reddit_collector())
