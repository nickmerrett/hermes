"""APScheduler job definitions and management"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import pytz
import os

from app.scheduler.collection import run_collection, purge_old_items
from app.config.settings import settings

logger = logging.getLogger(__name__)


def generate_daily_summaries():
    """Generate daily summaries for all customers"""
    from app.core.database import SessionLocal
    from app.models.database import Customer
    from app.services.daily_summary import generate_daily_summary

    logger.info("Running daily summary generation job")

    db = SessionLocal()
    try:
        customers = db.query(Customer).all()

        for customer in customers:
            try:
                # Call the service directly (no HTTP request needed)
                result = generate_daily_summary(
                    customer_id=customer.id,
                    db=db,
                    force_refresh=True
                )

                if result and not result.get('error'):
                    logger.info(f"Generated daily summary for {customer.name}")
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                    logger.warning(f"Failed to generate summary for {customer.name}: {error_msg}")

            except Exception as e:
                logger.error(f"Error generating summary for {customer.name}: {e}", exc_info=True)

        logger.info(f"Daily summary generation completed for {len(customers)} customers")

    except Exception as e:
        logger.error(f"Daily summary generation job failed: {e}", exc_info=True)
    finally:
        db.close()

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

    # Add periodic collection job - checks all sources and runs those due for collection
    # based on their configured intervals (runs every hour and checks which sources need to run)
    if settings.hourly_collection_enabled or settings.daily_collection_enabled:
        # Load collection days from platform settings
        collection_days = 'mon,tue,wed,thu,fri,sat,sun'  # Default: all days
        try:
            from app.core.database import SessionLocal
            from app.models.database import PlatformSettings

            db = SessionLocal()
            try:
                collection_settings = db.query(PlatformSettings).filter(
                    PlatformSettings.key == 'collection_config'
                ).first()

                if collection_settings and collection_settings.value.get('collection_days'):
                    days = collection_settings.value['collection_days']
                    if isinstance(days, list):
                        collection_days = ','.join(days)
                    else:
                        collection_days = days
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not load collection days: {e}, using default (all days)")

        scheduler.add_job(
            func=periodic_collection_job,
            trigger=CronTrigger(minute=0, day_of_week=collection_days),  # Run at the start of every hour on selected days
            id='periodic_collection',
            name='Periodic Collection Check',
            replace_existing=True
        )
        logger.info(f"Scheduled periodic collection job (checks all sources hourly on {collection_days})")

    # Add daily summary generation job (if enabled)
    try:
        from app.core.database import SessionLocal
        from app.models.database import PlatformSettings

        db = SessionLocal()
        try:
            briefing_settings = db.query(PlatformSettings).filter(
                PlatformSettings.key == 'daily_briefing'
            ).first()

            if briefing_settings and briefing_settings.value.get('schedule', {}).get('enabled', False):
                schedule = briefing_settings.value['schedule']
                hour = schedule.get('hour', 8)
                minute = schedule.get('minute', 0)

                # Get days of week (default: Monday-Friday)
                # Format: 'mon,tue,wed,thu,fri' or list ['mon', 'tue', 'wed', 'thu', 'fri']
                days_of_week = schedule.get('days_of_week', 'mon,tue,wed,thu,fri')
                if isinstance(days_of_week, list):
                    days_of_week = ','.join(days_of_week)

                scheduler.add_job(
                    func=generate_daily_summaries,
                    trigger=CronTrigger(hour=hour, minute=minute, day_of_week=days_of_week),
                    id='daily_summary_generation',
                    name='Daily Summary Generation',
                    replace_existing=True
                )
                logger.info(f"Scheduled daily summary generation at {hour:02d}:{minute:02d} on {days_of_week}")
            else:
                logger.info("Daily summary generation not scheduled (disabled in settings)")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not load daily summary schedule: {e}")

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


def periodic_collection_job():
    """
    Periodic collection job - runs every hour and checks which sources are due

    This job checks all sources and only collects from those where enough time
    has elapsed since their last collection based on their configured interval.
    Replaces the old hourly/daily job pattern with a unified time-based approach.
    """
    logger.info("Running periodic collection check")
    try:
        run_collection(collection_type='periodic')
    except Exception as e:
        logger.error(f"Periodic collection job failed: {e}", exc_info=True)


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
