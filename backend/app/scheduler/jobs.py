"""APScheduler job definitions and management"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import pytz
import os

from app.scheduler.collection import run_collection, purge_old_items
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: BackgroundScheduler = None


def start_scheduler():
    """Initialize and start the APScheduler"""
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already running")
        return

    # Get timezone from environment variable, default to UTC
    tz_name = os.environ.get('TZ', 'UTC')
    try:
        scheduler_timezone = pytz.timezone(tz_name)
        logger.info(f"Using timezone: {tz_name}")
    except pytz.UnknownTimeZoneError:
        logger.warning(f"Unknown timezone '{tz_name}', falling back to UTC")
        scheduler_timezone = pytz.UTC

    scheduler = BackgroundScheduler(
        timezone=scheduler_timezone,
        job_defaults={
            'coalesce': True,  # Combine multiple pending executions into one
            'max_instances': 1,  # Only one instance of each job at a time
            'misfire_grace_time': 300  # 5 minutes grace period for misfired jobs
        }
    )

    # Add hourly collection job
    if settings.hourly_collection_enabled:
        scheduler.add_job(
            func=hourly_collection_job,
            trigger=CronTrigger(minute=0),  # Run at the start of every hour
            id='hourly_collection',
            name='Hourly News Collection',
            replace_existing=True
        )
        logger.info("Scheduled hourly collection job")

    # Add daily comprehensive collection job
    if settings.daily_collection_enabled:
        scheduler.add_job(
            func=daily_collection_job,
            trigger=CronTrigger(hour=settings.daily_collection_hour, minute=0),
            id='daily_collection',
            name='Daily Comprehensive Collection',
            replace_existing=True
        )
        logger.info(f"Scheduled daily collection job at {settings.daily_collection_hour}:00 {tz_name}")

    # Add daily purge job
    scheduler.add_job(
        func=daily_purge_job,
        trigger=CronTrigger(hour=0, minute=0),  # Run at midnight daily
        id='daily_purge',
        name='Daily Data Purge',
        replace_existing=True
    )
    logger.info(f"Scheduled daily purge job (retention: {settings.intelligence_retention_days} days)")

    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started successfully")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully"""
    global scheduler

    if scheduler is not None:
        scheduler.shutdown(wait=True)
        scheduler = None
        logger.info("Scheduler shutdown complete")


def hourly_collection_job():
    """Hourly collection job - focuses on news updates"""
    logger.info("Running hourly collection job")
    try:
        run_collection()
    except Exception as e:
        logger.error(f"Hourly collection job failed: {e}", exc_info=True)


def daily_collection_job():
    """Daily comprehensive collection job - all sources"""
    logger.info("Running daily comprehensive collection job")
    try:
        run_collection()
    except Exception as e:
        logger.error(f"Daily collection job failed: {e}", exc_info=True)


def daily_purge_job():
    """Daily purge job - removes old intelligence items"""
    logger.info(f"Running daily purge job (retention: {settings.intelligence_retention_days} days)")
    try:
        purge_old_items()
    except Exception as e:
        logger.error(f"Daily purge job failed: {e}", exc_info=True)


def get_scheduler_status() -> dict:
    """Get current scheduler status and job information"""
    global scheduler

    if scheduler is None:
        return {
            'running': False,
            'jobs': []
        }

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        })

    return {
        'running': scheduler.running,
        'jobs': jobs
    }
