"""Story clustering utilities for intelligent deduplication"""

import uuid
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import numpy as np

from app.models.database import IntelligenceItem, PlatformSettings
from app.core.vector_store import get_vector_store
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

# LLM clients (lazy loaded)
_anthropic_client = None
_openai_client = None


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
            # Merge with defaults for any missing keys
            defaults = get_default_clustering_settings()
            merged = {**defaults, **setting.value}
            return merged
    except Exception as e:
        logger.warning(f"Error loading clustering settings from database: {e}")

    return get_default_clustering_settings()


def get_default_clustering_settings() -> Dict:
    """Return default clustering settings"""
    return {
        'enabled': True,
        'similarity_threshold': 0.80,  # Raised from 0.50
        'time_window_hours': 96,
        # Title similarity settings
        'title_similarity_enabled': True,
        'title_similarity_threshold': 0.40,  # Titles must be at least 40% similar
        'max_cluster_size': 25,  # Don't add to clusters larger than this
        'max_cluster_age_hours': 168,  # Don't add to clusters older than 7 days
        # LLM tiebreaker settings (uses ai_model_cheap/ai_provider_cheap from settings)
        'llm_tiebreaker_enabled': False,  # Use LLM when embedding/title disagree
        'llm_tiebreaker_embedding_min': 0.50,  # Only use LLM if embedding >= this
    }


