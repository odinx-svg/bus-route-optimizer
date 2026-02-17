"""
SQLAlchemy models for Tutti database.

These models define the database schema for:
- Routes and stops
- Optimization jobs and results
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime,
    Boolean, ForeignKey, JSON, Time, Text
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY as PGARRAY
import uuid
from datetime import datetime

Base = declarative_base()


# Cross-database compatible types.
# PostgreSQL keeps native UUID/ARRAY, SQLite uses String/JSON fallback.
UUIDType = PGUUID(as_uuid=False).with_variant(String(36), "sqlite")
DaysArrayType = PGARRAY(String).with_variant(JSON, "sqlite")


class RouteModel(Base):
    """Ruta de autobús escolar"""
    __tablename__ = "routes"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'entry' or 'exit'
    school_id = Column(String, nullable=False)
    school_name = Column(String, nullable=False)
    arrival_time = Column(Time, nullable=True)
    departure_time = Column(Time, nullable=True)
    capacity_needed = Column(Integer, default=0)
    contract_id = Column(String, nullable=False)
    days = Column(DaysArrayType, default=list)  # ['L', 'M', 'X']
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    stops = relationship("StopModel", back_populates="route", cascade="all, delete-orphan")
    optimization_results = relationship("OptimizationResultModel", back_populates="route")

    def __repr__(self):
        return f"<RouteModel(id='{self.id}', name='{self.name}', type='{self.type}')>"


class StopModel(Base):
    """Parada de una ruta"""
    __tablename__ = "stops"

    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    route_id = Column(String, ForeignKey("routes.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    order = Column(Integer, nullable=False)
    time_from_start = Column(Integer, default=0)
    passengers = Column(Integer, default=0)
    is_school = Column(Boolean, default=False)

    route = relationship("RouteModel", back_populates="stops")

    def __repr__(self):
        return f"<StopModel(name='{self.name}', order={self.order})>"


class OptimizationJob(Base):
    """Job de optimización (para tracking async)"""
    __tablename__ = "optimization_jobs"

    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, default="pending")  # pending, running, completed, failed
    algorithm = Column(String, default="v6")  # v2, v4, v5, v6
    input_data = Column(JSON)  # Rutas de entrada
    result = Column(JSON)  # Schedule result
    stats = Column(JSON)  # Estadísticas de la optimización
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    results = relationship("OptimizationResultModel", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<OptimizationJob(id='{self.id}', status='{self.status}', algorithm='{self.algorithm}')>"


class OptimizationResultModel(Base):
    """Resultado: qué ruta va en qué bus para un job"""
    __tablename__ = "optimization_results"

    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(UUIDType, ForeignKey("optimization_jobs.id", ondelete="CASCADE"))
    route_id = Column(String, ForeignKey("routes.id", ondelete="SET NULL"))
    bus_id = Column(String, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    time_shift_minutes = Column(Integer, default=0)
    deadhead_minutes = Column(Integer, default=0)

    job = relationship("OptimizationJob", back_populates="results")
    route = relationship("RouteModel", back_populates="optimization_results")

    def __repr__(self):
        return f"<OptimizationResultModel(bus_id='{self.bus_id}', route_id='{self.route_id}')>"


class ManualScheduleModel(Base):
    """Horario manual/publicado persistido por día."""
    __tablename__ = "manual_schedules"

    day = Column(String, primary_key=True)  # L, M, Mc, X, V
    payload = Column(JSON, nullable=False)  # schedule_{day} serialized payload
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ManualScheduleModel(day='{self.day}', updated_at='{self.updated_at}')>"
