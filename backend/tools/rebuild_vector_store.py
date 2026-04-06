#!/usr/bin/env python3
"""Rebuild vector store with correct distance metric"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.core.vector_store import get_vector_store
from app.models.database import IntelligenceItem
from app.utils.text_cleaning import clean_text_for_embedding
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def rebuild_vector_store():
    """Rebuild the vector store from scratch with correct distance metric"""

    logger.info("Starting vector store rebuild...")

    # Reset vector store (deletes and recreates collection with new settings)
    vector_store = get_vector_store()
    logger.info(f"Current item count: {vector_store.get_item_count()}")

    logger.info("Resetting vector store...")
    vector_store.reset()

    # Get all intelligence items from database
    db = SessionLocal()
    try:
        items = db.query(IntelligenceItem).all()
        logger.info(f"Found {len(items)} items in database")

        if not items:
            logger.warning("No items found in database")
            return

        # Re-add all items to vector store
        item_ids = []
        texts = []
        metadatas = []

        for item in items:
            text_for_embedding = clean_text_for_embedding(item.title, item.content)

            item_ids.append(item.id)
            texts.append(text_for_embedding)
            metadatas.append({
                'customer_id': item.customer_id,
                'source_type': item.source_type,
                'published_timestamp': int(
                    (item.published_date or item.collected_date or datetime.utcnow()).timestamp()
                ),
            })

        # Add in batches
        batch_size = 100
        for i in range(0, len(item_ids), batch_size):
            batch_ids = item_ids[i:i+batch_size]
            batch_texts = texts[i:i+batch_size]
            batch_metadatas = metadatas[i:i+batch_size]

            vector_store.add_items_batch(batch_ids, batch_texts, batch_metadatas)
            logger.info(f"Added batch {i//batch_size + 1}/{(len(item_ids) + batch_size - 1)//batch_size}")

        logger.info(f"✓ Vector store rebuilt successfully with {vector_store.get_item_count()} items")

        # Test search
        results = vector_store.search("test query", n_results=5)
        logger.info(f"Test search returned {len(results['ids'][0])} results")
        if results['ids'][0]:
            logger.info(f"Top result similarity: {results['similarities'][0][0]:.3f}")

    finally:
        db.close()

if __name__ == "__main__":
    rebuild_vector_store()
