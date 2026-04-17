"""Analytics API endpoints"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from anthropic import Anthropic
from collections import Counter, defaultdict
import json

from app.core.database import get_db
from app.core.dependencies import get_current_user, check_customer_access
from app.models import schemas
from app.models.database import IntelligenceItem, ProcessedIntelligence, Customer, User, DailySummary
import logging

logger = logging.getLogger(__name__)

# Import OpenAI (optional)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. OpenAI models will not be available for daily summaries.")
router = APIRouter()


def _create_ai_client_from_model_config(model_config):
    """Helper to create AI client from template model config"""
    if model_config.provider == 'anthropic':
        if not model_config.api_key:
            raise ValueError(f"{model_config.api_key_env} not configured")
        return Anthropic(api_key=model_config.api_key, base_url=model_config.api_base), 'anthropic'
    elif model_config.provider in ['openai', 'lmstudio']:
        if not OPENAI_AVAILABLE:
            raise ValueError("OpenAI package not installed")
        api_key = model_config.api_key if model_config.api_key else "lm-studio"
        return OpenAI(api_key=api_key, base_url=model_config.api_base), 'openai'
    else:
        raise ValueError(f"Unknown provider: {model_config.provider}")


@router.get("/summary", response_model=schemas.AnalyticsSummary)
async def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get analytics summary across all intelligence items"""

    # Total items
    total_items = db.query(IntelligenceItem).count()

    # Items by category
    category_counts = db.query(
        ProcessedIntelligence.category,
        func.count(ProcessedIntelligence.id)
    ).group_by(ProcessedIntelligence.category).all()
    items_by_category = {cat: count for cat, count in category_counts if cat}

    # Items by sentiment
    sentiment_counts = db.query(
        ProcessedIntelligence.sentiment,
        func.count(ProcessedIntelligence.id)
    ).group_by(ProcessedIntelligence.sentiment).all()
    items_by_sentiment = {sent: count for sent, count in sentiment_counts if sent}

    # Items by source
    source_counts = db.query(
        IntelligenceItem.source_type,
        func.count(IntelligenceItem.id)
    ).group_by(IntelligenceItem.source_type).all()
    items_by_source = {src: count for src, count in source_counts}

    # Recent items (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_items_count = db.query(IntelligenceItem).filter(
        IntelligenceItem.collected_date >= yesterday
    ).count()

    # High priority items (priority > 0.7)
    high_priority_items = db.query(ProcessedIntelligence).filter(
        ProcessedIntelligence.priority_score > 0.7
    ).count()

    # Number of customers
    customers_monitored = db.query(Customer).count()

    return schemas.AnalyticsSummary(
        total_items=total_items,
        items_by_category=items_by_category,
        items_by_sentiment=items_by_sentiment,
        items_by_source=items_by_source,
        recent_items_count=recent_items_count,
        high_priority_items=high_priority_items,
        customers_monitored=customers_monitored
    )


