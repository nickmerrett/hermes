"""Test domain blacklist functionality"""

from app.collectors.base import BaseCollector

def test_blacklist():
    """Test the domain blacklist functionality"""

    # Test configuration with blacklist enabled
    blacklist_config = {
        'enabled': True,
        'domains': [
            'yahoo.com',
            'msn.com',
            'aol.com',
            'bing.com',
            'pinterest.com',
            'tumblr.com'
        ]
    }

    print("Testing Domain Blacklist Functionality")
    print("=" * 50)

    # Test 1: URLs that should be blocked
    blocked_urls = [
        'https://www.yahoo.com/news/article',
        'https://finance.yahoo.com/quote/AAPL',
        'http://msn.com/article',
        'https://www.MSN.COM/news',  # Test case insensitivity
        'https://pinterest.com/pin/123456',
        'https://www.bing.com/search?q=test'
    ]

    print("\n1. Testing URLs that SHOULD be blocked:")
    for url in blocked_urls:
        is_blocked = BaseCollector.is_url_blacklisted(url, blacklist_config)
        status = "✓ BLOCKED" if is_blocked else "✗ FAILED - should be blocked"
        print(f"  {status}: {url}")

    # Test 2: URLs that should NOT be blocked
    allowed_urls = [
        'https://techcrunch.com/article',
        'https://www.reuters.com/business',
        'https://www.bloomberg.com/news',
        'https://news.ycombinator.com/item?id=123',
        None  # Test None URL
    ]

    print("\n2. Testing URLs that should NOT be blocked:")
    for url in allowed_urls:
        is_blocked = BaseCollector.is_url_blacklisted(url, blacklist_config)
        status = "✓ ALLOWED" if not is_blocked else "✗ FAILED - should be allowed"
        url_display = url if url else "None"
        print(f"  {status}: {url_display}")

    # Test 3: Blacklist disabled
    disabled_config = {
        'enabled': False,
        'domains': blacklist_config['domains']
    }

    print("\n3. Testing with blacklist DISABLED:")
    test_url = 'https://yahoo.com/article'
    is_blocked = BaseCollector.is_url_blacklisted(test_url, disabled_config)
    status = "✓ ALLOWED" if not is_blocked else "✗ FAILED - should be allowed when disabled"
    print(f"  {status}: {test_url}")

    # Test 4: Empty blacklist config
    empty_config = {}

    print("\n4. Testing with empty blacklist config:")
    is_blocked = BaseCollector.is_url_blacklisted(test_url, empty_config)
    status = "✓ ALLOWED" if not is_blocked else "✗ FAILED - should be allowed with empty config"
    print(f"  {status}: {test_url}")

    print("\n" + "=" * 50)
    print("Domain Blacklist Tests Complete!")
    print("\nNext: Test with actual collection by:")
    print("1. Ensure domain_blacklist is configured in PlatformSettings")
    print("2. Run a collection job")
    print("3. Check logs for 'Skipping blacklisted URL' messages")
    print("4. Verify no items from blacklisted domains are stored")


if __name__ == "__main__":
    test_blacklist()
