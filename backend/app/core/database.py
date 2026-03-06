"""Database connection and session management"""

from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from typing import Generator
import logging
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
        pool_pre_ping=True,  # Verify connection health before use
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


def _migrate_add_missing_columns(eng):
    """Add columns that exist in models but not yet in the database.

    SQLAlchemy's create_all(checkfirst=True) creates new tables but does NOT
    add new columns to existing tables. This function inspects each table and
    adds any missing columns using ALTER TABLE.
    """
    logger = logging.getLogger(__name__)
    inspector = inspect(eng)

    with eng.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if not inspector.has_table(table_name):
                continue  # Table doesn't exist yet; create_all will handle it

            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}

            for column in table.columns:
                if column.name not in existing_columns:
                    # Build ALTER TABLE statement
                    col_type = column.type.compile(eng.dialect)
                    default_clause = ""
                    if column.default is not None:
                        default_val = column.default.arg
                        if callable(default_val):
                            default_clause = ""  # Skip callable defaults (handled by ORM)
                        elif isinstance(default_val, str):
                            default_clause = f" DEFAULT '{default_val}'"
                        else:
                            default_clause = f" DEFAULT {default_val}"
                    elif column.server_default is not None:
                        default_clause = f" DEFAULT {column.server_default.arg}"

                    sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}{default_clause}"
                    logger.info(f"Migration: adding column {table_name}.{column.name} ({col_type})")
                    conn.execute(text(sql))


def init_db():
    """Initialize database by creating all tables and adding missing columns"""
    eng, _ = _get_engine_and_session()
    # Add any missing columns to existing tables first
    _migrate_add_missing_columns(eng)
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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reset_db():
    """Drop and recreate all tables (use with caution!)"""
    eng, _ = _get_engine_and_session()
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