def _get_llm_client(provider: str):
    """Get or create LLM client for tiebreaker"""
    global _anthropic_client, _openai_client

    if provider == 'anthropic':
        if _anthropic_client is None:
            from anthropic import Anthropic
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured for LLM tiebreaker")
            _anthropic_client = Anthropic(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_api_base_url,
                timeout=60.0  # Add 60 second timeout to prevent hanging
            )
        return _anthropic_client, 'anthropic'

    elif provider == 'openai':
        if _openai_client is None:
            from openai import OpenAI
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured for LLM tiebreaker")
            _openai_client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout=60.0  # Add 60 second timeout to prevent hanging
            )
        return _openai_client, 'openai'

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def llm_similarity_check(
    title_a: str,
    title_b: str,
    embedding_similarity: float,
    title_similarity: float,
    db: Session = None
) -> Tuple[bool, str]:
    """
    Use LLM to determine if two headlines are about the same news story.

    This is a tiebreaker for when embedding similarity is high but title
    similarity (Jaccard) is low - common when articles use different wording.

    Uses settings.ai_provider_cheap and settings.ai_model_cheap (same as entity extraction).
    If db is provided, reads model override from platform_settings ai_config.

    Args:
        title_a: First headline
        title_b: Second headline
        embedding_similarity: Cosine similarity of embeddings (0.0-1.0)
        title_similarity: Jaccard similarity of titles (0.0-1.0)
        db: Database session (optional, used to read model from platform settings)

    Returns:
        Tuple of (is_same_story: bool, reasoning: str)
    """
    provider = settings.ai_provider_cheap
    model = settings.ai_model_cheap

    # Check for model override in platform settings (same as ai_processor.py)
    if db:
        try:
            ai_config_row = db.query(PlatformSettings).filter(
                PlatformSettings.key == 'ai_config'
            ).first()
            if ai_config_row and isinstance(ai_config_row.value, dict):
                config = ai_config_row.value
                model = config.get('model_cheap', model)
                logger.debug(f"LLM tiebreaker using model from ai_config: {model}")
        except Exception as e:
            logger.warning(f"Could not read ai_config from database: {e}")

    try:
        client, client_type = _get_llm_client(provider)

        prompt = f"""You are analyzing news headlines to determine if they cover the same story.

Context:
- Embedding similarity: {embedding_similarity:.0%} (semantic similarity of full content)
- Title word overlap: {title_similarity:.0%} (Jaccard coefficient)

The embedding similarity is high but title word overlap is low. This often happens when:
- Different outlets use different words for the same event (buy/acquire, deal/merger)
- Entity name variations (Chalco/Chinalco, CBA/Companhia Brasileira de Alumínio)
- Different focus angles on the same underlying news

Headline A: {title_a}

Headline B: {title_b}

Are these two headlines about the SAME news story/event?

Answer with ONLY "YES" or "NO" on the first line, then a brief reason on the second line."""

        if client_type == 'anthropic':
            response = client.messages.create(
                model=model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.content[0].text.strip()
        else:  # openai
            response = client.chat.completions.create(
                model=model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.choices[0].message.content.strip()

        # Parse response
        lines = response_text.split('\n')
        answer = lines[0].strip().upper()
        reasoning = lines[1].strip() if len(lines) > 1 else ""

        is_same = answer.startswith('YES')

        logger.info(
            f"LLM tiebreaker: {'SAME' if is_same else 'DIFFERENT'} story - "
            f"'{title_a[:40]}...' vs '{title_b[:40]}...' - {reasoning}"
        )

        return is_same, reasoning

    except Exception as e:
        logger.error(f"LLM tiebreaker error: {e}")
        # On error, fall back to not clustering (safer)
        return False, f"Error: {e}"


# Source tier rankings (lower = higher priority)
SOURCE_TIERS = {
    # Tier 1: Official sources (highest priority)
    'press_release': 1,
    'pressrelease': 1,
    'linkedin': 1,  # Legacy - Executive LinkedIn posts
    'linkedin_company': 1,  # Official company posts
    'linkedin_user': 1,  # Executive posts
    'web_scrape': 1,  # Company newsrooms

    # Tier 2: Primary news sources (original reporting)
    'news_api': 2,  # Depends on source, but generally good
    'rss': 2,
    'australian_news': 2,

    # Tier 3: Secondary sources
    'stock': 3,  # Yahoo Finance news (often aggregated)
    'yahoo_finance_news': 3,

    # Tier 4: Aggregators
    'google_news': 4,

    # Tier 5: Community/Social
    'reddit': 5,
    'twitter': 5,
    'youtube': 5,
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
    item_title: str,
    customer_id: int,
    published_date: datetime,
    db: Session,
    similarity_threshold: float = 0.80,
    time_window_hours: int = 96,
    title_similarity_enabled: bool = True,
    title_similarity_threshold: float = 0.40,
    max_cluster_size: int = 25,
    max_cluster_age_hours: int = 168,
    llm_tiebreaker_enabled: bool = False,
    llm_tiebreaker_embedding_min: float = 0.50
) -> Optional[str]:
    """
    Find existing cluster for a new item based on embedding similarity

    Args:
        item_embedding: Vector embedding of the new item
        item_title: Title of the new item (for title similarity check)
        customer_id: Customer ID for filtering
        published_date: When item was published
        db: Database session
        similarity_threshold: Min embedding similarity to consider same story (0.0-1.0)
        time_window_hours: How far back to look for similar items
        title_similarity_enabled: Whether to also check title similarity
        title_similarity_threshold: Min title similarity if enabled (0.0-1.0)
        max_cluster_size: Don't add to clusters larger than this
        max_cluster_age_hours: Don't add to clusters older than this
        llm_tiebreaker_enabled: Use LLM when embedding passes but title fails
        llm_tiebreaker_embedding_min: Min embedding similarity to invoke LLM

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

        # Track cluster info to avoid repeated lookups
        cluster_info_cache = {}

        # Get embeddings for recent items from vector store
        best_similarity = 0.0
        best_title_sim = 0.0
        best_cluster_id = None

        for existing_item in recent_items:
            try:
                cluster_id = existing_item.cluster_id

                # Check cluster constraints (size and age)
                if cluster_id not in cluster_info_cache:
                    cluster_info_cache[cluster_id] = get_cluster_info(cluster_id, db)

                cluster_info = cluster_info_cache[cluster_id]

                # Skip if cluster is too large
                if max_cluster_size > 0 and cluster_info['size'] >= max_cluster_size:
                    logger.debug(f"Skipping cluster {cluster_id}: size {cluster_info['size']} >= max {max_cluster_size}")
                    continue

                # Skip if cluster is too old
                if max_cluster_age_hours > 0 and cluster_info['oldest_date']:
                    cluster_age = published_date - cluster_info['oldest_date']
                    if cluster_age.total_seconds() / 3600 > max_cluster_age_hours:
                        logger.debug(f"Skipping cluster {cluster_id}: age {cluster_age.total_seconds()/3600:.1f}h > max {max_cluster_age_hours}h")
                        continue

                # Get embedding from vector store
                existing_embedding = vector_store.get_embedding(existing_item.id)

                if existing_embedding is None:
                    continue

                # Calculate cosine similarity
                embedding_sim = cosine_similarity(item_embedding, existing_embedding)

                if embedding_sim < similarity_threshold:
                    continue

                # Check title similarity if enabled
                if title_similarity_enabled:
                    t_sim = title_similarity(item_title, existing_item.title)
                    if t_sim < title_similarity_threshold:
                        # Title similarity failed - try LLM tiebreaker if enabled
                        if llm_tiebreaker_enabled and embedding_sim >= llm_tiebreaker_embedding_min:
                            logger.info(
                                f"Title mismatch (emb={embedding_sim:.3f}, title={t_sim:.3f}) - "
                                f"invoking LLM tiebreaker"
                            )
                            is_same, reason = llm_similarity_check(
                                title_a=item_title,
                                title_b=existing_item.title,
                                embedding_similarity=embedding_sim,
                                title_similarity=t_sim,
                                db=db
                            )
                            if not is_same:
                                logger.debug(
                                    f"LLM confirmed different stories: "
                                    f"'{item_title[:50]}...' vs '{existing_item.title[:50]}...' - {reason}"
                                )
                                continue
                            else:
                                logger.info(
                                    f"LLM confirmed same story despite title mismatch: "
                                    f"'{item_title[:50]}...' vs '{existing_item.title[:50]}...' - {reason}"
                                )
                                # LLM says it's the same - allow clustering
                        else:
                            logger.debug(
                                f"Rejected cluster match: embedding sim {embedding_sim:.3f} OK but "
                                f"title sim {t_sim:.3f} < {title_similarity_threshold} "
                                f"('{item_title[:50]}...' vs '{existing_item.title[:50]}...')"
                            )
                            continue
                else:
                    t_sim = 1.0  # Not checking titles

                # This is a valid match - check if it's the best one
                if embedding_sim > best_similarity:
                    best_similarity = embedding_sim
                    best_title_sim = t_sim
                    best_cluster_id = cluster_id

            except Exception as e:
                logger.warning(f"Error comparing with item {existing_item.id}: {e}")
                continue

        if best_cluster_id:
            logger.info(
                f"Found similar cluster {best_cluster_id} with embedding similarity {best_similarity:.3f}"
                + (f", title similarity {best_title_sim:.3f}" if title_similarity_enabled else "")
            )

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


def title_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity between two titles using token overlap (Jaccard-like)

    This is a simple but effective check to ensure titles are about the same event,
    not just the same company/topic.

    Args:
        title1: First title
        title2: Second title

    Returns:
        Similarity score 0.0-1.0
    """
    if not title1 or not title2:
        return 0.0

    # Normalize: lowercase, remove punctuation, split into words
    import re

    def tokenize(text: str) -> set:
        # Remove punctuation and lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # Split and filter short words (articles, prepositions)
        words = set(w for w in text.split() if len(w) > 2)
        return words

    tokens1 = tokenize(title1)
    tokens2 = tokenize(title2)

    if not tokens1 or not tokens2:
        return 0.0

    # Jaccard similarity: intersection / union
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    if union == 0:
        return 0.0

    return intersection / union


def get_cluster_info(cluster_id: str, db: Session) -> Dict:
    """
    Get information about a cluster

    Args:
        cluster_id: The cluster ID
        db: Database session

    Returns:
        Dict with cluster info (size, oldest_date, newest_date, primary_title)
    """
    try:
        items = db.query(IntelligenceItem).filter(
            IntelligenceItem.cluster_id == cluster_id
        ).all()

        if not items:
            return {'size': 0, 'oldest_date': None, 'newest_date': None, 'primary_title': None}

        dates = [i.published_date or i.collected_date for i in items]
        primary = next((i for i in items if i.is_cluster_primary), items[0])

        return {
            'size': len(items),
            'oldest_date': min(dates) if dates else None,
            'newest_date': max(dates) if dates else None,
            'primary_title': primary.title if primary else None
        }
    except Exception as e:
        logger.error(f"Error getting cluster info: {e}")
        return {'size': 0, 'oldest_date': None, 'newest_date': None, 'primary_title': None}


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
            IntelligenceItem.is_cluster_primary.is_(True)
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
            similarity_threshold = clustering_settings.get('similarity_threshold', 0.80)

        time_window_hours = clustering_settings.get('time_window_hours', 96)

        # New settings with defaults
        title_similarity_enabled = clustering_settings.get('title_similarity_enabled', True)
        title_similarity_threshold = clustering_settings.get('title_similarity_threshold', 0.40)
        max_cluster_size = clustering_settings.get('max_cluster_size', 25)
        max_cluster_age_hours = clustering_settings.get('max_cluster_age_hours', 168)

        # LLM tiebreaker settings
        llm_tiebreaker_enabled = clustering_settings.get('llm_tiebreaker_enabled', False)
        llm_tiebreaker_embedding_min = clustering_settings.get('llm_tiebreaker_embedding_min', 0.50)

        # LinkedIn posts are individual perspectives, don't cluster them
        # Always give them their own cluster
        if item.source_type in ['linkedin', 'linkedin_user']:
            logger.info(f"Creating solo cluster for LinkedIn item {item.id}")
            return create_new_cluster(item, db)

        # Try to find similar cluster
        cluster_id = find_similar_cluster(
            item_embedding=item_embedding,
            item_title=item.title or '',
            customer_id=item.customer_id,
            published_date=item.published_date or item.collected_date,
            db=db,
            similarity_threshold=similarity_threshold,
            time_window_hours=time_window_hours,
            title_similarity_enabled=title_similarity_enabled,
            title_similarity_threshold=title_similarity_threshold,
            max_cluster_size=max_cluster_size,
            max_cluster_age_hours=max_cluster_age_hours,
            llm_tiebreaker_enabled=llm_tiebreaker_enabled,
            llm_tiebreaker_embedding_min=llm_tiebreaker_embedding_min
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
