"""Semantic search API endpoints"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_user, check_customer_access, get_accessible_customer_ids
from app.core.vector_store import get_vector_store
from app.models import schemas
from app.models.database import IntelligenceItem, User
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=schemas.SearchResponse)
async def semantic_search(
    query: schemas.SemanticSearchQuery,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Perform hybrid search across intelligence items

    Combines keyword matching (for names, exact phrases) with semantic search (for concepts)
    """
    try:
        # Enforce customer access
        if query.customer_id:
            check_customer_access(query.customer_id, current_user, db)

        accessible_ids = get_accessible_customer_ids(current_user, db)

        vector_store = get_vector_store()

        # Step 1: Keyword/Text Search
        # Good for: proper names, exact phrases, specific terms
        keyword_results = {}

        # Build keyword search query
        base_query = db.query(IntelligenceItem)
        if query.customer_id:
            base_query = base_query.filter(IntelligenceItem.customer_id == query.customer_id)
        elif accessible_ids is not None:
            base_query = base_query.filter(IntelligenceItem.customer_id.in_(accessible_ids))

        # Search in title and content
        search_pattern = f"%{query.query}%"
        keyword_items = base_query.filter(
            (IntelligenceItem.title.ilike(search_pattern)) |
            (IntelligenceItem.content.ilike(search_pattern))
        ).limit(query.limit * 2).all()  # Get more to ensure we have enough after merging

        # Score keyword matches higher (1.0 for exact matches in title, 0.9 for content)
        for item in keyword_items:
            if query.query.lower() in item.title.lower():
                keyword_results[item.id] = 1.0
            elif item.content and query.query.lower() in item.content.lower():
                keyword_results[item.id] = 0.9

        # Step 2: Semantic/Vector Search
        # Good for: concepts, topics, related ideas
        where = None
        if query.customer_id:
            where = {"customer_id": query.customer_id}
        elif accessible_ids is not None:
            where = {"customer_id": {"$in": accessible_ids}}

        results = vector_store.search(
            query=query.query,
            n_results=query.limit * 2,  # Get more to ensure we have enough after merging
            where=where
        )

        semantic_results = {}
        if results['ids'] and len(results['ids'][0]) > 0:
            item_ids = [int(id) for id in results['ids'][0]]
            similarities = results['similarities'][0]

            for item_id, similarity in zip(item_ids, similarities):
                if similarity >= query.min_similarity:
                    semantic_results[item_id] = similarity

        # Step 3: Merge and rank results
        # Combine scores from both methods, prioritizing keyword matches
        merged_scores = {}

        # Add keyword matches with their scores
        for item_id, score in keyword_results.items():
            merged_scores[item_id] = score

        # Add semantic matches, boosting if also found via keyword
        for item_id, score in semantic_results.items():
            if item_id in merged_scores:
                # Item found in both - boost the score
                merged_scores[item_id] = max(merged_scores[item_id], score * 1.1)
            else:
                merged_scores[item_id] = score

        # Sort by score descending and take top N
        sorted_items = sorted(merged_scores.items(), key=lambda x: x[1], reverse=True)[:query.limit]

        # Get full items from database
        search_results = []
        for item_id, similarity in sorted_items:
            item = db.query(IntelligenceItem).filter(
                IntelligenceItem.id == item_id
            ).first()

            if item:
                search_results.append(
                    schemas.SearchResult(
                        item=item,
                        similarity=similarity
                    )
                )

        return schemas.SearchResponse(
            results=search_results,
            query=query.query
        )

    except Exception as e:
        logger.error(f"Error performing hybrid search: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/diagnostics")
async def vector_store_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get vector store diagnostics to help debug search issues
    """
    try:
        vector_store = get_vector_store()

        # Get vector store item count
        vector_count = vector_store.get_item_count()

        # Get database item count
        db_count = db.query(IntelligenceItem).count()

        # Get recent items (last 24 hours)
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_count = db.query(IntelligenceItem).filter(
            IntelligenceItem.collected_date >= last_24h
        ).count()

        # Get sample of recent items
        recent_items = db.query(IntelligenceItem).filter(
            IntelligenceItem.collected_date >= last_24h
        ).order_by(IntelligenceItem.collected_date.desc()).limit(5).all()

        recent_samples = [
            {
                "id": item.id,
                "title": item.title[:60],
                "source_type": item.source_type,
                "collected_date": item.collected_date.isoformat()
            }
            for item in recent_items
        ]

        return {
            "vector_store_count": vector_count,
            "database_count": db_count,
            "recent_24h_count": recent_count,
            "in_sync": vector_count == db_count,
            "missing_from_vector_store": max(0, db_count - vector_count),
            "recent_samples": recent_samples
        }

    except Exception as e:
        logger.error(f"Error getting diagnostics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
