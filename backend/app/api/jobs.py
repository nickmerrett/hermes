"""Collection jobs API endpoints"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List

from app.core.database import get_db
from app.models import schemas
from app.models.database import CollectionJob
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=List[schemas.CollectionJobResponse])
async def list_jobs(
    limit: int = 50,
    customer_id: int = None,
    db: Session = Depends(get_db)
):
    """Get list of recent collection jobs"""
    query = db.query(CollectionJob)

    if customer_id:
        query = query.filter(CollectionJob.customer_id == customer_id)

    jobs = query.order_by(desc(CollectionJob.started_at)).limit(limit).all()
    return jobs


@router.get("/{job_id}", response_model=schemas.CollectionJobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get details of a specific job"""
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.post("/trigger")
async def trigger_collection(
    background_tasks: BackgroundTasks,
    customer_id: int = None,
    db: Session = Depends(get_db)
):
    """Manually trigger a collection job"""
    from app.scheduler.collection import run_collection

    # Trigger collection in background
    background_tasks.add_task(run_collection, customer_id)

    return {
        "status": "triggered",
        "message": f"Collection job triggered for {'all customers' if not customer_id else f'customer {customer_id}'}"
    }


@router.post("/purge")
async def trigger_purge(
    background_tasks: BackgroundTasks,
    retention_days: int = None,
    db: Session = Depends(get_db)
):
    """Manually trigger a data purge job

    Args:
        retention_days: Number of days to retain items. If not provided, uses default from settings.
    """
    from app.scheduler.collection import purge_old_items
    from app.config.settings import settings

    if retention_days is None:
        retention_days = settings.intelligence_retention_days

    # Trigger purge in background
    background_tasks.add_task(purge_old_items, retention_days)

    return {
        "status": "triggered",
        "message": f"Purge job triggered (retention: {retention_days} days)"
    }


@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler status and next run times for scheduled jobs"""
    from app.scheduler.jobs import get_scheduler_status

    return get_scheduler_status()


@router.post("/reprocess-failed")
async def reprocess_failed_items(
    background_tasks: BackgroundTasks,
    customer_id: int = None,
    max_items: int = 100,
    db: Session = Depends(get_db)
):
    """
    Reprocess items that failed AI processing

    Args:
        customer_id: Optional - only reprocess items for this customer
        max_items: Maximum number of items to reprocess (default: 100)

    Returns:
        Status and count of items queued for reprocessing
    """
    from app.models.database import ProcessedIntelligence, IntelligenceItem
    from app.processors.ai_processor import get_ai_processor
    from app.models.database import Customer
    from datetime import datetime

    # Find items that need reprocessing
    query = db.query(ProcessedIntelligence).filter(
        ProcessedIntelligence.needs_reprocessing == True
    )

    if customer_id:
        # Filter by customer through join
        query = query.join(IntelligenceItem).filter(
            IntelligenceItem.customer_id == customer_id
        )

    # Get items ordered by last attempt (oldest first)
    failed_items = query.order_by(
        ProcessedIntelligence.last_processing_attempt
    ).limit(max_items).all()

    if not failed_items:
        return {
            "status": "no_items",
            "message": "No items found that need reprocessing",
            "count": 0
        }

    # Reprocess items in background
    async def reprocess_items():
        """Background task to reprocess failed items"""
        ai_processor = get_ai_processor()
        from app.core.vector_store import get_vector_store
        vector_store = get_vector_store()

        success_count = 0
        still_failed_count = 0

        for processed in failed_items:
            try:
                # Get the intelligence item
                item = db.query(IntelligenceItem).filter(
                    IntelligenceItem.id == processed.item_id
                ).first()

                if not item:
                    continue

                # Get customer info
                customer = db.query(Customer).filter(
                    Customer.id == item.customer_id
                ).first()

                if not customer:
                    continue

                # Extract customer context
                customer_config = customer.config or {}
                keywords = customer.keywords or []
                competitors = customer.competitors or []
                priority_keywords = customer_config.get('priority_keywords', [])

                # Try to reprocess with AI (3 retries with exponential backoff)
                max_retries = 3
                processing_succeeded = False
                processing_error = None

                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            import asyncio
                            wait_time = 2 ** attempt
                            logger.info(f"Reprocessing retry {attempt + 1}/{max_retries} for item {item.id} after {wait_time}s...")
                            await asyncio.sleep(wait_time)

                        processed_data = await ai_processor.process_item(
                            title=item.title,
                            content=item.content or "",
                            customer_name=customer.name,
                            source_type=item.source_type,
                            keywords=keywords,
                            competitors=competitors,
                            priority_keywords=priority_keywords
                        )

                        processing_succeeded = True
                        break

                    except Exception as e:
                        processing_error = str(e)
                        logger.warning(f"Reprocessing attempt {attempt + 1}/{max_retries} failed for item {item.id}: {e}")

                if processing_succeeded and processed_data:
                    # Update processed intelligence with new data
                    if not processed_data.get('is_relevant', True):
                        processed_data['category'] = 'unrelated'
                        processed_data['priority_score'] = min(processed_data.get('priority_score', 0.1), 0.3)

                    processed.summary = processed_data['summary']
                    processed.category = processed_data['category']
                    processed.sentiment = processed_data['sentiment']
                    processed.priority_score = processed_data['priority_score']
                    processed.entities = processed_data['entities']
                    processed.tags = processed_data['tags']
                    processed.needs_reprocessing = False
                    processed.processing_attempts += max_retries
                    processed.last_processing_attempt = datetime.utcnow()
                    processed.last_processing_error = None

                    db.commit()

                    # Update vector store
                    try:
                        text_for_embedding = f"{item.title}\n\n{item.content or ''}"
                        vector_store.add_item(
                            item_id=item.id,
                            text=text_for_embedding,
                            metadata={
                                'customer_id': customer.id,
                                'source_type': item.source_type,
                                'category': processed_data['category'],
                                'priority': processed_data['priority_score']
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error updating vector store for item {item.id}: {e}")

                    success_count += 1
                    logger.info(f"Successfully reprocessed item {item.id}")

                else:
                    # Still failed - update attempt count and error
                    processed.processing_attempts += max_retries
                    processed.last_processing_attempt = datetime.utcnow()
                    processed.last_processing_error = processing_error
                    db.commit()

                    still_failed_count += 1
                    logger.error(f"Reprocessing still failed for item {item.id}: {processing_error}")

            except Exception as e:
                logger.error(f"Error reprocessing item {processed.item_id}: {e}")
                still_failed_count += 1

        logger.info(f"Reprocessing completed: {success_count} succeeded, {still_failed_count} still failed")

    # Add task to background
    background_tasks.add_task(reprocess_items)

    return {
        "status": "triggered",
        "message": f"Reprocessing {len(failed_items)} failed items in background",
        "count": len(failed_items)
    }
