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
    # Skip directory creation in test mode (tests use in-memory SQLite)
    if not os.environ.get("TESTING"):
        # Ensure database directory exists
        db_path = settings.database_path
        db_dir = os.path.dirname(db_path)
        if db_dir:  # Only create if there's a directory component
            os.makedirs(db_dir, exist_ok=True)

    # Create engine
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        echo=settings.sql_echo,  # Log SQL only when SQL_ECHO=true
    )
    return engine


# Create engine and session factory (skip in test mode - tests create their own)
engine = None
SessionLocal = None

if not os.environ.get("TESTING"):
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _get_engine_and_session():
    """Lazy initialization of engine and session factory"""
    global engine, SessionLocal
    if engine is None:
        engine = get_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def init_db():
    """Initialize database by creating all tables"""
    eng, _ = _get_engine_and_session()
    # checkfirst=True ensures we don't try to create tables that already exist
    Base.metadata.create_all(bind=eng, checkfirst=True)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session
    Usage in FastAPI: db: Session = Depends(get_db)
    """
    _, session_local = _get_engine_and_session()
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def reset_db():
    """Drop and recreate all tables (use with caution!)"""
    eng, _ = _get_engine_and_session()
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
