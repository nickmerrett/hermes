#!/usr/bin/env python3
"""
Check if the URL uniqueness migration has been applied
"""

import sqlite3

def main():
    print("=" * 80)
    print("CHECKING MIGRATION STATUS")
    print("=" * 80)
    print()

    db_path = '/app/data/hermes.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get the schema for intelligence_items table
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='intelligence_items'")
        result = cursor.fetchone()

        if not result:
            print("✗ intelligence_items table not found!")
            return

        schema = result[0]
        print("Current schema:")
        print("-" * 80)
        print(schema)
        print("-" * 80)
        print()

        # Check for old constraint (globally unique URL)
        if 'UNIQUE(url)' in schema or 'url VARCHAR(2048) UNIQUE' in schema.upper():
            print("❌ OLD SCHEMA DETECTED")
            print("   URL is globally unique (prevents same article for multiple customers)")
            print()
            print("   Migration status: NOT APPLIED")
            print()
            print("   Action needed: Run migration to fix this")
            migrated = False

        # Check for new constraint (per-customer unique URL)
        elif 'UNIQUE(customer_id, url)' in schema or 'UNIQUE (customer_id, url)' in schema:
            print("✅ NEW SCHEMA DETECTED")
            print("   URL is unique per customer (allows same article for multiple customers)")
            print()
            print("   Migration status: ALREADY APPLIED")
            print()
            print("   No action needed!")
            migrated = True

        else:
            print("⚠️  UNKNOWN SCHEMA")
            print("   Could not determine if migration was applied")
            print()
            print("   Please check schema manually")
            migrated = None

        # Test with actual data
        print()
        print("Testing with database data:")
        print("-" * 80)

        # Count total items
        cursor.execute("SELECT COUNT(*) FROM intelligence_items")
        total = cursor.fetchone()[0]
        print(f"Total articles: {total}")

        # Count unique URLs
        cursor.execute("SELECT COUNT(DISTINCT url) FROM intelligence_items")
        unique_urls = cursor.fetchone()[0]
        print(f"Unique URLs: {unique_urls}")

        # Check for duplicate URLs across customers
        cursor.execute("""
            SELECT url, COUNT(DISTINCT customer_id) as customer_count, COUNT(*) as total_count
            FROM intelligence_items
            WHERE url IS NOT NULL
            GROUP BY url
            HAVING COUNT(DISTINCT customer_id) > 1
            LIMIT 5
        """)
        duplicates = cursor.fetchall()

        if duplicates:
            print(f"\n✓ Found {len(duplicates)} URLs shared across customers (sample):")
            for url, cust_count, total_count in duplicates:
                print(f"  • {url[:60]}...")
                print(f"    Used by {cust_count} customers, {total_count} total articles")
        else:
            print("\nNo URLs currently shared across customers")

        # If old schema but has duplicates, something is wrong
        if not migrated and duplicates:
            print("\n⚠️  WARNING: Old schema but duplicate URLs exist!")
            print("   This shouldn't be possible. Database may be inconsistent.")

    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        conn.close()

    print()
    print("=" * 80)

if __name__ == "__main__":
    main()
