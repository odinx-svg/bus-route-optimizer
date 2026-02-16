"""
Database module for Tutti backend.

This module provides PostgreSQL integration using SQLAlchemy.
It can be disabled by setting USE_DATABASE=false in environment variables.
"""

from .database import (
    get_db,
    SessionLocal,
    engine,
    Base,
    USE_DATABASE,
    is_database_available,
)
from .models import (
    RouteModel,
    StopModel,
    OptimizationJob,
    OptimizationResultModel,
    ManualScheduleModel,
)
from . import crud, schemas

__all__ = [
    "get_db",
    "SessionLocal",
    "engine",
    "Base",
    "USE_DATABASE",
    "is_database_available",
    "RouteModel",
    "StopModel",
    "OptimizationJob",
    "OptimizationResultModel",
    "ManualScheduleModel",
    "crud",
    "schemas",
]
