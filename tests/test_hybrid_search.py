#!/usr/bin/env python3
"""
Test script for hybrid search functionality
"""
import sys
sys.path.insert(0, 'backend')

import requests

API_URL = "http://localhost:8000/api"

def test_search(query, customer_id=1):
    """Test search with a query"""
    print(f"\n{'='*60}")
    print(f"Testing: '{query}'")
    print('='*60)

    response = requests.post(
        f"{API_URL}/search",
        json={
            "query": query,
            "customer_id": customer_id,
            "limit": 10,
            "min_similarity": 0.3
        }
    )

    if response.status_code == 200:
        data = response.json()
        results = data.get('results', [])

        if results:
            print(f"\n✅ Found {len(results)} results:")
            for idx, result in enumerate(results[:5], 1):
                item = result['item']
                similarity = result['similarity']
                print(f"\n{idx}. [{similarity:.2f}] {item['title'][:80]}")
                print(f"   Source: {item['source_type']} | Published: {item['published_date'][:10]}")
                # Show snippet where query appears
                content_preview = item.get('content', '')[:200] if item.get('content') else ''
                if content_preview:
                    print(f"   Preview: {content_preview}...")
        else:
            print("\n❌ No results found")
    else:
        print(f"\n❌ Error: {response.status_code}")
        print(response.text)

def main():
    print("="*60)
    print("Hybrid Search Test Suite")
    print("="*60)

    # Test 1: Partial name - "Nuno"
    test_search("Nuno")

    # Test 2: Partial name - "Arvind"
    test_search("Arvind")

    # Test 3: Full name - "Nuno Matos"
    test_search("Nuno Matos")

    # Test 4: Full name with title - "Arvind Krishna CEO"
    test_search("Arvind Krishna CEO")

    # Test 5: Concept search - should still work
    test_search("artificial intelligence")

    # Test 6: Company name
    test_search("ANZ Bank")

    print("\n" + "="*60)
    print("Test Complete")
    print("="*60)

if __name__ == "__main__":
    main()
