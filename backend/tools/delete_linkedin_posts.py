#!/usr/bin/env python3
"""Delete all LinkedIn posts from the database"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_linkedin_posts():
    """Delete all LinkedIn posts from database"""

    db = SessionLocal()
    try:
        # Count posts before deletion
        count = db.query(IntelligenceItem).filter(
            IntelligenceItem.source_type == 'linkedin_user'
        ).count()

        logger.info(f"Found {count} LinkedIn posts to delete")

        if count == 0:
            logger.info("No LinkedIn posts found")
            return

        # Delete all LinkedIn posts
        deleted = db.query(IntelligenceItem).filter(
            IntelligenceItem.source_type == 'linkedin_user'
        ).delete()

        db.commit()

        logger.info(f"✓ Successfully deleted {deleted} LinkedIn posts")

    except Exception as e:
        logger.error(f"Error deleting LinkedIn posts: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    delete_linkedin_posts()
