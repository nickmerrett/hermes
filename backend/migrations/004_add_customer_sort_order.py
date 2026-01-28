"""
Migration: Add sort_order to customers

Adds:
- customers.sort_order (INTEGER, default 0)
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
        # Check if column already exists
        cursor.execute("PRAGMA table_info(customers)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'sort_order' not in columns:
            print("Adding 'sort_order' column to customers...")
            cursor.execute("""
                ALTER TABLE customers
                ADD COLUMN sort_order INTEGER DEFAULT 0
            """)
        else:
            print("'sort_order' column already exists, skipping.")

        conn.commit()
        print("✓ Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        conn.close()


def rollback():
    """Rollback migration"""
    print("⚠️  Warning: SQLite doesn't support DROP COLUMN natively.")
    print("To rollback this migration, you would need to recreate the table.")
    print("If you need to rollback, restore from a backup.")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback()
    else:
        migrate()
