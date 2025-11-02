"""Customer management API endpoints"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models import schemas
from app.models.database import Customer
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=List[schemas.CustomerResponse])
async def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get list of all customers"""
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers


@router.get("/{customer_id}", response_model=schemas.CustomerResponse)
async def get_customer(customer_id: int, db: Session = Depends(get_db)):
    """Get a specific customer by ID"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("", response_model=schemas.CustomerResponse, status_code=201)
async def create_customer(
    customer: schemas.CustomerCreate,
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
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
async def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """Delete a customer"""
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.delete(db_customer)
    db.commit()

    logger.info(f"Deleted customer: {db_customer.name}")
    return None
