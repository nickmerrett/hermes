#!/usr/bin/env python3
"""
Test script for deduplication utilities
"""
import sys
sys.path.insert(0, 'backend')

from app.utils.deduplication import normalize_url, is_similar_title, calculate_title_similarity


def test_url_normalization():
    """Test URL normalization"""
    print("="*60)
    print("Testing URL Normalization")
    print("="*60)

    test_cases = [
        # Tracking parameters
        (
            "https://techcrunch.com/article?utm_source=twitter&utm_medium=social",
            "https://techcrunch.com/article"
        ),
        # AMP versions
        (
            "https://www.google.com/amp/s/news.com/article.amp",
            "https://google.com/s/news.com/article"
        ),
        # www. removal
        (
            "https://www.reuters.com/technology/article",
            "https://reuters.com/technology/article"
        ),
        # Multiple tracking params
        (
            "https://example.com/story?fbclid=123&gclid=456&ref=homepage",
            "https://example.com/story"
        ),
        # Trailing slash
        (
            "https://news.com/article/",
            "https://news.com/article"
        ),
        # Case normalization
        (
            "https://NEWS.COM/Article",
            "https://news.com/Article"
        ),
    ]

    for original, expected in test_cases:
        result = normalize_url(original)
        status = "✅" if result == expected else "❌"
        print(f"\n{status} Original: {original}")
        print(f"   Expected: {expected}")
        print(f"   Got:      {result}")
        if result != expected:
            print(f"   MISMATCH!")


def test_title_similarity():
    """Test title similarity detection"""
    print("\n" + "="*60)
    print("Testing Title Similarity")
    print("="*60)

    test_cases = [
        # Exact match
        (
            "Company X Raises $50M Series B",
            "Company X Raises $50M Series B",
            1.0,
            True
        ),
        # Very similar (minor wording change)
        (
            "Company X Raises $50M Series B",
            "Company X Secures $50M in Series B Funding",
            0.70,  # Approximate expected similarity
            True
        ),
        # Similar but different amounts
        (
            "Startup Raises $10M",
            "Startup Raises $20M",
            0.90,
            True
        ),
        # Different stories
        (
            "Tesla Announces New Model",
            "Apple Releases iPhone 15",
            0.30,
            False
        ),
        # Same story, different phrasing
        (
            "Biden Signs Climate Bill Into Law",
            "President Biden Signs Historic Climate Legislation",
            0.60,
            True
        ),
        # Syndicated content (usually identical or very similar)
        (
            "[Reuters] Tech Giant Announces Layoffs",
            "[Bloomberg] Tech Giant Announces Layoffs",
            0.85,
            True
        ),
    ]

    threshold = 0.85

    for title1, title2, expected_min_similarity, should_match in test_cases:
        similarity = calculate_title_similarity(title1, title2)
        is_match = is_similar_title(title1, title2, threshold=threshold)

        status = "✅" if is_match == should_match else "❌"
        print(f"\n{status} Similarity: {similarity:.2f} (threshold: {threshold})")
        print(f"   Title 1: {title1}")
        print(f"   Title 2: {title2}")
        print(f"   Match:   {is_match} (expected: {should_match})")


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "="*60)
    print("Testing Edge Cases")
    print("="*60)

    # Empty strings
    print("\nEmpty string tests:")
    print(f"  normalize_url(''): '{normalize_url('')}'")
    print(f"  normalize_url(None): '{normalize_url(None)}'")
    print(f"  is_similar_title('', 'test'): {is_similar_title('', 'test')}")
    print(f"  is_similar_title('test', ''): {is_similar_title('test', '')}")

    # Invalid URLs
    print("\nInvalid URL tests:")
    print(f"  normalize_url('not a url'): '{normalize_url('not a url')}'")

    # Case sensitivity
    print("\nCase sensitivity tests:")
    similarity = calculate_title_similarity("BREAKING NEWS", "breaking news")
    print(f"  'BREAKING NEWS' vs 'breaking news': {similarity:.2f}")


if __name__ == "__main__":
    test_url_normalization()
    test_title_similarity()
    test_edge_cases()

    print("\n" + "="*60)
    print("Deduplication Tests Complete")
    print("="*60)
