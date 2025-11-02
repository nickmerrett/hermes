"""Story clustering utilities for intelligent deduplication"""

import uuid
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import numpy as np

from app.models.database import IntelligenceItem, PlatformSettings
from app.core.vector_store import get_vector_store
import logging

logger = logging.getLogger(__name__)


def get_clustering_settings(db: Session) -> Dict:
    """
    Get clustering configuration from database

    Returns default settings if not configured in database
    """
    try:
        setting = db.query(PlatformSettings).filter(
            PlatformSettings.key == 'clustering_config'
        ).first()

        if setting and setting.value:
            return setting.value
    except Exception as e:
        logger.warning(f"Error loading clustering settings from database: {e}")

    # Return defaults if not configured
    return {
        'enabled': True,
        'similarity_threshold': 0.50,
        'time_window_hours': 96
    }


# Source tier rankings (lower = higher priority)
SOURCE_TIERS = {
    # Tier 1: Official sources (highest priority)
    'press_release': 1,
    'linkedin': 1,  # Executive LinkedIn posts
    'web_scrape': 1,  # Company newsrooms

    # Tier 2: Primary news sources (original reporting)
    'news_api': 2,  # Depends on source, but generally good
    'rss': 2,

    # Tier 3: Secondary sources
    'stock': 3,  # Yahoo Finance news (often aggregated)

    # Tier 4: Aggregators
    'google_news': 4,

    # Tier 5: Community/Social
    'reddit': 5,
    'twitter': 5,
    'hackernews': 5,
}


def get_source_tier(source_type: str) -> str:
    """
    Map source_type to tier name

    Args:
        source_type: The source type string

    Returns:
        Tier name: official/primary/secondary/aggregator/social
    """
    tier_num = SOURCE_TIERS.get(source_type, 3)

    if tier_num == 1:
        return 'official'
    elif tier_num == 2:
        return 'primary'
    elif tier_num == 3:
        return 'secondary'
    elif tier_num == 4:
        return 'aggregator'
    else:
        return 'social'


def get_source_priority(source_type: str) -> int:
    """Get numeric priority for source type (lower = higher priority)"""
    return SOURCE_TIERS.get(source_type, 3)


def find_similar_cluster(
    item_embedding: List[float],
    customer_id: int,
    published_date: datetime,
    db: Session,
    similarity_threshold: float = 0.50,
    time_window_hours: int = 96
) -> Optional[str]:
    """
    Find existing cluster for a new item based on embedding similarity

    Args:
        item_embedding: Vector embedding of the new item
        customer_id: Customer ID for filtering
        published_date: When item was published
        db: Database session
        similarity_threshold: Min similarity to consider same story (0.0-1.0)
        time_window_hours: How far back to look for similar items

    Returns:
        cluster_id if similar cluster found, None otherwise
    """
    try:
        # Define time window
        time_cutoff = published_date - timedelta(hours=time_window_hours)

        # Get recent items from same customer
        # Exclude LinkedIn items - they don't cluster with other sources
        recent_items = db.query(IntelligenceItem).filter(
            IntelligenceItem.customer_id == customer_id,
            IntelligenceItem.published_date >= time_cutoff,
            IntelligenceItem.published_date <= published_date + timedelta(hours=2),  # Allow slight future dates
            IntelligenceItem.cluster_id.isnot(None),  # Only items already in clusters
            ~IntelligenceItem.source_type.in_(['linkedin', 'linkedin_user'])  # Exclude LinkedIn
        ).all()

        if not recent_items:
            return None

        # Get vector store
        vector_store = get_vector_store()

        # Get embeddings for recent items from vector store
        best_similarity = 0.0
        best_cluster_id = None

        for existing_item in recent_items:
            try:
                # Get embedding from vector store
                existing_embedding = vector_store.get_embedding(existing_item.id)

                if existing_embedding is None:
                    continue

                # Calculate cosine similarity
                similarity = cosine_similarity(item_embedding, existing_embedding)

                if similarity >= similarity_threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_cluster_id = existing_item.cluster_id

            except Exception as e:
                logger.warning(f"Error comparing with item {existing_item.id}: {e}")
                continue

        if best_cluster_id:
            logger.info(f"Found similar cluster {best_cluster_id} with similarity {best_similarity:.3f}")

        return best_cluster_id

    except Exception as e:
        logger.error(f"Error finding similar cluster: {e}")
        return None


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    try:
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        return float(dot_product / (norm_v1 * norm_v2))
    except Exception as e:
        logger.error(f"Error calculating cosine similarity: {e}")
        return 0.0


