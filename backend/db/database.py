"""
Database configuration and connection handling.

Supports both PostgreSQL and in-memory fallback mode.
Set USE_DATABASE=false to run without database (legacy mode).
"""

import os
import logging
from typing import Generator

from sqlalchemy import create_engine, inspect, text
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

DEFAULT_COMPANY_ID = "company_main"
DEFAULT_COMPANY_NAME = "Empresa Principal"


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
        if engine.dialect.name == "sqlite":
            _ensure_sqlite_schema_compatibility(engine)
        logger.info("Database tables created")


def drop_tables():
    """Drop all tables (use with caution!)."""
    if engine is not None:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped")


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if table_name not in table_names:
        return False
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def _add_column_if_missing(conn, table_name: str, column_name: str, ddl_type: str) -> bool:
    if _column_exists(conn, table_name, column_name):
        return False
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl_type}"))
    logger.info("[DB][SQLite] Added missing column %s.%s", table_name, column_name)
    return True


def _ensure_sqlite_schema_compatibility(sqlite_engine: Engine) -> None:
    """
    Apply lightweight idempotent schema patches for desktop SQLite databases.

    This avoids runtime crashes when users update from older desktop versions
    where SQLite tables were created before newer columns existed.
    """
    try:
        with sqlite_engine.begin() as conn:
            _add_column_if_missing(conn, "fleet_vehicles", "seats_base", "INTEGER")
            _add_column_if_missing(conn, "fleet_vehicles", "seats_pmr", "INTEGER DEFAULT 0")
            _add_column_if_missing(conn, "optimization_workspaces", "company_id", "VARCHAR(64)")

            # Backfill fleet seat derivations after adding new columns.
            if _column_exists(conn, "fleet_vehicles", "seats_base"):
                conn.execute(
                    text(
                        "UPDATE fleet_vehicles "
                        "SET seats_base = COALESCE(seats_base, seats_max, seats_min, 1)"
                    )
                )
            if _column_exists(conn, "fleet_vehicles", "seats_pmr"):
                conn.execute(
                    text(
                        "UPDATE fleet_vehicles "
                        "SET seats_pmr = COALESCE(seats_pmr, 0)"
                    )
                )
            if _column_exists(conn, "fleet_vehicles", "seats_min"):
                conn.execute(
                    text(
                        "UPDATE fleet_vehicles "
                        "SET seats_min = COALESCE(seats_min, seats_base, 1)"
                    )
                )
            if _column_exists(conn, "fleet_vehicles", "seats_max"):
                conn.execute(
                    text(
                        "UPDATE fleet_vehicles "
                        "SET seats_max = COALESCE(seats_max, seats_base + COALESCE(seats_pmr, 0), seats_min, 1)"
                    )
                )

            # Ensure default company and backfill workspace tenant relation.
            conn.execute(
                text(
                    "INSERT INTO companies (id, name, is_default, created_at, updated_at) "
                    "SELECT :id, :name, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
                    "WHERE NOT EXISTS (SELECT 1 FROM companies WHERE id = :id)"
                ),
                {"id": DEFAULT_COMPANY_ID, "name": DEFAULT_COMPANY_NAME},
            )
            if _column_exists(conn, "optimization_workspaces", "company_id"):
                conn.execute(
                    text(
                        "UPDATE optimization_workspaces "
                        "SET company_id = :id "
                        "WHERE company_id IS NULL OR company_id = ''"
                    ),
                    {"id": DEFAULT_COMPANY_ID},
                )
    except Exception as exc:
        logger.warning("[DB][SQLite] Schema compatibility patch failed: %s", exc)


# Initialize engine on module import
init_engine()
