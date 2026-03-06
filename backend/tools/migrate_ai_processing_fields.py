#!/usr/bin/env python3
"""Add AI processing status tracking fields to database"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def column_exists(db, table_name, column_name):
    """Check if a column exists in a table"""
    result = db.execute(text(f"PRAGMA table_info({table_name})"))
    columns = [row[1] for row in result.fetchall()]
    return column_name in columns

def migrate_database():
    """Add new columns for AI processing status tracking"""

    logger.info("Starting database migration: AI processing status fields")

    db = SessionLocal()
    try:
        # Check and add columns to processed_intelligence table
        columns_to_add = [
            ("needs_reprocessing", "BOOLEAN DEFAULT 0"),
            ("processing_attempts", "INTEGER DEFAULT 0"),
            ("last_processing_error", "TEXT"),
            ("last_processing_attempt", "TIMESTAMP")
        ]

        logger.info("Migrating processed_intelligence table...")
        for col_name, col_def in columns_to_add:
            if not column_exists(db, "processed_intelligence", col_name):
                logger.info(f"  Adding column: {col_name}")
                db.execute(text(f"ALTER TABLE processed_intelligence ADD COLUMN {col_name} {col_def}"))
                db.commit()
                logger.info(f"  ✓ Added {col_name}")
            else:
                logger.info(f"  ⊙ Column {col_name} already exists, skipping")

        # Add index on needs_reprocessing
        logger.info("Creating index on needs_reprocessing...")
        try:
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_processed_intelligence_needs_reprocessing
                ON processed_intelligence(needs_reprocessing)
            """))
            db.commit()
            logger.info("✓ Index created")
        except Exception as e:
            logger.info(f"⊙ Index may already exist: {e}")

        # Check and add column to collection_jobs table
        logger.info("Migrating collection_jobs table...")
        if not column_exists(db, "collection_jobs", "items_failed_processing"):
            logger.info("  Adding column: items_failed_processing")
            db.execute(text("ALTER TABLE collection_jobs ADD COLUMN items_failed_processing INTEGER DEFAULT 0"))
            db.commit()
            logger.info("  ✓ Added items_failed_processing")
        else:
            logger.info("  ⊙ Column items_failed_processing already exists, skipping")

        logger.info("✓ All migrations completed successfully!")

        # Verify the columns were added using SQLite PRAGMA
        logger.info("\nVerifying columns...")

        # Verify processed_intelligence columns
        result = db.execute(text("PRAGMA table_info(processed_intelligence)"))
        all_columns = {row[1]: row[2] for row in result.fetchall()}

        expected_cols = ['needs_reprocessing', 'processing_attempts', 'last_processing_error', 'last_processing_attempt']
        found_cols = [col for col in expected_cols if col in all_columns]

        if len(found_cols) == 4:
            logger.info("✓ All processed_intelligence columns verified:")
            for col_name in found_cols:
                logger.info(f"  - {col_name} ({all_columns[col_name]})")
        else:
            logger.warning(f"⚠ Expected 4 columns, found {len(found_cols)}: {found_cols}")

        # Verify collection_jobs column
        result = db.execute(text("PRAGMA table_info(collection_jobs)"))
        all_columns = {row[1]: row[2] for row in result.fetchall()}

        if 'items_failed_processing' in all_columns:
            logger.info("✓ collection_jobs.items_failed_processing column verified")
        else:
            logger.warning("⚠ collection_jobs.items_failed_processing column not found")

        logger.info("\n✓ Migration completed successfully!")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_database()
