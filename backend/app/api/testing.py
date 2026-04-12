"""Testing API endpoints for prompt evaluation"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.database import IntelligenceItem, ProcessedIntelligence, Customer

router = APIRouter(dependencies=[Depends(get_current_user)])


class CustomerInfo(BaseModel):
    """Customer information for testing"""
    id: int
    name: str
    keywords: List[str]
    competitors: List[str]


class ProcessedInfo(BaseModel):
    """Processed intelligence baseline"""
    summary: str | None
    category: str | None
    sentiment: str | None
    priority_score: float
    entities: dict | None
    tags: List[str] | None
    pain_points_opportunities: dict | None


class TestItem(BaseModel):
    """Single test item with full context"""
    item_id: int
    title: str
    content: str | None
    source_type: str
    customer: CustomerInfo
    baseline: ProcessedInfo


class TestDataResponse(BaseModel):
    """Response for test data endpoint"""
    items: List[TestItem]
    total: int


@router.get("/test-data", response_model=TestDataResponse)
def get_test_data(
    limit: int = Query(10, ge=1, le=100, description="Number of test items"),
    customer_id: int | None = Query(None, description="Filter by customer"),
    db: Session = Depends(get_db)
):
    """
    Get items for prompt testing with full baseline data

    Returns recent items that have been processed, including:
    - Full item content
    - Customer details (name, keywords, competitors)
    - Baseline processed results from frontier model
    """

    # Query items with processing results
    query = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id
    ).join(
        Customer,
        IntelligenceItem.customer_id == Customer.id
    ).filter(
        ProcessedIntelligence.summary.isnot(None),
        IntelligenceItem.content.isnot(None)
    )

    if customer_id:
        query = query.filter(IntelligenceItem.customer_id == customer_id)

    # Order by newest first
    query = query.order_by(IntelligenceItem.id.desc())

    total = query.count()
    items = query.limit(limit).all()

    # Build response
    test_items = []
    for item in items:
        customer = db.query(Customer).filter(Customer.id == item.customer_id).first()

        test_items.append(TestItem(
            item_id=item.id,
            title=item.title,
            content=item.content,
            source_type=item.source_type,
            customer=CustomerInfo(
                id=customer.id,
                name=customer.name,
                keywords=customer.keywords or [],
                competitors=customer.competitors or []
            ),
            baseline=ProcessedInfo(
                summary=item.processed.summary,
                category=item.processed.category,
                sentiment=item.processed.sentiment,
                priority_score=item.processed.priority_score or 0.5,
                entities=item.processed.entities,
                tags=item.processed.tags,
                pain_points_opportunities=item.processed.pain_points_opportunities
            )
        ))

    return TestDataResponse(
        items=test_items,
        total=total
    )
