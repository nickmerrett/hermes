#!/usr/bin/env python3
"""Delete LinkedIn profile items from the database"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_linkedin_profiles():
    """Delete all LinkedIn profile items from database"""

    db = SessionLocal()
    try:
        # Count profile items before deletion
        count = db.query(IntelligenceItem).filter(
            IntelligenceItem.source_type == 'linkedin_user',
            IntelligenceItem.title.like('[LinkedIn Profile]%')
        ).count()

        logger.info(f"Found {count} LinkedIn profile items to delete")

        if count == 0:
            logger.info("No LinkedIn profile items found")
            return

        # Delete all LinkedIn profile items
        deleted = db.query(IntelligenceItem).filter(
            IntelligenceItem.source_type == 'linkedin_user',
            IntelligenceItem.title.like('[LinkedIn Profile]%')
        ).delete(synchronize_session=False)

        db.commit()

        logger.info(f"✓ Successfully deleted {deleted} LinkedIn profile items")

        # Show remaining LinkedIn posts
        remaining = db.query(IntelligenceItem).filter(
            IntelligenceItem.source_type == 'linkedin_user'
        ).count()
        logger.info(f"Remaining LinkedIn posts: {remaining}")

    except Exception as e:
        logger.error(f"Error deleting LinkedIn profile items: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    delete_linkedin_profiles()
