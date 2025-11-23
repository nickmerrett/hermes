#!/usr/bin/env python3
"""
Verify timezone handling in the database and API responses
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone
import sqlite3

def main():
    print("=" * 80)
    print("TIMEZONE VERIFICATION")
    print("=" * 80)
    print()

    # Check system timezone
    print("System Information:")
    print("-" * 80)
    print(f"  datetime.now():           {datetime.now()}")
    print(f"  datetime.utcnow():        {datetime.utcnow()}")
    try:
        print(f"  datetime.now(timezone.utc): {datetime.now(timezone.utc)}")
    except:
        pass

    try:
        import time
        offset_hours = -time.timezone / 3600
        print(f"  System timezone offset:   UTC{offset_hours:+.1f} hours")
    except:
        pass
    print()

    # Check database dates
    print("Database Date Samples:")
    print("-" * 80)

    db_path = '/app/data/hermes.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id,
                title,
                published_date,
                collected_date,
                customer_id
            FROM intelligence_items
            ORDER BY collected_date DESC
            LIMIT 5
        """)

        items = cursor.fetchall()

        if not items:
            print("No items found in database")
            return

        now_utc = datetime.utcnow()

        for i, (item_id, title, published_date, collected_date, customer_id) in enumerate(items, 1):
            print(f"\nItem {i} (ID: {item_id}, Customer: {customer_id}):")
            print(f"  Title: {title[:60]}...")
            print(f"  Published Date (DB): {published_date}")
            print(f"  Collected Date (DB): {collected_date}")

            if published_date:
                try:
                    # Parse the date
                    pub_dt = datetime.fromisoformat(published_date.replace('Z', '+00:00') if 'Z' in published_date else published_date)

                    # Calculate age
                    if pub_dt.tzinfo is None:
                        # Naive datetime - assume UTC
                        age = now_utc - pub_dt
                    else:
                        # Timezone-aware datetime
                        age = datetime.now(timezone.utc) - pub_dt

                    hours_ago = age.total_seconds() / 3600
                    days_ago = age.days

                    if days_ago > 0:
                        print(f"  Age: {days_ago} days, {int(hours_ago % 24)} hours ago")
                    else:
                        print(f"  Age: {int(hours_ago)} hours ago")

                except Exception as e:
                    print(f"  Age: Error calculating - {e}")

    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        conn.close()

    print()
    print()
    print("API Response Check:")
    print("-" * 80)
    print("To verify API serialization, run this from your machine:")
    print()
    print("  curl -s http://localhost:8000/api/feed?limit=1 | jq '.items[0].published_date'")
    print()
    print("Expected output format:")
    print("  ✓ CORRECT: \"2025-11-11T12:34:56Z\"       (has 'Z' suffix)")
    print("  ✗ WRONG:   \"2025-11-11T12:34:56\"        (missing 'Z' suffix)")
    print()
    print("If the 'Z' is missing, the timezone fix hasn't been applied yet.")
    print("Restart the pod after code changes to apply the fix.")
    print()

    print("=" * 80)
    print("COMMON ISSUES")
    print("=" * 80)
    print()
    print("1. Dates missing 'Z' suffix in API:")
    print("   → Restart pod to apply CustomJSONResponse fix")
    print()
    print("2. Dates stored without timezone in DB:")
    print("   → This is normal for SQLite. The 'Z' suffix is added during serialization.")
    print()
    print("3. Still seeing wrong times in browser:")
    print("   → Hard refresh browser (Ctrl+Shift+R)")
    print("   → Check browser console for errors")
    print("   → Verify API response has 'Z' suffix")
    print()

if __name__ == "__main__":
    main()
