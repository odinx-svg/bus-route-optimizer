"""
Database configuration and connection handling.

Supports both PostgreSQL and in-memory fallback mode.
Set USE_DATABASE=false to run without database (legacy mode).
"""

import os
import logging
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base

logger = logging.getLogger(__name__)

# Feature flag: enable/disable database
USE_DATABASE = os.getenv("USE_DATABASE", "true").lower() in ("true", "1", "yes", "on")

# Database URL (PostgreSQL default)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://tutti:tutti@localhost:5432/tutti"
)

# Global engine instance
engine: Engine | None = None
SessionLocal = None


def init_engine() -> Engine | None:
    """Initialize database engine if database is enabled."""
    global engine, SessionLocal
    
    if not USE_DATABASE:
        logger.info("Database is disabled (USE_DATABASE=false)")
        return None
    
    try:
        is_sqlite = DATABASE_URL.startswith("sqlite")
        engine_kwargs = {
            "echo": os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
        }

        if is_sqlite:
            # SQLite local mode (desktop): thread-safe access for FastAPI workers.
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            engine_kwargs["pool_pre_ping"] = True
        else:
            # PostgreSQL mode.
            engine_kwargs["pool_pre_ping"] = True
            engine_kwargs["pool_size"] = 5
            engine_kwargs["max_overflow"] = 10
            engine_kwargs["pool_recycle"] = 3600  # Recycle connections after 1 hour

        new_engine = create_engine(DATABASE_URL, **engine_kwargs)
        
        # Test connection
        with new_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        engine = new_engine
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        logger.info(f"Database connected: {DATABASE_URL.split('@')[-1]}")
        return engine
        
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        logger.warning("Running in fallback mode (no database persistence)")
        engine = None
        SessionLocal = None
        return None


def is_database_available() -> bool:
    """Check if database is available for use."""
    if not USE_DATABASE:
        return False
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_db() -> Generator[Session | None, None, None]:
    """
    Dependency for FastAPI to get database session.
    
    Yields None if database is disabled or unavailable.
    Usage: db: Session = Depends(get_db)
    """
    if not USE_DATABASE or SessionLocal is None:
        yield None
        return
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables (for initial setup)."""
    if engine is not None:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")


def drop_tables():
    """Drop all tables (use with caution!)."""
    if engine is not None:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped")


# Initialize engine on module import
init_engine()
