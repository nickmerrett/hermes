"""Data sources API endpoints"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import schemas
from app.models.database import Source, User
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=List[schemas.SourceResponse])
async def list_sources(
    customer_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all data sources, optionally filtered by customer"""
    query = db.query(Source)

    if customer_id:
        query = query.filter(Source.customer_id == customer_id)

    sources = query.all()
    return sources


@router.get("/status", response_model=List[schemas.SourceResponse])
async def get_sources_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get status of all data sources"""
    sources = db.query(Source).all()
    return sources


@router.post("", response_model=schemas.SourceResponse, status_code=201)
async def create_source(
    source: schemas.SourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new data source"""
    db_source = Source(
        customer_id=source.customer_id,
        type=source.type,
        name=source.name,
        url=source.url,
        config=source.config or {},
        enabled=source.enabled
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)

    logger.info(f"Created source: {source.name}")
    return db_source


@router.post("/{source_id}/enable", response_model=schemas.SourceResponse)
async def enable_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Enable a data source"""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.enabled = True
    db.commit()
    db.refresh(source)

    logger.info(f"Enabled source: {source.name}")
    return source


@router.post("/{source_id}/disable", response_model=schemas.SourceResponse)
async def disable_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disable a data source"""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.enabled = False
    db.commit()
    db.refresh(source)

    logger.info(f"Disabled source: {source.name}")
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a data source"""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    db.delete(source)
    db.commit()

    logger.info(f"Deleted source: {source.name}")
    return None
