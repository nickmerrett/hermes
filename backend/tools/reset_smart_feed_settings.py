#!/usr/bin/env python3
"""Reset smart feed settings to use new schema"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import get_db
from app.models.database import PlatformSettings

def reset_smart_feed_settings():
    """Delete smart_feed_config to force reload with new defaults"""
    db = next(get_db())

    try:
        # Find and delete the old smart_feed_config
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'smart_feed_config'
        ).first()

        if setting:
            print("Found existing smart_feed_config, deleting...")
            db.delete(setting)
            db.commit()
            print("✓ Smart feed settings reset successfully!")
            print("The new defaults will be loaded next time you access Platform Settings.")
        else:
            print("No smart_feed_config found in database (already using defaults)")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    reset_smart_feed_settings()
