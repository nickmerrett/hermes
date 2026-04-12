"""Customer management API endpoints"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import (
    get_current_user, check_customer_reshare,
    get_customer_access
)
from app.models import schemas
from app.models.database import Customer, CustomerAccess, User
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _enrich_customer(customer: Customer, user: User, db: Session) -> schemas.CustomerResponse:
    """Build a CustomerResponse with is_owner/can_admin/can_reshare for the current user."""
    is_owner = (customer.owner_id == user.id) or (customer.owner_id is None) or (user.id == 0)
    if is_owner:
        can_admin = can_reshare = True
    else:
        access = get_customer_access(customer.id, user, db)
        can_admin = bool(access and access.can_admin)
        can_reshare = bool(access and access.can_reshare)

    data = schemas.CustomerResponse.model_validate(customer)
    data.is_owner = is_owner
    data.can_admin = can_admin
    data.can_reshare = can_reshare
    return data


@router.get("", response_model=List[schemas.CustomerResponse])
async def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all customers — returns only those owned by or shared with the current user."""
    customers = db.query(Customer).order_by(Customer.sort_order, Customer.id).offset(skip).limit(limit).all()
    return [_enrich_customer(c, current_user, db) for c in customers]


class CustomerOrderItem(BaseModel):
    id: int
    sort_order: int


@router.patch("/reorder")
async def reorder_customers(
    items: List[CustomerOrderItem],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update sort order for customers"""
    for item in items:
        db.query(Customer).filter(Customer.id == item.id).update(
            {Customer.sort_order: item.sort_order}
        )
    db.commit()
    return {"status": "ok"}


@router.get("/{customer_id}", response_model=schemas.CustomerResponse)
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific customer by ID"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("", response_model=schemas.CustomerResponse, status_code=201)
async def create_customer(
    customer: schemas.CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new customer"""
    db_customer = Customer(
        name=customer.name,
        domain=customer.domain,
        keywords=customer.keywords,
        competitors=customer.competitors,
        stock_symbol=customer.stock_symbol,
        config=customer.config or {}
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)

    logger.info(f"Created customer: {customer.name}")
    return db_customer


@router.put("/{customer_id}", response_model=schemas.CustomerResponse)
async def update_customer(
    customer_id: int,
    customer_update: schemas.CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a customer"""
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Update fields if provided
    update_data = customer_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_customer, field, value)

    db.commit()
    db.refresh(db_customer)

    logger.info(f"Updated customer: {db_customer.name}")
    return db_customer


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a customer"""
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.delete(db_customer)
    db.commit()

    logger.info(f"Deleted customer: {db_customer.name}")
    return None


# ---------------------------------------------------------------------------
# Share management endpoints
# ---------------------------------------------------------------------------

@router.get("/{customer_id}/shares", response_model=schemas.ShareListResponse)
async def list_shares(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all shares for a customer. Requires owner or can_reshare."""
    check_customer_reshare(customer_id, current_user, db)

    shares = db.query(CustomerAccess).filter(CustomerAccess.customer_id == customer_id).all()
    entries = [
        schemas.ShareEntry(
            user_id=s.user_id,
            email=s.user.email,
            can_admin=s.can_admin,
            can_reshare=s.can_reshare,
            granted_at=s.granted_at,
            granted_by_email=s.granted_by.email if s.granted_by else None
        )
        for s in shares
    ]
    return schemas.ShareListResponse(shares=entries)


@router.post("/{customer_id}/shares", status_code=201)
async def add_share(
    customer_id: int,
    request: schemas.ShareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Share a customer with another user. Granted permissions capped at granter's own."""
    granter_access = check_customer_reshare(customer_id, current_user, db)

    # Cap permissions at what the granter themselves has
    # granter_access is None when granter is the owner (no cap)
    can_admin = request.can_admin
    can_reshare = request.can_reshare
    if granter_access is not None:
        can_admin = can_admin and granter_access.can_admin
        can_reshare = can_reshare and granter_access.can_reshare

    target = db.query(User).filter(User.email == request.email).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot share with yourself")

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if target.id == customer.owner_id:
        raise HTTPException(status_code=400, detail="User is already the owner")

    existing = db.query(CustomerAccess).filter(
        CustomerAccess.customer_id == customer_id,
        CustomerAccess.user_id == target.id
    ).first()

    if existing:
        existing.can_admin = can_admin
        existing.can_reshare = can_reshare
        existing.granted_by_id = current_user.id
        existing.granted_at = datetime.utcnow()
        db.commit()
        logger.info(f"Updated share: customer {customer_id} → {target.email} by {current_user.email}")
        return {"message": "Share updated"}

    db.add(CustomerAccess(
        customer_id=customer_id,
        user_id=target.id,
        granted_by_id=current_user.id,
        can_admin=can_admin,
        can_reshare=can_reshare,
    ))
    db.commit()
    logger.info(f"Shared customer {customer_id} with {target.email} by {current_user.email}")
    return {"message": "Customer shared successfully"}


@router.delete("/{customer_id}/shares/{user_id}", status_code=204)
async def revoke_share(
    customer_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Revoke a user's access to a customer. Requires owner or can_reshare."""
    check_customer_reshare(customer_id, current_user, db)

    access = db.query(CustomerAccess).filter(
        CustomerAccess.customer_id == customer_id,
        CustomerAccess.user_id == user_id
    ).first()
    if not access:
        raise HTTPException(status_code=404, detail="Share not found")

    db.delete(access)
    db.commit()
    logger.info(f"Revoked user {user_id} access to customer {customer_id} by {current_user.email}")
    return None
