#!/usr/bin/env python3
"""Check LinkedIn post dates in the database"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.database import IntelligenceItem
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_linkedin_dates():
    """Check LinkedIn post dates"""

    db = SessionLocal()
    try:
        # Get most recent LinkedIn posts
        posts = db.query(IntelligenceItem).filter(
            IntelligenceItem.source_type == 'linkedin_user'
        ).order_by(IntelligenceItem.id.desc()).limit(5).all()

        if not posts:
            logger.info("No LinkedIn posts found in database")
            return

        logger.info(f"\nFound {len(posts)} LinkedIn posts:")
        logger.info(f"Current time: {datetime.now()}\n")

        for post in posts:
            logger.info(f"ID: {post.id}")
            logger.info(f"Title: {post.title[:80]}...")
            logger.info(f"Published Date: {post.published_date}")
            logger.info(f"Collected Date: {post.collected_date}")

            # Calculate age
            if post.published_date:
                age = datetime.now() - post.published_date
                days = age.days
                hours = age.seconds // 3600
                logger.info(f"Age: {days} days, {hours} hours ago")

            logger.info("-" * 80)

    except Exception as e:
        logger.error(f"Error checking dates: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_linkedin_dates()
