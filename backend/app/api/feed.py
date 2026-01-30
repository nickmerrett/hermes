"""Intelligence feed API endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import Optional, List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import schemas
from app.models.database import IntelligenceItem, ProcessedIntelligence, CollectionStatus, User
from app.utils.smart_feed import (
    get_smart_feed_settings,
    calculate_effective_priority,
    should_include_item,
    apply_diversity_control
)
from app.utils.clustering import (
    get_clustering_settings,
    title_similarity,
    cosine_similarity,
    cluster_item
)
from app.core.vector_store import get_vector_store
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=schemas.FeedResponse)
async def get_feed(
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    min_priority: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum priority score"),
    search: Optional[str] = Query(None, description="Search in title and content"),
    clustered: bool = Query(True, description="Show clustered view (only primary items)"),
    limit: int = Query(50, ge=1, le=200, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get intelligence feed with filtering and pagination

    Returns items sorted by published_date (newest first)

    Smart Feed (clustered=True):
    - Shows only primary items (one per story cluster)
    - Applies intelligent filtering based on platform settings:
      * Priority thresholds (configurable minimum)
      * Category preferences (always show preferred categories)
      * Source preferences (always show preferred sources)
      * Recency boost (boost priority for recent items)
      * Diversity control (prevent single source domination)

    Full Feed (clustered=False):
    - Shows all items including duplicates from different sources
    - No smart filtering applied
    """
    # Build query
    query = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id,
        isouter=True  # Left join to include unprocessed items
    )

    # Apply filters
    filters = []

    # Always filter out ignored items
    filters.append(IntelligenceItem.ignored.is_(False))

    if customer_id:
        filters.append(IntelligenceItem.customer_id == customer_id)

    if source_type:
        filters.append(IntelligenceItem.source_type == source_type)

    if start_date:
        filters.append(IntelligenceItem.published_date >= start_date)

    if end_date:
        filters.append(IntelligenceItem.published_date <= end_date)

    if category:
        filters.append(ProcessedIntelligence.category == category)

    if sentiment:
        filters.append(ProcessedIntelligence.sentiment == sentiment)

    # Load smart feed configuration if using Smart Feed mode
    smart_config = None
    if clustered:
        smart_config = get_smart_feed_settings(db)
        logger.debug(f"Smart Feed enabled: {smart_config.get('enabled', True)}")
        logger.debug(f"Smart Feed min_priority: {smart_config.get('min_priority', 0.3)}")

        # Log enabled preferences
        cat_prefs = smart_config.get('category_preferences', {})
        enabled_cats = [k for k, v in cat_prefs.items() if v]
        logger.debug(f"Smart Feed preferred categories: {enabled_cats}")

        src_prefs = smart_config.get('source_preferences', {})
        enabled_srcs = [k for k, v in src_prefs.items() if v]
        logger.debug(f"Smart Feed preferred sources: {enabled_srcs}")

    # Apply explicit min_priority if provided
    # For Smart Feed, skip priority filter here - we'll apply smart filtering after query
    if min_priority is not None and not clustered:
        # Only apply to Full Feed if explicitly provided
        filters.append(ProcessedIntelligence.priority_score >= min_priority)

    if search:
        search_filter = f"%{search}%"
        filters.append(
            (IntelligenceItem.title.like(search_filter)) |
            (IntelligenceItem.content.like(search_filter))
        )

    # Clustering filter - only show primary items
    if clustered:
        filters.append(IntelligenceItem.is_cluster_primary.is_(True))

    # Exclude unrelated/advertisement items unless explicitly filtering for them
    if not category or category not in ('unrelated', 'advertisement'):
        filters.append(
            ~ProcessedIntelligence.category.in_(['unrelated', 'advertisement'])
            | ProcessedIntelligence.category.is_(None)  # Keep unprocessed items
        )

    if filters:
        query = query.filter(and_(*filters))

    # Fetch more items than requested to account for filtering
    # Smart Feed needs extra because smart filtering further reduces the count
    if clustered and smart_config and smart_config.get('enabled', True):
        fetch_limit = limit * 3
    else:
        fetch_limit = limit

    # Apply sorting and get items
    all_items = query.order_by(
        desc(IntelligenceItem.published_date)
    ).offset(offset).limit(fetch_limit).all()

    # Apply smart feed filtering if enabled
    if clustered and smart_config and smart_config.get('enabled', True):
        filtered_items = []

        # Get all processed intelligence data for these items
        item_ids = [item.id for item in all_items]
        processed_map = {}
        if item_ids:
            processed_list = db.query(ProcessedIntelligence).filter(
                ProcessedIntelligence.item_id.in_(item_ids)
            ).all()
            processed_map = {p.item_id: p for p in processed_list}

        for item in all_items:
            # Get processed intelligence data
            processed = processed_map.get(item.id)

            # Calculate effective priority with recency boost
            effective_priority = calculate_effective_priority(item, processed, smart_config)

            # Check if item should be included
            if should_include_item(item, processed, effective_priority, smart_config):
                filtered_items.append(item)

        logger.info(f"Smart Feed filtered {len(all_items)} -> {len(filtered_items)} items")

        # Apply diversity control
        filtered_items = apply_diversity_control(filtered_items, smart_config)

        # Limit to requested amount
        items = filtered_items[:limit]
        total = len(filtered_items)
    else:
        # Full Feed or Smart Feed disabled - use all items
        items = all_items
        total = query.count()

    return schemas.FeedResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        clustered=clustered
    )