@router.get("/daily-summary/{customer_id}")
async def get_daily_summary(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily summary of items collected in the last 24 hours for a specific customer"""

    yesterday = datetime.utcnow() - timedelta(days=1)

    # Get items from last 24 hours for this customer
    recent_items = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id,
        isouter=True
    ).filter(
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= yesterday
    ).order_by(
        ProcessedIntelligence.priority_score.desc().nullslast(),
        IntelligenceItem.collected_date.desc()
    ).limit(20).all()

    # Count by category
    category_counts = db.query(
        ProcessedIntelligence.category,
        func.count(ProcessedIntelligence.id)
    ).join(
        IntelligenceItem,
        IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= yesterday
    ).group_by(ProcessedIntelligence.category).all()

    # Count high priority items
    high_priority_count = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= yesterday,
        ProcessedIntelligence.priority_score >= 0.7
    ).count()

    return {
        "customer_id": customer_id,
        "period": "last_24_hours",
        "total_items": len(recent_items),
        "high_priority_count": high_priority_count,
        "items_by_category": {cat: count for cat, count in category_counts if cat},
        "recent_items": [
            {
                "id": item.id,
                "title": item.title,
                "summary": item.processed.summary if item.processed else None,
                "category": item.processed.category if item.processed else None,
                "priority_score": item.processed.priority_score if item.processed else None,
                "sentiment": item.processed.sentiment if item.processed else None,
                "url": item.url,
                "published_date": item.published_date,
                "collected_date": item.collected_date,
                "source_type": item.source_type
            }
            for item in recent_items
        ]
    }


@router.get("/daily-summary-ai/{customer_id}")
async def get_daily_summary_ai(
    customer_id: int,
    force_refresh: bool = False,
    persona: str = None,
    custom_persona_text: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get or generate an AI-powered textual summary of the last 24 hours for a customer

    Args:
        customer_id: Customer ID
        force_refresh: If True, bypass cache and regenerate summary
        persona: Persona key to use from template (e.g., 'executive', 'technical', 'sales')
        custom_persona_text: Custom persona instructions (overrides persona key)
        db: Database session
        current_user: Authenticated user (required for manual API access)

    Returns:
        Daily summary data or None if no summary available
    """
    from app.services.daily_summary import generate_daily_summary

    return generate_daily_summary(
        customer_id=customer_id,
        db=db,
        force_refresh=force_refresh,
        persona=persona,
        custom_persona_text=custom_persona_text
    )


@router.get("/summaries/{customer_id}")
async def list_daily_summaries(
    customer_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return all stored daily summaries for a customer, newest first."""
    check_customer_access(customer_id, current_user, db)
    rows = (
        db.query(DailySummary)
        .filter(DailySummary.customer_id == customer_id)
        .order_by(DailySummary.generated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "summary_date": r.summary_date,
            "generated_at": r.generated_at,
            "summary_text": r.summary_text,
            "total_items": r.total_items,
            "high_priority_count": r.high_priority_count,
            "items_by_category": r.items_by_category,
            "sources": r.sources_json,
        }
        for r in rows
    ]


@router.get("/dashboard/{customer_id}")
async def get_analytics_dashboard(
    customer_id: int,
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get full analytics dashboard data for a customer"""

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return {"error": "Customer not found"}

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Base query filters
    base_item_filter = [
        IntelligenceItem.customer_id == customer_id,
        IntelligenceItem.collected_date >= cutoff,
        IntelligenceItem.ignored.is_(False),
    ]

    # --- Summary stats ---
    total_items = db.query(func.count(IntelligenceItem.id)).filter(
        *base_item_filter
    ).scalar() or 0

    high_priority_count = db.query(func.count(ProcessedIntelligence.id)).join(
        IntelligenceItem, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        *base_item_filter,
        ProcessedIntelligence.priority_score >= 0.7,
    ).scalar() or 0

    avg_priority = db.query(func.avg(ProcessedIntelligence.priority_score)).join(
        IntelligenceItem, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        *base_item_filter,
    ).scalar()
    avg_priority = round(avg_priority, 2) if avg_priority else 0

    sources_active = db.query(func.count(func.distinct(IntelligenceItem.source_type))).filter(
        *base_item_filter
    ).scalar() or 0

    # --- Timeline: daily counts by category ---
    timeline_rows = db.query(
        func.date(IntelligenceItem.collected_date).label('day'),
        ProcessedIntelligence.category,
        func.count(IntelligenceItem.id).label('cnt'),
    ).outerjoin(
        ProcessedIntelligence, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        *base_item_filter,
    ).group_by('day', ProcessedIntelligence.category).all()

    # Build timeline with zero-fill
    timeline_map = defaultdict(lambda: defaultdict(int))
    all_categories = set()
    for row in timeline_rows:
        day_str = str(row.day)
        cat = row.category or 'uncategorized'
        timeline_map[day_str][cat] += row.cnt
        all_categories.add(cat)

    # Zero-fill missing days
    timeline = []
    if timeline_map:
        current = cutoff.date()
        end = datetime.utcnow().date()
        while current <= end:
            day_str = current.isoformat()
            breakdown = timeline_map.get(day_str, {})
            count = sum(breakdown.values())
            timeline.append({
                "date": day_str,
                "count": count,
                "breakdown": dict(breakdown),
            })
            current += timedelta(days=1)

    # --- Tag frequencies ---
    tag_rows = db.query(ProcessedIntelligence.tags).join(
        IntelligenceItem, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        *base_item_filter,
        ProcessedIntelligence.tags.isnot(None),
    ).all()

    tag_counter = Counter()
    for (tags_json,) in tag_rows:
        if isinstance(tags_json, list):
            for tag in tags_json:
                if isinstance(tag, str) and tag.strip():
                    tag_counter[tag.strip().lower()] += 1
        elif isinstance(tags_json, str):
            try:
                tags_list = json.loads(tags_json)
                for tag in tags_list:
                    if isinstance(tag, str) and tag.strip():
                        tag_counter[tag.strip().lower()] += 1
            except (json.JSONDecodeError, TypeError):
                pass

    tag_frequencies = [
        {"tag": tag, "count": count}
        for tag, count in tag_counter.most_common(80)
    ]

    # --- Distributions ---
    category_rows = db.query(
        ProcessedIntelligence.category,
        func.count(ProcessedIntelligence.id),
    ).join(
        IntelligenceItem, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        *base_item_filter,
    ).group_by(ProcessedIntelligence.category).all()
    items_by_category = {cat: cnt for cat, cnt in category_rows if cat}

    sentiment_rows = db.query(
        ProcessedIntelligence.sentiment,
        func.count(ProcessedIntelligence.id),
    ).join(
        IntelligenceItem, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        *base_item_filter,
    ).group_by(ProcessedIntelligence.sentiment).all()
    items_by_sentiment = {sent: cnt for sent, cnt in sentiment_rows if sent}

    source_rows = db.query(
        IntelligenceItem.source_type,
        func.count(IntelligenceItem.id),
    ).filter(
        *base_item_filter,
    ).group_by(IntelligenceItem.source_type).all()
    items_by_source = {src: cnt for src, cnt in source_rows}

    # --- Priority histogram ---
    priority_scores = db.query(ProcessedIntelligence.priority_score).join(
        IntelligenceItem, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        *base_item_filter,
        ProcessedIntelligence.priority_score.isnot(None),
    ).all()

    bins = [
        ("0.0-0.2", "Very Low", 0.0, 0.2),
        ("0.2-0.4", "Low", 0.2, 0.4),
        ("0.4-0.6", "Medium", 0.4, 0.6),
        ("0.6-0.8", "High", 0.6, 0.8),
        ("0.8-1.0", "Critical", 0.8, 1.01),
    ]
    priority_histogram = []
    for bin_label, label, lo, hi in bins:
        count = sum(1 for (s,) in priority_scores if s is not None and lo <= s < hi)
        priority_histogram.append({"bin": bin_label, "label": label, "count": count})

    # --- Weekly trends ---
    weekly_rows = db.query(
        func.strftime('%Y-%W', IntelligenceItem.collected_date).label('week'),
        ProcessedIntelligence.sentiment,
        ProcessedIntelligence.category,
        func.count(IntelligenceItem.id).label('cnt'),
    ).outerjoin(
        ProcessedIntelligence, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        *base_item_filter,
    ).group_by('week', ProcessedIntelligence.sentiment, ProcessedIntelligence.category).all()

    weekly_map = defaultdict(lambda: {"total": 0, "by_sentiment": defaultdict(int), "by_category": defaultdict(int)})
    for row in weekly_rows:
        w = row.week
        weekly_map[w]["total"] += row.cnt
        if row.sentiment:
            weekly_map[w]["by_sentiment"][row.sentiment] += row.cnt
        if row.category:
            weekly_map[w]["by_category"][row.category] += row.cnt

    weekly_trends = sorted([
        {
            "week_start": week,
            "total": data["total"],
            "by_sentiment": dict(data["by_sentiment"]),
            "by_category": dict(data["by_category"]),
        }
        for week, data in weekly_map.items()
    ], key=lambda x: x["week_start"])

    # --- Top entities ---
    entity_rows = db.query(ProcessedIntelligence.entities).join(
        IntelligenceItem, IntelligenceItem.id == ProcessedIntelligence.item_id
    ).filter(
        *base_item_filter,
        ProcessedIntelligence.entities.isnot(None),
    ).all()

    entity_counters = defaultdict(Counter)
    for (entities_json,) in entity_rows:
        if isinstance(entities_json, dict):
            for entity_type, entity_list in entities_json.items():
                if isinstance(entity_list, list):
                    for name in entity_list:
                        if isinstance(name, str) and name.strip():
                            entity_counters[entity_type][name.strip()] += 1
        elif isinstance(entities_json, str):
            try:
                entities_dict = json.loads(entities_json)
                if isinstance(entities_dict, dict):
                    for entity_type, entity_list in entities_dict.items():
                        if isinstance(entity_list, list):
                            for name in entity_list:
                                if isinstance(name, str) and name.strip():
                                    entity_counters[entity_type][name.strip()] += 1
            except (json.JSONDecodeError, TypeError):
                pass

    top_entities = {
        etype: [{"name": name, "count": cnt} for name, cnt in counter.most_common(10)]
        for etype, counter in entity_counters.items()
    }

    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "period_days": days,
        "total_items": total_items,
        "high_priority_count": high_priority_count,
        "avg_priority": avg_priority,
        "sources_active": sources_active,
        "timeline": timeline,
        "tag_frequencies": tag_frequencies,
        "items_by_category": items_by_category,
        "items_by_sentiment": items_by_sentiment,
        "items_by_source": items_by_source,
        "priority_histogram": priority_histogram,
        "weekly_trends": weekly_trends,
        "top_entities": top_entities,
    }
