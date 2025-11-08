"""
Migration: Add ignored and dismissed fields

Adds:
- intelligence_items.ignored (BOOLEAN, default FALSE)
- intelligence_items.ignored_at (DATETIME, nullable)
- collection_status.dismissed (BOOLEAN, default FALSE)
- collection_status.dismissed_at (DATETIME, nullable)
"""

import sqlite3
import os
from pathlib import Path


def get_db_path():
    """Get database path"""
    db_path = os.environ.get('DATABASE_PATH')
    if not db_path:
        # Default to data directory
        data_dir = Path(__file__).parent.parent / 'data'
        data_dir.mkdir(exist_ok=True)
        db_path = str(data_dir / 'hermes.db')
    return db_path


def migrate():
    """Run migration"""
    db_path = get_db_path()
    print(f"Running migration on database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(intelligence_items)")
        columns = [col[1] for col in cursor.fetchall()]

        # Add ignored fields to intelligence_items if not exists
        if 'ignored' not in columns:
            print("Adding 'ignored' column to intelligence_items...")
            cursor.execute("""
                ALTER TABLE intelligence_items
                ADD COLUMN ignored BOOLEAN DEFAULT 0
            """)

        if 'ignored_at' not in columns:
            print("Adding 'ignored_at' column to intelligence_items...")
            cursor.execute("""
                ALTER TABLE intelligence_items
                ADD COLUMN ignored_at DATETIME
            """)

        # Check collection_status table
        cursor.execute("PRAGMA table_info(collection_status)")
        columns = [col[1] for col in cursor.fetchall()]

        # Add dismissed fields to collection_status if not exists
        if 'dismissed' not in columns:
            print("Adding 'dismissed' column to collection_status...")
            cursor.execute("""
                ALTER TABLE collection_status
                ADD COLUMN dismissed BOOLEAN DEFAULT 0
            """)

        if 'dismissed_at' not in columns:
            print("Adding 'dismissed_at' column to collection_status...")
            cursor.execute("""
                ALTER TABLE collection_status
                ADD COLUMN dismissed_at DATETIME
            """)

        # Create indexes for better query performance
        print("Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_intelligence_items_ignored
            ON intelligence_items(ignored)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_collection_status_dismissed
            ON collection_status(dismissed)
        """)

        conn.commit()
        print("✓ Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        conn.close()


def rollback():
    """Rollback migration - Note: SQLite doesn't support DROP COLUMN easily"""
    print("⚠️  Warning: SQLite doesn't support DROP COLUMN natively.")
    print("To rollback this migration, you would need to recreate the tables.")
    print("This is not implemented to avoid data loss.")
    print("If you need to rollback, restore from a backup.")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback()
    else:
        migrate()
