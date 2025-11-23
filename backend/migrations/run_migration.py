#!/usr/bin/env python3
"""
Run database migration to allow same URL for multiple customers
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

def main():
    print("=" * 80)
    print("DATABASE MIGRATION: Fix URL Uniqueness")
    print("=" * 80)
    print()

    # Paths
    db_path = '/app/data/hermes.db'
    backup_path = f'/app/data/hermes.db.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    migration_path = '/app/migrations/001_fix_url_uniqueness.sql'

    # Step 1: Backup
    print("Step 1: Creating backup...")
    try:
        shutil.copy(db_path, backup_path)
        print(f"✓ Backup created: {backup_path}")
    except Exception as e:
        print(f"✗ Error creating backup: {e}")
        return
    print()

    # Step 2: Read migration SQL
    print("Step 2: Reading migration SQL...")
    try:
        migration_sql = Path(migration_path).read_text()
        print(f"✓ Migration loaded from: {migration_path}")
    except Exception as e:
        print(f"✗ Error reading migration: {e}")
        return
    print()

    # Step 3: Execute migration
    print("Step 3: Executing migration...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Execute the migration script
        conn.executescript(migration_sql)
        print("✓ Migration executed successfully")
    except Exception as e:
        print(f"✗ Error executing migration: {e}")
        print("Rolling back changes...")
        conn.rollback()
        conn.close()
        # Restore backup
        shutil.copy(backup_path, db_path)
        print("✓ Database restored from backup")
        return
    print()

    # Step 4: Verify
    print("Step 4: Verifying migration...")
    try:
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='intelligence_items'")
        table_schema = cursor.fetchone()

        if table_schema and 'UNIQUE(customer_id, url)' in table_schema[0]:
            print("✓ Verified: Composite unique constraint (customer_id, url) exists")
        else:
            print("⚠ Warning: Could not verify constraint in schema")

        # Count items
        cursor.execute("SELECT COUNT(*) FROM intelligence_items")
        item_count = cursor.fetchone()[0]
        print(f"✓ Table contains {item_count} items")

    except Exception as e:
        print(f"✗ Error verifying migration: {e}")
    finally:
        conn.close()

    print()
    print("=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print()
    print(f"Backup location: {backup_path}")
    print()
    print("Next steps:")
    print("1. Exit this pod")
    print("2. Restart deployment: kubectl rollout restart deployment hermes-backend")
    print("3. Test collection: The same article can now be collected for multiple customers")
    print()

if __name__ == "__main__":
    main()
