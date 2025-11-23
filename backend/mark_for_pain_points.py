#!/usr/bin/env python3
"""Mark all items with empty pain_points for reprocessing"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.database import ProcessedIntelligence
from datetime import datetime

db = SessionLocal()

try:
    # Find items with empty or NULL pain points
    items = db.query(ProcessedIntelligence).filter(
        (ProcessedIntelligence.pain_points_opportunities == None) |
        (ProcessedIntelligence.pain_points_opportunities == '') |
        (ProcessedIntelligence.pain_points_opportunities == '{"pain_points": [], "opportunities": []}')
    ).all()

    print(f"Found {len(items)} items with empty pain_points_opportunities")

    if len(items) == 0:
        print("Nothing to do!")
        sys.exit(0)

    # Ask for confirmation
    response = input(f"\nMark {len(items)} items for reprocessing? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        sys.exit(0)

    # Mark them all for reprocessing
    count = 0
    for item in items:
        item.needs_reprocessing = True
        item.last_processing_attempt = datetime.utcnow()
        count += 1

        # Commit in batches of 100
        if count % 100 == 0:
            db.commit()
            print(f"Marked {count} items...")

    # Final commit
    db.commit()

    print(f"\n✓ Successfully marked {count} items for reprocessing")
    print(f"Run this to reprocess them:")
    print(f"  curl -X POST 'http://localhost:8000/api/jobs/reprocess-incomplete?max_items=100'")

except Exception as e:
    print(f"Error: {e}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()