@router.get("/collection-errors")
async def get_collection_errors(
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get collection errors and auth issues

    Returns collection statuses with errors or auth_required status from the last 24 hours.
    Used to show alert banners in the UI when collectors fail.
    Errors older than 24 hours are automatically filtered out.
    """
    # Only show errors from the last 24 hours
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)

    query = db.query(CollectionStatus).filter(
        and_(
            CollectionStatus.status.in_(['error', 'auth_required']),
            CollectionStatus.updated_at >= twenty_four_hours_ago,
            CollectionStatus.dismissed.is_(False)  # Don't show dismissed errors
        )
    )

    if customer_id:
        query = query.filter(CollectionStatus.customer_id == customer_id)

    errors = query.all()

    return {
        "errors": [
            {
                "id": e.id,  # Include ID for dismissing
                "customer_id": e.customer_id,
                "source_type": e.source_type,
                "status": e.status,
                "error_message": e.error_message,
                "error_count": e.error_count,
                "last_run": e.last_run.isoformat() if e.last_run else None,
                "last_success": e.last_success.isoformat() if e.last_success else None,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None
            }
            for e in errors
        ]
    }


@router.get("/{item_id}", response_model=schemas.IntelligenceItemDetail)
async def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed information about a specific intelligence item"""
    item = db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Intelligence item not found")

    return item


@router.get("/cluster/{cluster_id}")
async def get_cluster_items(
    cluster_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all items in a cluster

    Returns all intelligence items that belong to the same story cluster
    Useful for showing all sources covering the same story
    """
    items = db.query(IntelligenceItem).filter(
        IntelligenceItem.cluster_id == cluster_id
    ).order_by(
        # Show primary first, then by source tier priority
        desc(IntelligenceItem.is_cluster_primary),
        IntelligenceItem.source_tier
    ).all()

    if not items:
        raise HTTPException(status_code=404, detail="Cluster not found")

    return {
        "cluster_id": cluster_id,
        "item_count": len(items),
        "items": items
    }


@router.get("/debug/clustering")
async def debug_clustering(
    search: str = Query(..., description="Search term to find items (e.g., 'Rio Tinto')"),
    limit: int = Query(10, ge=1, le=20, description="Number of items to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Debug clustering - analyze why items may not have clustered together

    Returns:
    - Current clustering settings
    - Items matching the search term
    - Pairwise similarity analysis (embedding + title similarity)
    - Explanation of why items did/didn't cluster
    """
    # Get clustering settings
    settings = get_clustering_settings(db)
    emb_threshold = settings.get('similarity_threshold', 0.80)
    title_threshold = settings.get('title_similarity_threshold', 0.40)
    title_enabled = settings.get('title_similarity_enabled', True)

    # Search for items
    items = db.query(IntelligenceItem).filter(
        IntelligenceItem.title.ilike(f'%{search}%')
    ).order_by(desc(IntelligenceItem.collected_date)).limit(limit).all()

    if not items:
        return {
            "settings": settings,
            "search": search,
            "items": [],
            "analysis": [],
            "message": "No items found matching search term"
        }

    # Get vector store for embeddings
    vector_store = get_vector_store()

    # Build item info
    items_info = []
    items_with_embeddings = []
    embeddings = []

    for item in items:
        emb = vector_store.get_embedding(item.id)
        has_embedding = emb is not None

        item_info = {
            "id": item.id,
            "title": item.title,
            "source_type": item.source_type,
            "published_date": item.published_date.isoformat() if item.published_date else None,
            "cluster_id": item.cluster_id,
            "is_cluster_primary": item.is_cluster_primary,
            "cluster_member_count": item.cluster_member_count or 1,
            "has_embedding": has_embedding
        }
        items_info.append(item_info)

        if has_embedding:
            items_with_embeddings.append(item)
            embeddings.append(emb)

    # Pairwise analysis
    analysis = []
    for i in range(len(items_with_embeddings)):
        for j in range(i + 1, len(items_with_embeddings)):
            item_i = items_with_embeddings[i]
            item_j = items_with_embeddings[j]
            emb_i = embeddings[i]
            emb_j = embeddings[j]

            emb_sim = cosine_similarity(emb_i, emb_j)
            title_sim = title_similarity(item_i.title, item_j.title)

            emb_pass = emb_sim >= emb_threshold
            title_pass = title_sim >= title_threshold or not title_enabled

            would_cluster = emb_pass and title_pass
            same_cluster = (
                item_i.cluster_id and item_j.cluster_id and
                item_i.cluster_id == item_j.cluster_id
            )

            # Build reason
            if would_cluster:
                reason = "Would cluster (both thresholds met)"
            else:
                blockers = []
                if not emb_pass:
                    blockers.append(f"embedding {emb_sim:.3f} < {emb_threshold}")
                if title_enabled and not title_pass:
                    blockers.append(f"title {title_sim:.3f} < {title_threshold}")
                reason = f"Blocked: {', '.join(blockers)}"

            analysis.append({
                "item_a": {"id": item_i.id, "title": item_i.title[:80]},
                "item_b": {"id": item_j.id, "title": item_j.title[:80]},
                "embedding_similarity": round(emb_sim, 3),
                "embedding_passes": emb_pass,
                "title_similarity": round(title_sim, 3),
                "title_passes": title_pass,
                "would_cluster": would_cluster,
                "currently_same_cluster": same_cluster,
                "reason": reason
            })

    return {
        "settings": {
            "similarity_threshold": emb_threshold,
            "title_similarity_enabled": title_enabled,
            "title_similarity_threshold": title_threshold,
            "time_window_hours": settings.get('time_window_hours', 96),
            "max_cluster_size": settings.get('max_cluster_size', 25),
            "max_cluster_age_hours": settings.get('max_cluster_age_hours', 168)
        },
        "search": search,
        "items_found": len(items),
        "items_with_embeddings": len(items_with_embeddings),
        "items": items_info,
        "pairwise_analysis": analysis
    }


@router.post("/debug/recluster")
async def recluster_items(
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    search: Optional[str] = Query(None, description="Search term to find items to recluster"),
    item_ids: Optional[List[int]] = Query(None, description="Specific item IDs to recluster"),
    hours: int = Query(48, ge=1, le=168, description="Recluster items from the last N hours"),
    dry_run: bool = Query(False, description="If true, only show what would happen without making changes"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Re-cluster items using current clustering settings

    Use this after changing clustering settings to see if items cluster better.
    Items are processed oldest-first so newer items can cluster with older ones.

    Options:
    - customer_id: Filter to a specific customer
    - search: Recluster items matching a search term (e.g., "Rio Tinto")
    - item_ids: Recluster specific items by ID
    - hours: Recluster all items from the last N hours (default: 48)
    - dry_run: Preview what would happen without making changes
    """
    vector_store = get_vector_store()
    settings = get_clustering_settings(db)

    # Build base query
    query = db.query(IntelligenceItem)

    # Apply customer filter if provided
    if customer_id:
        query = query.filter(IntelligenceItem.customer_id == customer_id)

    # Find items to recluster
    if item_ids:
        items = query.filter(
            IntelligenceItem.id.in_(item_ids)
        ).order_by(IntelligenceItem.published_date.asc()).all()
    elif search:
        items = query.filter(
            IntelligenceItem.title.ilike(f'%{search}%')
        ).order_by(IntelligenceItem.published_date.asc()).all()
    else:
        # Default: last N hours
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        items = query.filter(
            IntelligenceItem.collected_date >= cutoff
        ).order_by(IntelligenceItem.published_date.asc()).all()

    if not items:
        return {
            "message": "No items found to recluster",
            "settings": settings
        }

    results = []
    reclustered = 0
    errors = 0

    for item in items:
        old_cluster = item.cluster_id
        old_primary = item.is_cluster_primary

        # Get embedding
        embedding = vector_store.get_embedding(item.id)
        if not embedding:
            results.append({
                "id": item.id,
                "title": item.title[:60],
                "status": "skipped",
                "reason": "no embedding"
            })
            continue

        if dry_run:
            # For dry run, just report current state
            results.append({
                "id": item.id,
                "title": item.title[:60],
                "status": "would_recluster",
                "current_cluster": old_cluster[:8] + "..." if old_cluster else None,
                "has_embedding": True
            })
            continue

        try:
            # Clear existing cluster assignment
            item.cluster_id = None
            item.is_cluster_primary = False
            item.cluster_member_count = None
            db.flush()

            # Re-cluster with current settings
            new_cluster = cluster_item(item, embedding, db)

            results.append({
                "id": item.id,
                "title": item.title[:60],
                "status": "reclustered",
                "old_cluster": old_cluster[:8] + "..." if old_cluster else None,
                "new_cluster": new_cluster[:8] + "..." if new_cluster else None,
                "changed": old_cluster != new_cluster,
                "is_primary": item.is_cluster_primary
            })
            reclustered += 1

        except Exception as e:
            logger.error(f"Error reclustering item {item.id}: {e}")
            db.rollback()
            results.append({
                "id": item.id,
                "title": item.title[:60],
                "status": "error",
                "error": str(e)
            })
            errors += 1

    # Update member counts for affected clusters
    if not dry_run:
        affected_clusters = set(r.get('new_cluster') for r in results if r.get('new_cluster'))
        for cluster_id_short in affected_clusters:
            if cluster_id_short:
                # Find full cluster ID and update counts
                cluster_items = db.query(IntelligenceItem).filter(
                    IntelligenceItem.cluster_id.like(f'{cluster_id_short.replace("...", "")}%')
                ).all()
                count = len(cluster_items)
                for ci in cluster_items:
                    ci.cluster_member_count = count
        db.commit()

    return {
        "dry_run": dry_run,
        "settings": {
            "similarity_threshold": settings.get('similarity_threshold'),
            "title_similarity_threshold": settings.get('title_similarity_threshold'),
            "title_similarity_enabled": settings.get('title_similarity_enabled')
        },
        "items_processed": len(items),
        "reclustered": reclustered,
        "errors": errors,
        "results": results
    }


@router.patch("/{item_id}/ignore")
async def ignore_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark an intelligence item as ignored (hide from feed)"""
    item = db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Intelligence item not found")

    item.ignored = True
    item.ignored_at = datetime.utcnow()
    db.commit()

    logger.info(f"Marked intelligence item {item_id} as ignored")
    return {"message": "Item ignored successfully", "item_id": item_id}


@router.patch("/{item_id}/unignore")
async def unignore_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Un-ignore an intelligence item (show in feed again)"""
    item = db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Intelligence item not found")

    item.ignored = False
    item.ignored_at = None
    db.commit()

    logger.info(f"Unmarked intelligence item {item_id} as ignored")
    return {"message": "Item un-ignored successfully", "item_id": item_id}


@router.patch("/collection-errors/{error_id}/dismiss")
async def dismiss_error(
    error_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Dismiss a collection error (hide from error banner)"""
    error = db.query(CollectionStatus).filter(CollectionStatus.id == error_id).first()

    if not error:
        raise HTTPException(status_code=404, detail="Collection error not found")

    error.dismissed = True
    error.dismissed_at = datetime.utcnow()
    db.commit()

    logger.info(f"Dismissed collection error {error_id} for customer {error.customer_id}, source {error.source_type}")
    return {"message": "Error dismissed successfully", "error_id": error_id}


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an intelligence item permanently (use ignore instead if you just want to hide it)"""
    item = db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Intelligence item not found")

    # Delete from vector store as well
    try:
        from app.core.vector_store import get_vector_store
        vector_store = get_vector_store()
        vector_store.delete_item(item_id)
    except Exception as e:
        logger.warning(f"Could not delete from vector store: {e}")

    db.delete(item)
    db.commit()

    logger.info(f"Deleted intelligence item {item_id}")
    return None
