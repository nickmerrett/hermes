#!/usr/bin/env python3
"""
Recreate database with CASCADE DELETE foreign key constraints.

This script is needed for SQLite because it doesn't support altering foreign key constraints.
It will backup the current database and create a new one with proper CASCADE DELETE constraints.

WARNING: This will recreate all tables. Use with caution!
"""

import os
import shutil
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, Base
from app.config.settings import settings


def main():
    """Recreate database with CASCADE DELETE constraints"""

    db_path = settings.database_path

    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Database does not exist at {db_path}")
        print("Creating new database with CASCADE DELETE constraints...")
        Base.metadata.create_all(bind=engine)
        print("✓ Database created successfully!")
        return

    # Backup current database
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"

    print(f"Backing up database to: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print("✓ Backup created")

    # Drop and recreate all tables
    print("\nRecreating database with CASCADE DELETE constraints...")
    print("WARNING: This will delete all data in the database!")
    response = input("Are you sure you want to continue? (yes/no): ")

    if response.lower() != 'yes':
        print("Aborted. Database backup saved at:", backup_path)
        return

    # Drop all tables
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("✓ Tables dropped")

    # Create all tables with new schema (includes CASCADE DELETE)
    print("Creating tables with CASCADE DELETE constraints...")
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created")

    print("\n✓ Database successfully recreated with CASCADE DELETE constraints!")
    print(f"Original database backed up to: {backup_path}")
    print("\nNote: All data has been cleared. You may need to:")
    print("  1. Re-import customers from config/customers.yaml")
    print("  2. Run data collection to repopulate intelligence items")


if __name__ == "__main__":
    main()