def assign_to_cluster(
    item: IntelligenceItem,
    cluster_id: str,
    db: Session
) -> None:
    """
    Assign an item to an existing cluster and update cluster metadata

    Args:
        item: The item to assign
        cluster_id: The cluster to assign to
        db: Database session
    """
    try:
        # Set cluster fields
        item.cluster_id = cluster_id
        item.source_tier = get_source_tier(item.source_type)

        # Check if this should be the new primary (higher priority source)
        current_primary = db.query(IntelligenceItem).filter(
            IntelligenceItem.cluster_id == cluster_id,
            IntelligenceItem.is_cluster_primary == True
        ).first()

        if current_primary:
            # Compare source priorities
            item_priority = get_source_priority(item.source_type)
            current_priority = get_source_priority(current_primary.source_type)

            if item_priority < current_priority:
                # New item is higher priority - make it primary
                current_primary.is_cluster_primary = False
                item.is_cluster_primary = True
                logger.info(f"Updated cluster {cluster_id} primary from {current_primary.source_type} to {item.source_type}")
            else:
                item.is_cluster_primary = False
        else:
            # No primary yet, make this one primary
            item.is_cluster_primary = True

        # Update member counts for all items in cluster
        cluster_items = db.query(IntelligenceItem).filter(
            IntelligenceItem.cluster_id == cluster_id
        ).all()

        member_count = len(cluster_items) + 1  # +1 for the new item
        for cluster_item in cluster_items:
            cluster_item.cluster_member_count = member_count
        item.cluster_member_count = member_count

        db.commit()
        logger.info(f"Assigned item {item.id} to cluster {cluster_id} (now {member_count} members)")

    except Exception as e:
        logger.error(f"Error assigning item to cluster: {e}")
        db.rollback()
        raise


def create_new_cluster(item: IntelligenceItem, db: Session) -> str:
    """
    Create a new cluster for an item

    Args:
        item: The item to create a cluster for
        db: Database session

    Returns:
        The new cluster_id
    """
    try:
        cluster_id = str(uuid.uuid4())

        item.cluster_id = cluster_id
        item.is_cluster_primary = True  # First item is always primary
        item.source_tier = get_source_tier(item.source_type)
        item.cluster_member_count = 1

        db.commit()
        logger.info(f"Created new cluster {cluster_id} for item {item.id}")

        return cluster_id

    except Exception as e:
        logger.error(f"Error creating new cluster: {e}")
        db.rollback()
        raise


def cluster_item(
    item: IntelligenceItem,
    item_embedding: List[float],
    db: Session,
    similarity_threshold: Optional[float] = None
) -> str:
    """
    Main clustering function - finds or creates cluster for an item

    Args:
        item: The IntelligenceItem to cluster
        item_embedding: Vector embedding of the item
        db: Database session
        similarity_threshold: Min similarity for clustering (if None, loads from settings)

    Returns:
        cluster_id that was assigned
    """
    try:
        # Load clustering settings from database
        clustering_settings = get_clustering_settings(db)

        # Check if clustering is enabled
        if not clustering_settings.get('enabled', True):
            logger.info(f"Clustering disabled - creating solo cluster for item {item.id}")
            return create_new_cluster(item, db)

        # Use provided threshold or get from settings
        if similarity_threshold is None:
            similarity_threshold = clustering_settings.get('similarity_threshold', 0.50)

        time_window_hours = clustering_settings.get('time_window_hours', 96)

        # LinkedIn posts are individual perspectives, don't cluster them
        # Always give them their own cluster
        if item.source_type in ['linkedin', 'linkedin_user']:
            logger.info(f"Creating solo cluster for LinkedIn item {item.id}")
            return create_new_cluster(item, db)

        # Try to find similar cluster
        cluster_id = find_similar_cluster(
            item_embedding=item_embedding,
            customer_id=item.customer_id,
            published_date=item.published_date or item.collected_date,
            db=db,
            similarity_threshold=similarity_threshold,
            time_window_hours=time_window_hours
        )

        if cluster_id:
            # Assign to existing cluster
            assign_to_cluster(item, cluster_id, db)
        else:
            # Create new cluster
            cluster_id = create_new_cluster(item, db)

        return cluster_id

    except Exception as e:
        logger.error(f"Error clustering item {item.id}: {e}")
        # On error, create solo cluster so item isn't orphaned
        return create_new_cluster(item, db)
