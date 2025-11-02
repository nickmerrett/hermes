#!/usr/bin/env python3
"""
Add collection_status table to track collector errors and auth issues
"""
import sys
sys.path.insert(0, 'backend')

from app.core.database import engine
from sqlalchemy import text

def migrate():
    """Add collection_status table"""

    print("="*60)
    print("Adding collection_status table")
    print("="*60)

    with engine.connect() as conn:
        # Check if table exists
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='collection_status'"
        ))

        if result.fetchone():
            print("\n⚠️  collection_status table already exists")
            return

        print("\n🔄 Creating collection_status table...")

        conn.execute(text("""
            CREATE TABLE collection_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                source_type VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL,
                last_run DATETIME,
                last_success DATETIME,
                error_message TEXT,
                error_count INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(customer_id) REFERENCES customers (id),
                UNIQUE(customer_id, source_type)
            )
        """))

        conn.execute(text("""
            CREATE INDEX ix_collection_status_customer_id ON collection_status (customer_id)
        """))

        conn.execute(text("""
            CREATE INDEX ix_collection_status_source_type ON collection_status (source_type)
        """))

        conn.execute(text("""
            CREATE INDEX ix_collection_status_status ON collection_status (status)
        """))

        conn.execute(text("""
            CREATE INDEX ix_collection_status_last_run ON collection_status (last_run)
        """))

        conn.commit()

        print("✅ collection_status table created successfully!")
        print("\nNext steps:")
        print("1. Restart the backend to use the new table")
        print("2. Collection errors will now be tracked automatically")
        print("3. Frontend will show alerts for auth/collection failures")


if __name__ == "__main__":
    migrate()
