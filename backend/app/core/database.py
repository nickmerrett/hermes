"""Database connection and session management"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from typing import Generator
import os

from app.config.settings import settings
from app.models.database import Base


# Enable foreign key constraints and WAL mode for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key support and WAL mode in SQLite for better concurrency"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")  # Enable Write-Ahead Logging for concurrent access
    cursor.execute("PRAGMA busy_timeout=5000")  # Wait up to 5 seconds for locks
    cursor.close()


def get_engine():
    """Create database engine"""
    # Ensure database directory exists
    db_path = settings.database_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Create engine
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        echo=settings.is_development,  # Log SQL in development
    )
    return engine


# Create engine and session factory
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database by creating all tables"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session
    Usage in FastAPI: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_db():
    """Drop and recreate all tables (use with caution!)"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
