"""RSS feed API endpoints"""

import secrets
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.database import (
    IntelligenceItem, ProcessedIntelligence, Customer,
    User, RSSFeedToken
)
from app.models.auth_schemas import RSSTokenCreate, RSSTokenResponse, RSSTokenListResponse
from app.utils.rss_generator import generate_rss_feed
from app.utils.smart_feed import (
    get_smart_feed_settings,
    get_customer_smart_feed_settings,
    get_default_smart_feed_settings,
    calculate_effective_priority,
    should_include_item,
    apply_diversity_control
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _generate_token() -> str:
    """Generate a secure random token for RSS feed access"""
    return secrets.token_urlsafe(32)


@router.get("/feed")
async def get_rss_feed(
    token: str = Query(..., description="RSS feed access token"),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Get RSS feed for a customer using token-based authentication

    This endpoint does NOT require JWT authentication - it uses the token
    in the URL for compatibility with RSS readers.
    """
    # Find token in database
    rss_token = db.query(RSSFeedToken).filter(
        RSSFeedToken.token == token,
        RSSFeedToken.is_active.is_(True)
    ).first()

    if not rss_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired RSS token"
        )

    # Update last used timestamp
    rss_token.last_used = datetime.utcnow()
    db.commit()

    # Get customer
    customer = db.query(Customer).filter(Customer.id == rss_token.customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    # Get smart feed settings (customer-specific if configured)
    smart_config = get_customer_smart_feed_settings(db, customer.id)

    # Build query for intelligence items
    query = db.query(IntelligenceItem).join(
        ProcessedIntelligence,
        IntelligenceItem.id == ProcessedIntelligence.item_id,
        isouter=True
    )

    # Apply filters
    filters = [
        IntelligenceItem.customer_id == rss_token.customer_id,
        IntelligenceItem.ignored.is_(False),
        IntelligenceItem.is_cluster_primary.is_(True)  # Only show primary items
    ]
    query = query.filter(and_(*filters))

    # Fetch items
    fetch_limit = 100  # Get more for smart feed filtering
    all_items = query.order_by(
        desc(IntelligenceItem.published_date)
    ).limit(fetch_limit).all()

    # Apply smart feed filtering
    filtered_items = []
    if smart_config and smart_config.get('enabled', True):
        item_ids = [item.id for item in all_items]
        processed_map = {}
        if item_ids:
            processed_list = db.query(ProcessedIntelligence).filter(
                ProcessedIntelligence.item_id.in_(item_ids)
            ).all()
            processed_map = {p.item_id: p for p in processed_list}

        for item in all_items:
            processed = processed_map.get(item.id)
            effective_priority = calculate_effective_priority(item, processed, smart_config)
            if should_include_item(item, processed, effective_priority, smart_config):
                filtered_items.append(item)

        filtered_items = apply_diversity_control(filtered_items, smart_config)
        max_items = smart_config.get('max_items', 50)
        items = filtered_items[:max_items]
    else:
        max_items = smart_config.get('max_items', 50)
        items = all_items[:max_items]

    # Build feed URL
    base_url = str(request.base_url).rstrip('/')
    feed_url = f"{base_url}/api/rss/feed?token={token}"

    # Build all item dicts (articles + daily briefings) then sort by date
    item_dicts = []

    # Add all stored daily summaries as feed items
    from app.models.database import DailySummary
    summaries = (
        db.query(DailySummary)
        .filter(DailySummary.customer_id == customer.id)
        .order_by(DailySummary.generated_at.desc())
        .limit(30)
        .all()
    )
    for s in summaries:
        date_str = s.summary_date.strftime('%Y-%m-%d') if s.summary_date else s.generated_at.strftime('%Y-%m-%d')
        stats = f"Items: {s.total_items or 0} | High priority: {s.high_priority_count or 0}"
        item_dicts.append({
            'id': f"briefing-{s.id}",
            'title': f"Daily Briefing — {customer.name} — {date_str}",
            'url': None,
            'summary': f"{s.summary_text}\n\n---\n{stats}",
            'content': s.summary_text,
            'published_date': s.generated_at,
            'source_type': 'daily_briefing',
            'category': 'daily_briefing',
            'priority_score': 1.0,
            'sentiment': None,
        })

    # Convert intelligence items to dict format
    for item in items:
        item_dict = {
            'id': item.id,
            'title': item.title,
            'url': item.url,
            'content': item.content,
            'published_date': item.published_date,
            'source_type': item.source_type,
        }
        if item.processed:
            item_dict.update({
                'summary': item.processed.summary,
                'category': item.processed.category,
                'priority_score': item.processed.priority_score,
                'sentiment': item.processed.sentiment,
            })
        item_dicts.append(item_dict)

    # Sort merged list newest-first by published_date
    item_dicts.sort(key=lambda x: x.get('published_date') or datetime.min, reverse=True)

    # Generate RSS XML
    rss_xml = generate_rss_feed(
        items=item_dicts,
        customer_name=customer.name,
        feed_url=feed_url
    )

    return Response(
        content=rss_xml,
        media_type="application/rss+xml",
        headers={
            "Content-Type": "application/rss+xml; charset=utf-8"
        }
    )


@router.get("/tokens", response_model=RSSTokenListResponse)
async def list_rss_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all RSS tokens for the current user
    """
    tokens = db.query(RSSFeedToken).filter(
        RSSFeedToken.user_id == current_user.id
    ).order_by(desc(RSSFeedToken.created_at)).all()

    # Enrich with customer names
    token_responses = []
    for token in tokens:
        customer = db.query(Customer).filter(Customer.id == token.customer_id).first()
        token_dict = {
            'id': token.id,
            'token': token.token,
            'name': token.name,
            'customer_id': token.customer_id,
            'customer_name': customer.name if customer else None,
            'user_id': token.user_id,
            'is_active': token.is_active,
            'created_at': token.created_at,
            'last_used': token.last_used,
            'rss_url': None  # Will be set by frontend
        }
        token_responses.append(RSSTokenResponse(**token_dict))

    return RSSTokenListResponse(tokens=token_responses, total=len(token_responses))


@router.post("/tokens", response_model=RSSTokenResponse, status_code=201)
async def create_rss_token(
    token_create: RSSTokenCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new RSS feed token for a customer
    """
    # Verify customer exists
    customer = db.query(Customer).filter(Customer.id == token_create.customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    # Generate token
    token_value = _generate_token()

    # Create token record
    rss_token = RSSFeedToken(
        token=token_value,
        customer_id=token_create.customer_id,
        user_id=current_user.id,
        name=token_create.name,
        is_active=True
    )
    db.add(rss_token)
    db.commit()
    db.refresh(rss_token)

    # Build RSS URL
    base_url = str(request.base_url).rstrip('/')
    rss_url = f"{base_url}/api/rss/feed?token={token_value}"

    logger.info(f"Created RSS token for customer {customer.name} by user {current_user.email}")

    return RSSTokenResponse(
        id=rss_token.id,
        token=rss_token.token,
        name=rss_token.name,
        customer_id=rss_token.customer_id,
        customer_name=customer.name,
        user_id=rss_token.user_id,
        is_active=rss_token.is_active,
        created_at=rss_token.created_at,
        last_used=rss_token.last_used,
        rss_url=rss_url
    )


@router.delete("/tokens/{token_id}", status_code=204)
async def revoke_rss_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revoke (delete) an RSS feed token

    Users can only revoke their own tokens.
    Admins can revoke any token.
    """
    rss_token = db.query(RSSFeedToken).filter(RSSFeedToken.id == token_id).first()

    if not rss_token:
        raise HTTPException(
            status_code=404,
            detail="Token not found"
        )

    # Check ownership (unless admin)
    if rss_token.user_id != current_user.id and current_user.role != 'platform_admin':
        raise HTTPException(
            status_code=403,
            detail="You can only revoke your own tokens"
        )

    logger.info(f"Revoking RSS token {token_id} by user {current_user.email}")
    db.delete(rss_token)
    db.commit()

    return None


@router.patch("/tokens/{token_id}/deactivate")
async def deactivate_rss_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deactivate an RSS feed token without deleting it

    This allows the token to be reactivated later.
    """
    rss_token = db.query(RSSFeedToken).filter(RSSFeedToken.id == token_id).first()

    if not rss_token:
        raise HTTPException(
            status_code=404,
            detail="Token not found"
        )

    # Check ownership (unless admin)
    if rss_token.user_id != current_user.id and current_user.role != 'platform_admin':
        raise HTTPException(
            status_code=403,
            detail="You can only modify your own tokens"
        )

    rss_token.is_active = False
    db.commit()

    logger.info(f"Deactivated RSS token {token_id} by user {current_user.email}")
    return {"message": "Token deactivated", "token_id": token_id}


@router.patch("/tokens/{token_id}/activate")
async def activate_rss_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reactivate a deactivated RSS feed token
    """
    rss_token = db.query(RSSFeedToken).filter(RSSFeedToken.id == token_id).first()

    if not rss_token:
        raise HTTPException(
            status_code=404,
            detail="Token not found"
        )

    # Check ownership (unless admin)
    if rss_token.user_id != current_user.id and current_user.role != 'platform_admin':
        raise HTTPException(
            status_code=403,
            detail="You can only modify your own tokens"
        )

    rss_token.is_active = True
    db.commit()

    logger.info(f"Activated RSS token {token_id} by user {current_user.email}")
    return {"message": "Token activated", "token_id": token_id}


@router.get("/settings/{customer_id}")
async def get_customer_feed_settings(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get smart feed settings for a customer.

    Returns the merged settings (customer overrides + global defaults)
    along with the raw customer-specific overrides.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get global defaults
    global_settings = get_smart_feed_settings(db)
    defaults = get_default_smart_feed_settings()

    # Get customer-specific settings
    customer_settings = {}
    if customer.config and customer.config.get('smart_feed'):
        customer_settings = customer.config.get('smart_feed', {})

    # Get merged settings (what actually gets used)
    effective_settings = get_customer_smart_feed_settings(db, customer_id)

    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "use_custom": customer_settings.get('use_custom', False),
        "customer_settings": customer_settings,
        "effective_settings": effective_settings,
        "global_settings": global_settings,
        "defaults": defaults
    }


@router.put("/settings/{customer_id}")
async def update_customer_feed_settings(
    customer_id: int,
    settings: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update smart feed settings for a customer.

    The settings dict should include:
    - use_custom: bool - whether to use custom settings
    - Any smart feed settings to override (min_priority, max_items, etc.)
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Initialize config if needed
    if not customer.config:
        customer.config = {}

    # Update the smart_feed section
    customer.config['smart_feed'] = settings

    # SQLAlchemy needs to know the JSON changed
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(customer, 'config')

    db.commit()
    db.refresh(customer)

    logger.info(f"Updated smart feed settings for customer {customer.name} by user {current_user.email}")

    return {
        "message": "Settings updated",
        "customer_id": customer_id,
        "settings": settings
    }
