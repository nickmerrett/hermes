"""Main FastAPI application"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from contextlib import asynccontextmanager
import logging
from typing import List, Optional

from app.config.settings import settings
from app.core.database import init_db, get_db
from app.core.vector_store import get_vector_store
from app.models import schemas
from app.api import customers, feed, sources, jobs, search, analytics, customer_research, settings as settings_api
from app import __version__

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Hermes...")

    # Initialize database
    init_db()
    logger.info("Database initialized")

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


# Create FastAPI app
app = FastAPI(
    title="Hermes",
    description="Automated customer intelligence aggregation and analysis platform",
    version=__version__,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(feed.router, prefix="/api/feed", tags=["feed"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(customer_research.router, prefix="/api/customer-research", tags=["customer-research"])
app.include_router(settings_api.router, prefix="/api", tags=["settings"])


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
