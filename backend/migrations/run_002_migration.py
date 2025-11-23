#!/usr/bin/env python3
"""Run migration 002 - Add pain_points_opportunities field"""

import sys
import os
import sqlite3

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings

def run_migration():
    """Run the migration to add pain_points_opportunities field"""

    db_path = settings.database_path

    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False

    print("=" * 80)
    print("MIGRATION 002: Add pain_points_opportunities field")
    print("=" * 80)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if column already exists
        cursor.execute("PRAGMA table_info(processed_intelligence)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'pain_points_opportunities' in columns:
            print("\n✓ Column 'pain_points_opportunities' already exists!")
            print("  Migration already applied. Skipping.")
            conn.close()
            return True

        print("\n📋 Adding column 'pain_points_opportunities'...")

        # Read and execute migration SQL
        migration_file = os.path.join(
            os.path.dirname(__file__),
            '002_add_pain_points_opportunities.sql'
        )

        with open(migration_file, 'r') as f:
            sql = f.read()

        # Execute migration
        cursor.executescript(sql)
        conn.commit()

        # Verify
        cursor.execute("PRAGMA table_info(processed_intelligence)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'pain_points_opportunities' in columns:
            print("✓ Column added successfully!")

            # Count updated records
            cursor.execute("SELECT COUNT(*) FROM processed_intelligence WHERE pain_points_opportunities IS NOT NULL")
            count = cursor.fetchone()[0]
            print(f"✓ Initialized {count} existing records with default empty values")

            conn.close()

            print("\n" + "=" * 80)
            print("MIGRATION COMPLETE")
            print("=" * 80)
            print("\n✓ Database schema updated successfully!")
            print("  Restart your application to use the new field.")

            return True
        else:
            print("❌ Failed to add column!")
            conn.close()
            return False

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
