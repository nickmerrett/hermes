"""Main FastAPI application"""

import os
# Suppress HuggingFace tokenizers parallelism warning when using multiprocessing/forking
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
# Disable ChromaDB telemetry to suppress posthog errors
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

# ChromaDB 0.5.x has a broken posthog capture() call — patch it out entirely
try:
    import chromadb.telemetry.product.posthog as _chroma_ph
    _chroma_ph.Posthog.capture = lambda *a, **kw: None
except Exception:
    pass

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy import text
from contextlib import asynccontextmanager
import logging
from datetime import datetime
import json

from app.config.settings import settings
from app.core.database import init_db, get_db

# Rate limiter (keyed by client IP)
limiter = Limiter(key_func=get_remote_address)
from app.core.vector_store import get_vector_store
from app.models import schemas
from app.api import customers, feed, sources, jobs, search, analytics, customer_research, settings as settings_api, testing, gmail, executive_relationship, auth, rss
from app import __version__

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Quiet SQLAlchemy logging unless explicitly enabled via SQL_ECHO=true
# Even in development, SQL logging is too verbose for normal use
if not settings.sql_echo:
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)


def _assign_legacy_customer_ownership():
    """One-time idempotent migration: assign ownerless customers to the first platform admin."""
    from app.models.database import Customer, User
    from app.models.auth_schemas import UserRole
    from app.core.database import _get_engine_and_session
    _, session_local = _get_engine_and_session()
    db = session_local()
    try:
        unowned_count = db.query(Customer).filter(Customer.owner_id.is_(None)).count()
        if unowned_count == 0:
            return
        admin = db.query(User).filter(
            User.role == UserRole.PLATFORM_ADMIN.value,
            User.is_active.is_(True)
        ).order_by(User.id).first()
        if not admin:
            logger.warning("No active platform admin found — skipping legacy ownership migration")
            return
        db.query(Customer).filter(Customer.owner_id.is_(None)).update(
            {Customer.owner_id: admin.id}, synchronize_session=False
        )
        db.commit()
        logger.info(f"Assigned {unowned_count} legacy customers to admin {admin.email} (id={admin.id})")
    except Exception as e:
        db.rollback()
        logger.error(f"Legacy ownership migration failed: {e}", exc_info=True)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Hermes...")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Assign unowned customers to first platform admin (idempotent)
    _assign_legacy_customer_ownership()
    logger.info("Customer ownership migration complete")

    # Initialize vector store
    vector_store = get_vector_store()
    logger.info(f"Vector store initialized with {vector_store.get_item_count()} items")

    # Initialize scheduler if enabled
    if settings.enable_scheduler:
        from app.scheduler.jobs import start_scheduler
        start_scheduler()
        logger.info("Scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if settings.enable_scheduler:
        from app.scheduler.jobs import shutdown_scheduler
        shutdown_scheduler()


# Custom JSON encoder to handle datetime serialization with UTC timezone
class CustomJSONResponse(JSONResponse):
    """Custom JSON response that ensures datetimes are serialized as UTC with 'Z' suffix"""

    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=self.datetime_encoder
        ).encode("utf-8")

    @staticmethod
    def datetime_encoder(obj):
        """Encode datetime objects as ISO 8601 with 'Z' suffix for UTC"""
        if isinstance(obj, datetime):
            # If datetime is naive (no timezone), assume it's UTC and add 'Z' suffix
            if obj.tzinfo is None:
                return obj.isoformat() + 'Z'
            # If datetime has timezone, convert to UTC and add 'Z' suffix
            utc_dt = obj.astimezone(None)
            return utc_dt.isoformat().replace('+00:00', 'Z')
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# Create FastAPI app (docs disabled in production)
app = FastAPI(
    title="Hermes",
    description="Automated customer intelligence aggregation and analysis platform",
    version=__version__,
    lifespan=lifespan,
    default_response_class=CustomJSONResponse,  # Use custom JSON response
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(rss.router, prefix="/api/rss", tags=["rss"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(feed.router, prefix="/api/feed", tags=["feed"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(customer_research.router, prefix="/api/customer-research", tags=["customer-research"])
app.include_router(settings_api.router, prefix="/api", tags=["settings"])
app.include_router(testing.router, prefix="/api/testing", tags=["testing"])
app.include_router(gmail.router, prefix="/api", tags=["gmail"])
app.include_router(executive_relationship.router, prefix="/api", tags=["executives"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Hermes",
        "version": __version__,
        "status": "running"
    }


@app.get("/api/health", response_model=schemas.HealthCheck)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Check database
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    # Check scheduler
    scheduler_status = "enabled" if settings.enable_scheduler else "disabled"

    return schemas.HealthCheck(
        status="healthy" if db_status == "healthy" else "degraded",
        version=__version__,
        database=db_status,
        scheduler=scheduler_status
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development
    )
