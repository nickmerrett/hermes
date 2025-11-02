#!/usr/bin/env python3
"""Verify collection_status table exists and check its structure"""
import sys
sys.path.insert(0, 'backend')

from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Check if table exists
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='collection_status'"
    ))

    table = result.fetchone()
    if table:
        print("✅ collection_status table EXISTS")

        # Show table structure
        result = conn.execute(text("PRAGMA table_info(collection_status)"))
        print("\nTable structure:")
        for row in result:
            print(f"  {row[1]}: {row[2]}")

        # Count rows
        result = conn.execute(text("SELECT COUNT(*) FROM collection_status"))
        count = result.fetchone()[0]
        print(f"\nRows in table: {count}")

        if count > 0:
            # Show sample data
            result = conn.execute(text("SELECT * FROM collection_status LIMIT 3"))
            print("\nSample rows:")
            for row in result:
                print(f"  {row}")
    else:
        print("❌ collection_status table DOES NOT EXIST")
        print("\nRun: python3 migrate_collection_status.py")
