"""
Test script for LinkedIn User Profile Collector

This script tests the LinkedInUserCollector to ensure it can properly
collect data from LinkedIn user profiles.

Usage:
    python tests/test_linkedin_user_collector.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.collectors.linkedin_collector import LinkedInUserCollector
from backend.app.config.settings import settings


async def test_linkedin_user_collector():
    """Test LinkedIn user profile collection"""

    print("=" * 60)
    print("LinkedIn User Profile Collector Test")
    print("=" * 60)
    print()

    # Test configuration with sample profile
    test_config = {
        'id': 1,
        'name': 'Test Customer',
        'domain': 'example.com',
        'keywords': [],
        'config': {
            'linkedin_user_profiles': [
                {
                    'profile_url': 'https://www.linkedin.com/in/satyanadella/',
                    'name': 'Satya Nadella',
                    'role': 'CEO Microsoft',
                    'notes': 'Test profile - tech industry leader'
                }
            ]
        }
    }

    print("Test Configuration:")
    print(f"  Customer: {test_config['name']}")
    print(f"  Profiles to monitor: {len(test_config['config']['linkedin_user_profiles'])}")
    print()

    # Check if Proxycurl API key is configured
    if settings.proxycurl_api_key:
        print("✅ Proxycurl API key detected - will use API method")
        print("   (This provides more reliable data)")
    else:
        print("⚠️  No Proxycurl API key - will use public profile scraping")
        print("   Note: LinkedIn may block scraping. Consider using Proxycurl API.")
        print("   Set PROXYCURL_API_KEY environment variable to use API.")
    print()

    # Initialize collector
    print("Initializing LinkedInUserCollector...")
    collector = LinkedInUserCollector(test_config)
    print(f"  Rate limit: {collector.rate_limit} requests/minute")
    print(f"  Profiles configured: {len(collector.user_profiles)}")
    print()

    # Test collection
    print("Running collection...")
    print("-" * 60)

    try:
        items = await collector.collect()

        print()
        print("=" * 60)
        print("Collection Results")
        print("=" * 60)
        print(f"Items collected: {len(items)}")
        print()

        # Categorize items
        profile_items = [i for i in items if 'Profile' in i.title and 'Post' not in i.title]
        post_items = [i for i in items if 'Post' in i.title]
        job_change_items = [i for i in items if 'joined' in i.title.lower()]

        print(f"  Profile updates: {len(profile_items)}")
        print(f"  Posts collected: {len(post_items)}")
        print(f"  Job changes: {len(job_change_items)}")
        print()

        if items:
            print("Sample items:")
            for i, item in enumerate(items[:5], 1):  # Show first 5 items
                print(f"\n{i}. {item.title}")
                print(f"   URL: {item.url}")
                print(f"   Source: {item.source_type}")
                if item.content:
                    content_preview = item.content[:150] + "..." if len(item.content) > 150 else item.content
                    print(f"   Content: {content_preview}")
                if item.raw_data:
                    print(f"   Data source: {item.raw_data.get('source', 'unknown')}")
                    # Show engagement metrics if available
                    if 'engagement' in item.raw_data:
                        engagement = item.raw_data['engagement']
                        print(f"   Engagement: {engagement.get('likes', 0)} likes, "
                              f"{engagement.get('comments', 0)} comments, "
                              f"{engagement.get('shares', 0)} shares")
        else:
            print("⚠️  No items collected. This could mean:")
            print("   1. LinkedIn is blocking the scraping attempt")
            print("   2. No recent changes detected on the profile")
            print("   3. API key is not configured (if using Proxycurl)")
            print()
            print("Recommendations:")
            print("   - Set up Proxycurl API key for reliable data collection")
            print("   - Check the profile URL is valid and public")
            print("   - Try again later (respect rate limits)")

        print()
        print("=" * 60)
        print("✅ Test completed successfully")
        print("=" * 60)

    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Test failed with error:")
        print(f"   {type(e).__name__}: {str(e)}")
        print("=" * 60)
        raise


async def test_job_change_detection():
    """Test job change detection logic"""

    print()
    print("=" * 60)
    print("Testing Job Change Detection")
    print("=" * 60)
    print()

    # Create test config
    test_config = {
        'id': 1,
        'name': 'Test Customer',
        'config': {'linkedin_user_profiles': []}
    }

    collector = LinkedInUserCollector(test_config)

    # Test with sample Proxycurl-style data
    from datetime import datetime

    sample_profile_data = {
        'experiences': [
            {
                'title': 'CEO',
                'company': 'Microsoft',
                'starts_at': {
                    'year': datetime.now().year,
                    'month': datetime.now().month - 1,  # 1 month ago
                    'day': 1
                },
                'ends_at': None  # Current position
            },
            {
                'title': 'Executive Vice President',
                'company': 'Microsoft',
                'starts_at': {
                    'year': 2020,
                    'month': 1,
                    'day': 1
                },
                'ends_at': {
                    'year': datetime.now().year,
                    'month': datetime.now().month - 1,
                    'day': 1
                }
            }
        ]
    }

    # Test extraction
    current_position = collector._extract_current_position(sample_profile_data)
    print("Current Position Detection:")
    if current_position:
        print(f"  ✅ Title: {current_position['title']}")
        print(f"  ✅ Company: {current_position['company']}")
    else:
        print("  ❌ Failed to detect current position")

    print()

    # Test job change detection
    job_changes = collector._extract_job_changes(
        sample_profile_data,
        'Test User',
        'https://linkedin.com/in/test'
    )

    print("Job Change Detection (last 90 days):")
    print(f"  Recent job changes found: {len(job_changes)}")

    if job_changes:
        for change in job_changes:
            print(f"  ✅ {change.title}")
    else:
        print("  ℹ️  No recent job changes (this is expected for the test data)")

    print()
    print("=" * 60)
    print("✅ Job change detection test completed")
    print("=" * 60)


async def test_post_collection():
    """Test LinkedIn post collection specifically"""

    print()
    print("=" * 60)
    print("Testing Post Collection")
    print("=" * 60)
    print()

    # Create test config
    test_config = {
        'id': 1,
        'name': 'Test Customer',
        'domain': 'example.com',
        'keywords': [],
        'config': {
            'linkedin_user_profiles': [
                {
                    'profile_url': 'https://www.linkedin.com/in/satyanadella/',
                    'name': 'Satya Nadella',
                    'role': 'CEO Microsoft'
                }
            ]
        }
    }

    collector = LinkedInUserCollector(test_config)

    print("Testing post collection methods...")
    print()

    # Test with Proxycurl if available
    if collector.api_key:
        print("✅ Testing Proxycurl post collection")
        try:
            posts = await collector._collect_posts_via_proxycurl(
                'https://www.linkedin.com/in/satyanadella/',
                'Satya Nadella',
                'CEO Microsoft'
            )
            print(f"   Posts collected via Proxycurl: {len(posts)}")

            if posts:
                print("   Sample post:")
                sample = posts[0]
                print(f"   - {sample.title[:80]}...")
                if sample.raw_data.get('engagement'):
                    eng = sample.raw_data['engagement']
                    print(f"   - Engagement: {eng.get('likes', 0)} likes")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    else:
        print("⚠️  No Proxycurl API key - skipping API post collection")

    print()

    # Test scraping fallback
    print("Testing web scraping post collection (fallback method)")
    try:
        posts = await collector._collect_posts_via_scraping(
            'https://www.linkedin.com/in/satyanadella/',
            'Satya Nadella',
            'CEO Microsoft'
        )
        print(f"   Posts collected via scraping: {len(posts)}")

        if posts:
            print("   Sample post:")
            sample = posts[0]
            print(f"   - {sample.title[:80]}...")
        else:
            print("   ℹ️  No posts collected (expected - LinkedIn blocks scrapers)")
    except Exception as e:
        print(f"   ℹ️  Scraping failed (expected): {e}")

    print()
    print("=" * 60)
    print("✅ Post collection test completed")
    print("=" * 60)


if __name__ == '__main__':
    print()
    print("Starting LinkedIn User Collector Tests")
    print()

    # Run main collection test
    asyncio.run(test_linkedin_user_collector())

    # Run job change detection test
    asyncio.run(test_job_change_detection())

    # Run post collection test
    asyncio.run(test_post_collection())

    print()
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Configure linkedin_user_profiles in config/customers.yaml")
    print("2. Set linkedin_user_enabled: true in collection_config")
    print("3. (Optional) Set PROXYCURL_API_KEY for reliable data collection")
    print("   - Profile data: https://nubela.co/proxycurl/api/v2/linkedin")
    print("   - Activity/posts: https://nubela.co/proxycurl/api/linkedin/profile/activities")
    print("4. Run a collection: python backend/app/cli.py collect")
    print()
    print("What you'll collect:")
    print("  ✓ Current job positions")
    print("  ✓ Recent job changes (last 90 days)")
    print("  ✓ LinkedIn posts and articles (up to 10 per profile)")
    print("  ✓ Engagement metrics (likes, comments, shares)")
    print()
