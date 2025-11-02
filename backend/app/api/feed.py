"""Intelligence feed API endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.models import schemas
from app.models.database import IntelligenceItem, ProcessedIntelligence, CollectionStatus
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
    db: Session = Depends(get_db)
):
    """
    Get intelligence feed with filtering and pagination

    Returns items sorted by published_date (newest first)
    When clustered=True, only returns primary items (one per story cluster)
    Smart Feed (clustered=True) filters out low priority items by default (>= 0.3)
    """
    # Build query
    query = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id,
        isouter=True  # Left join to include unprocessed items
    )

    # Apply filters
    filters = []

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

    # Smart Feed: Default minimum priority threshold of 0.3 to filter low-priority items
    # Full Feed: No default threshold (show everything)
    # Users can override by explicitly passing min_priority parameter
    if min_priority is not None:
        filters.append(ProcessedIntelligence.priority_score >= min_priority)
    elif clustered:
        # Default threshold for Smart Feed only
        filters.append(ProcessedIntelligence.priority_score >= 0.3)

    if search:
        search_filter = f"%{search}%"
        filters.append(
            (IntelligenceItem.title.like(search_filter)) |
            (IntelligenceItem.content.like(search_filter))
        )

    # Clustering filter - only show primary items
    if clustered:
        filters.append(IntelligenceItem.is_cluster_primary == True)

    if filters:
        query = query.filter(and_(*filters))

    # Get total count
    total = query.count()

    # Apply sorting and pagination
    items = query.order_by(
        desc(IntelligenceItem.published_date)
    ).offset(offset).limit(limit).all()

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
    db: Session = Depends(get_db)
):
    """
    Get collection errors and auth issues

    Returns all collection statuses with errors or auth_required status.
    Used to show alert banners in the UI when collectors fail.
    """
    query = db.query(CollectionStatus).filter(
        CollectionStatus.status.in_(['error', 'auth_required'])
    )

    if customer_id:
        query = query.filter(CollectionStatus.customer_id == customer_id)

    errors = query.all()

    return {
        "errors": [
            {
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
async def get_item(item_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific intelligence item"""
    item = db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Intelligence item not found")

    return item


@router.get("/cluster/{cluster_id}")
async def get_cluster_items(cluster_id: str, db: Session = Depends(get_db)):
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


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: int, db: Session = Depends(get_db)):
    """Delete an intelligence item"""
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
