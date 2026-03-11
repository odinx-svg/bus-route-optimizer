"""
SQLAlchemy models for Tutti database.

These models define the database schema for:
- Routes and stops
- Optimization jobs and results
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime,
    Boolean, ForeignKey, JSON, Time, Text, UniqueConstraint
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


class CompanyModel(Base):
    """Logical tenant/company for fleet + workspaces."""
    __tablename__ = "companies"

    id = Column(String(64), primary_key=True)
    name = Column(String, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    fleet_vehicles = relationship(
        "FleetVehicleModel",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    owned_utes = relationship(
        "UTEModel",
        back_populates="owner_company",
        cascade="all, delete-orphan",
    )
    ute_memberships = relationship(
        "UTEMemberModel",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    workspaces = relationship(
        "OptimizationWorkspaceModel",
        back_populates="company",
    )

    def __repr__(self):
        return f"<CompanyModel(id='{self.id}', name='{self.name}', is_default={self.is_default})>"


class FleetVehicleModel(Base):
    """Fleet vehicle persisted in database (DB-first fleet repository)."""
    __tablename__ = "fleet_vehicles"
    __table_args__ = (
        UniqueConstraint("company_id", "vehicle_code", name="uq_fleet_vehicle_company_code"),
        UniqueConstraint("company_id", "plate", name="uq_fleet_vehicle_company_plate"),
    )

    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(64), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_code = Column(String(32), nullable=False)
    plate = Column(String(32), nullable=False)
    brand = Column(String(80), nullable=True)
    model = Column(String(80), nullable=True)
    year = Column(Integer, nullable=True)
    seats_base = Column(Integer, nullable=True)
    seats_pmr = Column(Integer, nullable=True, default=0)
    seats_min = Column(Integer, nullable=False, default=1)
    seats_max = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="active")
    fuel_type = Column(String(32), nullable=True)
    accessibility = Column(Boolean, nullable=False, default=False)
    mileage_km = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    gps_provider = Column(String(64), nullable=True)
    gps_external_id = Column(String(120), nullable=True)
    gps_last_seen_at = Column(DateTime, nullable=True)
    gps_last_position = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("CompanyModel", back_populates="fleet_vehicles")
    documents = relationship(
        "FleetVehicleDocumentModel",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<FleetVehicleModel(id='{self.id}', code='{self.vehicle_code}', plate='{self.plate}')>"


class UTEModel(Base):
    """UTE (Union Temporal de Empresas) grouping companies for joint fleet scope."""
    __tablename__ = "utes"
    __table_args__ = (
        UniqueConstraint("name", name="uq_ute_name"),
    )

    id = Column(String(64), primary_key=True)
    name = Column(String(120), nullable=False)
    owner_company_id = Column(String(64), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner_company = relationship("CompanyModel", back_populates="owned_utes")
    members = relationship(
        "UTEMemberModel",
        back_populates="ute",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<UTEModel(id='{self.id}', name='{self.name}', owner='{self.owner_company_id}')>"


class UTEMemberModel(Base):
    """Company membership in a UTE."""
    __tablename__ = "ute_members"
    __table_args__ = (
        UniqueConstraint("ute_id", "company_id", name="uq_ute_member"),
    )

    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    ute_id = Column(String(64), ForeignKey("utes.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String(64), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False, default="partner")  # owner|partner
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    ute = relationship("UTEModel", back_populates="members")
    company = relationship("CompanyModel", back_populates="ute_memberships")

    def __repr__(self):
        return f"<UTEMemberModel(ute='{self.ute_id}', company='{self.company_id}', role='{self.role}')>"


class FleetVehicleDocumentModel(Base):
    """Documents associated with a fleet vehicle."""
    __tablename__ = "fleet_vehicle_documents"

    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = Column(
        UUIDType,
        ForeignKey("fleet_vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type = Column(String(80), nullable=False, default="")
    reference = Column(String(120), nullable=False, default="")
    issue_date = Column(String(32), nullable=True)
    expiry_date = Column(String(32), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    vehicle = relationship("FleetVehicleModel", back_populates="documents")

    def __repr__(self):
        return f"<FleetVehicleDocumentModel(id='{self.id}', vehicle_id='{self.vehicle_id}', type='{self.doc_type}')>"


class OptimizationWorkspaceModel(Base):
    """Optimization workspace root entity (draft/active/archive)."""
    __tablename__ = "optimization_workspaces"

    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(
        String(64),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    city_label = Column(String, nullable=True)
    archived = Column(Boolean, nullable=False, default=False)
    published_version_id = Column(
        UUIDType,
        ForeignKey("optimization_workspace_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    working_version_id = Column(
        UUIDType,
        ForeignKey("optimization_workspace_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    versions = relationship(
        "OptimizationWorkspaceVersionModel",
        back_populates="workspace",
        foreign_keys="OptimizationWorkspaceVersionModel.workspace_id",
        cascade="all, delete-orphan",
        order_by="OptimizationWorkspaceVersionModel.version_number",
    )
    published_version = relationship(
        "OptimizationWorkspaceVersionModel",
        foreign_keys=[published_version_id],
        post_update=True,
    )
    working_version = relationship(
        "OptimizationWorkspaceVersionModel",
        foreign_keys=[working_version_id],
        post_update=True,
    )
    company = relationship("CompanyModel", back_populates="workspaces")

    def __repr__(self):
        return (
            f"<OptimizationWorkspaceModel(id='{self.id}', name='{self.name}', "
            f"archived={self.archived})>"
        )


class OptimizationWorkspaceVersionModel(Base):
    """Immutable version snapshot for workspace save/publish/autosave."""
    __tablename__ = "optimization_workspace_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "version_number", name="uq_workspace_version_number"),
    )

    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        UUIDType,
        ForeignKey("optimization_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    save_kind = Column(String, nullable=False, default="autosave")  # autosave|save|publish|migration
    checkpoint_name = Column(String, nullable=True)
    routes_payload = Column(JSON, nullable=False, default=list)
    schedule_by_day = Column(JSON, nullable=False, default=dict)
    parse_report = Column(JSON, nullable=True)
    validation_report = Column(JSON, nullable=True)
    fleet_snapshot = Column(JSON, nullable=True)
    summary_metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workspace = relationship(
        "OptimizationWorkspaceModel",
        back_populates="versions",
        foreign_keys=[workspace_id],
    )

    def __repr__(self):
        return (
            f"<OptimizationWorkspaceVersionModel(id='{self.id}', workspace_id='{self.workspace_id}', "
            f"version={self.version_number}, save_kind='{self.save_kind}')>"
        )


class PublishedFleetAssignmentModel(Base):
    """
    Operational fleet reservations created only on workspace publish.
    One row per route assignment interval.
    """
    __tablename__ = "published_fleet_assignments"

    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(64), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(
        UUIDType,
        ForeignKey("optimization_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_version_id = Column(
        UUIDType,
        ForeignKey("optimization_workspace_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day = Column(String(8), nullable=False, index=True)
    bus_id = Column(String(64), nullable=False)
    route_id = Column(String(64), nullable=False)
    start_minute = Column(Integer, nullable=False)
    end_minute = Column(Integer, nullable=False)
    assigned_vehicle_id = Column(String(96), nullable=True, index=True)
    assignment_type = Column(String(16), nullable=False, default="virtual")  # real|virtual
    active = Column(Boolean, nullable=False, default=True, index=True)
    details = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<PublishedFleetAssignmentModel(id='{self.id}', workspace_id='{self.workspace_id}', "
            f"day='{self.day}', vehicle='{self.assigned_vehicle_id}', active={self.active})>"
        )


class AppMetaModel(Base):
    """Generic key/value table for migration flags and app preferences."""
    __tablename__ = "app_meta"

    key = Column(String, primary_key=True)
    value = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AppMetaModel(key='{self.key}')>"
