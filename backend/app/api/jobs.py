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
    Find and reprocess items that failed AI processing

    This endpoint finds items that have:
    - Processing errors (last_processing_error is not null)
    - High processing attempts without success

    And marks them for reprocessing, then processes them in the background.

    Args:
        customer_id: Optional - only reprocess items for this customer
        max_items: Maximum number of items to reprocess (default: 100)

    Returns:
        Job ID to track reprocessing progress
    """
    from app.models.database import ProcessedIntelligence, IntelligenceItem, CollectionJob
    from app.processors.ai_processor import get_ai_processor
    from app.models.database import Customer
    from datetime import datetime

    # Find items with processing errors
    query = db.query(ProcessedIntelligence).filter(
        (ProcessedIntelligence.last_processing_error != None) |
        (ProcessedIntelligence.last_processing_error != '') |
        (ProcessedIntelligence.needs_reprocessing == True)
    )

    if customer_id:
        # Filter by customer through join
        query = query.join(IntelligenceItem).filter(
            IntelligenceItem.customer_id == customer_id
        )

    # Order by ID descending to prioritize newest items first
    query = query.order_by(ProcessedIntelligence.id.desc())

    # Apply limit if specified
    if max_items:
        query = query.limit(max_items)

    failed_items = query.all()

    if not failed_items:
        return {
            "status": "no_items",
            "message": "No items found with processing errors",
            "count": 0,
            "job_id": None
        }

    # Log the range of items selected
    item_ids = [item.id for item in failed_items]
    logger.info(f"Selected {len(item_ids)} items for reprocessing - ID range: {max(item_ids)} to {min(item_ids)} (newest first)")

    # Extract IDs before committing (to avoid detached instance issues)
    processed_ids = item_ids

    # Create job record for tracking
    job = CollectionJob(
        job_type='reprocess_failed',
        customer_id=customer_id,
        status='pending',
        started_at=datetime.utcnow(),
        items_collected=len(processed_ids)
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id

    # Reprocess items in background using APScheduler
    def reprocess_items():
        """Background task to reprocess failed items"""
        # Create new database session for background task
        from app.core.database import SessionLocal
        db_bg = SessionLocal()

        try:
            # Update job status to running
            job_record = db_bg.query(CollectionJob).filter(CollectionJob.id == job_id).first()
            if job_record:
                job_record.status = 'running'
                db_bg.commit()

            # Mark all items for reprocessing
            for processed_id in processed_ids:
                item = db_bg.query(ProcessedIntelligence).filter(ProcessedIntelligence.id == processed_id).first()
                if item:
                    item.needs_reprocessing = True
                    item.last_processing_attempt = datetime.utcnow()
            db_bg.commit()

            ai_processor = get_ai_processor(db_bg)
            from app.core.vector_store import get_vector_store
            vector_store = get_vector_store()

            success_count = 0
            still_failed_count = 0
            batch_size = 5  # Commit every 5 items to reduce DB locking
            items_since_commit = 0

            for processed_id in processed_ids:
                # Fetch fresh object from database in this session
                processed = db_bg.query(ProcessedIntelligence).filter(
                    ProcessedIntelligence.id == processed_id
                ).first()

                if not processed:
                    logger.warning(f"ProcessedIntelligence {processed_id} not found")
                    continue
                try:
                    # Get the intelligence item
                    item = db_bg.query(IntelligenceItem).filter(
                        IntelligenceItem.id == processed.item_id
                    ).first()

                    if not item:
                        logger.warning(f"Item {processed.item_id} not found")
                        continue

                    # Get customer info
                    customer = db_bg.query(Customer).filter(
                        Customer.id == item.customer_id
                    ).first()

                    if not customer:
                        logger.warning(f"Customer {item.customer_id} not found")
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
                                import time
                                wait_time = 2 ** attempt
                                logger.info(f"Reprocessing retry {attempt + 1}/{max_retries} for item {item.id} after {wait_time}s...")
                                time.sleep(wait_time)

                            # Run async process_item in this thread's event loop
                            import asyncio
                            processed_data = asyncio.run(ai_processor.process_item(
                                title=item.title,
                                content=item.content or "",
                                customer_name=customer.name,
                                source_type=item.source_type,
                                keywords=keywords,
                                competitors=competitors,
                                priority_keywords=priority_keywords
                            ))

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
                        processed.pain_points_opportunities = processed_data.get('pain_points_opportunities', {'pain_points': [], 'opportunities': []})
                        processed.needs_reprocessing = False
                        processed.processing_attempts += max_retries
                        processed.last_processing_attempt = datetime.utcnow()
                        processed.last_processing_error = None

                        # Update vector store (delete existing then re-add with updated data)
                        try:
                            # Delete existing embedding if it exists
                            try:
                                vector_store.delete_item(item.id)
                            except:
                                pass  # Item might not exist in vector store yet

                            # Add updated embedding
                            text_for_embedding = f"{item.title}\n\n{item.content or ''}"
                            vector_store.add_item(
                                item_id=str(item.id),
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
                        items_since_commit += 1
                        logger.info(f"Successfully reprocessed item {item.id}")

                    else:
                        # Still failed - update attempt count and error
                        processed.processing_attempts += max_retries
                        processed.last_processing_attempt = datetime.utcnow()
                        processed.last_processing_error = processing_error

                        still_failed_count += 1
                        items_since_commit += 1
                        logger.error(f"Reprocessing still failed for item {item.id}: {processing_error}")

                    # Batch commit every N items to reduce database locking
                    if items_since_commit >= batch_size:
                        db_bg.commit()
                        items_since_commit = 0
                        logger.info(f"Batch committed {batch_size} items")

                except Exception as e:
                    logger.error(f"Error reprocessing item {processed.item_id}: {e}")
                    still_failed_count += 1

            # Commit any remaining items
            if items_since_commit > 0:
                db_bg.commit()
                logger.info(f"Final commit of {items_since_commit} remaining items")

            logger.info(f"Reprocessing completed: {success_count} succeeded, {still_failed_count} still failed")

            # Update job status to completed
            job_record = db_bg.query(CollectionJob).filter(CollectionJob.id == job_id).first()
            if job_record:
                job_record.status = 'completed'
                job_record.completed_at = datetime.utcnow()
                job_record.items_failed_processing = still_failed_count
                job_record.error_message = f"{still_failed_count} items still failed" if still_failed_count > 0 else None
                db_bg.commit()

        except Exception as e:
            logger.error(f"Error in reprocessing background task: {e}")
            # Update job status to failed
            try:
                job_record = db_bg.query(CollectionJob).filter(CollectionJob.id == job_id).first()
                if job_record:
                    job_record.status = 'failed'
                    job_record.completed_at = datetime.utcnow()
                    job_record.error_message = str(e)
                    db_bg.commit()
            except Exception as update_error:
                logger.error(f"Error updating job status to failed: {update_error}")
        finally:
            # Close the background database session
            db_bg.close()

    # Add job to APScheduler to run immediately in background thread
    from app.scheduler.jobs import scheduler
    from datetime import datetime

    scheduler.add_job(
        func=reprocess_items,
        trigger='date',
        run_date=datetime.now(),
        id=f'reprocess_failed_{job_id}',
        name=f'Reprocess Failed Items (Job {job_id})',
        replace_existing=True
    )

    return {
        "status": "triggered",
        "message": f"Found and queued {len(processed_ids)} items with processing errors",
        "count": len(processed_ids),
        "job_id": job_id,
        "details": f"Items are being reprocessed in the background. Use GET /api/jobs/{job_id} to check progress."
    }


@router.post("/reprocess-incomplete")
async def reprocess_incomplete_items(
    background_tasks: BackgroundTasks,
    customer_id: int = None,
    max_items: int = None,
    db: Session = Depends(get_db)
):
    """
    Find and reprocess items with missing/incomplete AI processing

    This endpoint finds items that have:
    - No summary
    - Empty entities
    - Missing pain points/opportunities
    - Missing tags or other AI-generated data

    And marks them for reprocessing, then processes them in the background.

    Args:
        customer_id: Optional - only reprocess items for this customer
        max_items: Optional - maximum number of items to reprocess (no limit if not specified)

    Returns:
        Job ID to track progress
    """
    from app.models.database import ProcessedIntelligence, IntelligenceItem, CollectionJob
    from app.processors.ai_processor import get_ai_processor
    from app.models.database import Customer
    from app.core.vector_store import get_vector_store
    from datetime import datetime
    import asyncio

    # Find items with missing AI processing data
    # Only for new processing or flagged items - does NOT backfill pain points
    # (Use force_reprocess parameter to backfill all items)
    query = db.query(ProcessedIntelligence).filter(
        (
            (ProcessedIntelligence.summary == None) |
            (ProcessedIntelligence.summary == '') |
            (ProcessedIntelligence.entities == None) |
            (ProcessedIntelligence.entities == '{}') |
            (ProcessedIntelligence.entities == '{"companies": [], "technologies": [], "people": []}')
        ) &
        (
            (ProcessedIntelligence.needs_reprocessing == True) |
            (ProcessedIntelligence.processing_attempts == 0) |
            (ProcessedIntelligence.processing_attempts == None)
        )
    )

    if customer_id:
        # Filter by customer through join
        query = query.join(IntelligenceItem).filter(
            IntelligenceItem.customer_id == customer_id
        )

    # Order by ID descending to prioritize newest items first
    query = query.order_by(ProcessedIntelligence.id.desc())

    # Apply limit if specified
    if max_items:
        query = query.limit(max_items)

    incomplete_items = query.all()

    if not incomplete_items:
        return {
            "status": "no_items",
            "message": "No items found with incomplete AI processing",
            "count": 0,
            "job_id": None
        }

    # Log the range of items selected
    item_ids = [item.id for item in incomplete_items]
    logger.info(f"Selected {len(item_ids)} items for reprocessing - ID range: {max(item_ids)} to {min(item_ids)} (newest first)")

    # Extract IDs before committing (to avoid detached instance issues)
    processed_ids = [item.id for item in incomplete_items]

    # Create job record for tracking
    job = CollectionJob(
        job_type='reprocess_incomplete',
        customer_id=customer_id,
        status='pending',
        started_at=datetime.utcnow(),
        items_collected=len(processed_ids)
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id

    # Reprocess items in background using APScheduler
    def reprocess_items():
        """Background task to reprocess incomplete items"""
        # Create new database session for background task
        from app.core.database import SessionLocal
        db_bg = SessionLocal()

        try:
            # Update job status to running
            job_record = db_bg.query(CollectionJob).filter(CollectionJob.id == job_id).first()
            if job_record:
                job_record.status = 'running'
                db_bg.commit()

            # Mark all items for reprocessing (in background to avoid blocking API response)
            for processed_id in processed_ids:
                item = db_bg.query(ProcessedIntelligence).filter(ProcessedIntelligence.id == processed_id).first()
                if item:
                    item.needs_reprocessing = True
                    item.last_processing_attempt = datetime.utcnow()
                    item.last_processing_error = "Incomplete AI data - marked for reprocessing"
            db_bg.commit()

            ai_processor = get_ai_processor(db_bg)
            vector_store = get_vector_store()

            success_count = 0
            still_failed_count = 0
            batch_size = 5  # Commit every 5 items to reduce DB locking
            items_since_commit = 0

            for processed_id in processed_ids:
                # Fetch fresh object from database in this session
                processed = db_bg.query(ProcessedIntelligence).filter(
                    ProcessedIntelligence.id == processed_id
                ).first()

                if not processed:
                    logger.warning(f"ProcessedIntelligence {processed_id} not found")
                    continue
                try:
                    # Get the intelligence item
                    item = db_bg.query(IntelligenceItem).filter(
                        IntelligenceItem.id == processed.item_id
                    ).first()

                    if not item:
                        logger.warning(f"Item {processed.item_id} not found")
                        continue

                    # Get customer
                    customer = db_bg.query(Customer).filter(Customer.id == item.customer_id).first()

                    if not customer:
                        logger.warning(f"Customer {item.customer_id} not found")
                        continue

                    # Extract customer context (same as other reprocess endpoint)
                    customer_config = customer.config or {}
                    keywords = customer.keywords or []
                    competitors = customer.competitors or []
                    priority_keywords = customer_config.get('priority_keywords', [])

                    # Process with AI
                    max_retries = 3
                    processing_succeeded = False
                    processed_data = None
                    processing_error = None

                    for attempt in range(max_retries):
                        try:
                            # Run async process_item in this thread's event loop
                            import asyncio
                            processed_data = asyncio.run(ai_processor.process_item(
                                title=item.title,
                                content=item.content or "",
                                customer_name=customer.name,
                                source_type=item.source_type,
                                keywords=keywords,
                                competitors=competitors,
                                priority_keywords=priority_keywords
                            ))
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
                        processed.pain_points_opportunities = processed_data.get('pain_points_opportunities', {'pain_points': [], 'opportunities': []})
                        processed.needs_reprocessing = False
                        processed.processing_attempts += max_retries
                        processed.last_processing_attempt = datetime.utcnow()
                        processed.last_processing_error = None

                        # Update vector store (delete existing then re-add with updated data)
                        try:
                            # Delete existing embedding if it exists
                            try:
                                vector_store.delete_item(item.id)
                            except:
                                pass  # Item might not exist in vector store yet

                            # Add updated embedding
                            text_for_embedding = f"{item.title}\n\n{item.content or ''}"
                            vector_store.add_item(
                                item_id=str(item.id),
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
                        items_since_commit += 1
                        logger.info(f"Successfully reprocessed item {item.id}")

                    else:
                        # Still failed - update attempt count and error
                        processed.processing_attempts += max_retries
                        processed.last_processing_attempt = datetime.utcnow()
                        processed.last_processing_error = processing_error

                        still_failed_count += 1
                        items_since_commit += 1
                        logger.error(f"Reprocessing still failed for item {item.id}: {processing_error}")

                    # Batch commit every N items to reduce database locking
                    if items_since_commit >= batch_size:
                        db_bg.commit()
                        items_since_commit = 0
                        logger.info(f"Batch committed {batch_size} items")

                except Exception as e:
                    logger.error(f"Error reprocessing item {processed.item_id}: {e}")
                    still_failed_count += 1

            # Commit any remaining items
            if items_since_commit > 0:
                db_bg.commit()
                logger.info(f"Final commit of {items_since_commit} remaining items")

            logger.info(f"Incomplete items reprocessing completed: {success_count} succeeded, {still_failed_count} still failed")

            # Update job status to completed
            job_record = db_bg.query(CollectionJob).filter(CollectionJob.id == job_id).first()
            if job_record:
                job_record.status = 'completed'
                job_record.completed_at = datetime.utcnow()
                job_record.items_failed_processing = still_failed_count
                job_record.error_message = f"{still_failed_count} items still failed" if still_failed_count > 0 else None
                db_bg.commit()

        except Exception as e:
            logger.error(f"Error in reprocessing background task: {e}")
            # Update job status to failed
            try:
                job_record = db_bg.query(CollectionJob).filter(CollectionJob.id == job_id).first()
                if job_record:
                    job_record.status = 'failed'
                    job_record.completed_at = datetime.utcnow()
                    job_record.error_message = str(e)
                    db_bg.commit()
            except Exception as update_error:
                logger.error(f"Error updating job status to failed: {update_error}")
        finally:
            # Close the background database session
            db_bg.close()

    # Add job to APScheduler to run immediately in background thread
    from app.scheduler.jobs import scheduler
    from datetime import datetime

    scheduler.add_job(
        func=reprocess_items,
        trigger='date',
        run_date=datetime.now(),
        id=f'reprocess_incomplete_{job_id}',
        name=f'Reprocess Incomplete Items (Job {job_id})',
        replace_existing=True
    )

    return {
        "status": "triggered",
        "message": f"Found and queued {len(processed_ids)} items with incomplete AI processing",
        "count": len(processed_ids),
        "job_id": job_id,
        "details": f"Items are being reprocessed in the background. Use GET /api/jobs/{job_id} to check progress."
    }
