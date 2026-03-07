"""Add company/fleet publication schema and missing workspace tables.

Revision ID: 003
Revises: 002
Create Date: 2026-03-07 12:00:00.000000
"""

from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


DEFAULT_COMPANY_ID = "company_main"
DEFAULT_COMPANY_NAME = "Empresa Principal"


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def _fk_exists(inspector, table_name: str, constrained_columns: list[str], referred_table: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    for fk in inspector.get_foreign_keys(table_name):
        cols = fk.get("constrained_columns") or []
        ref = fk.get("referred_table")
        if list(cols) == list(constrained_columns) and ref == referred_table:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name

    uuid_type = postgresql.UUID(as_uuid=False) if dialect == "postgresql" else sa.String(36)
    json_type = postgresql.JSON() if dialect == "postgresql" else sa.JSON()
    now_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")

    if not _table_exists(inspector, "companies"):
        op.create_table(
            "companies",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.PrimaryKeyConstraint("id"),
        )

    # Ensure missing runtime tables exist even on old upgraded environments.
    if not _table_exists(inspector, "optimization_workspaces"):
        op.create_table(
            "optimization_workspaces",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("city_label", sa.String(), nullable=True),
            sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("published_version_id", uuid_type, nullable=True),
            sa.Column("working_version_id", uuid_type, nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = inspect(bind)
    if not _table_exists(inspector, "optimization_workspace_versions"):
        op.create_table(
            "optimization_workspace_versions",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("workspace_id", uuid_type, nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("save_kind", sa.String(), nullable=False, server_default="autosave"),
            sa.Column("checkpoint_name", sa.String(), nullable=True),
            sa.Column("routes_payload", json_type, nullable=False),
            sa.Column("schedule_by_day", json_type, nullable=False),
            sa.Column("parse_report", json_type, nullable=True),
            sa.Column("validation_report", json_type, nullable=True),
            sa.Column("fleet_snapshot", json_type, nullable=True),
            sa.Column("summary_metrics", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.ForeignKeyConstraint(["workspace_id"], ["optimization_workspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("workspace_id", "version_number", name="uq_workspace_version_number"),
        )
        op.create_index(
            "ix_optimization_workspace_versions_workspace_id",
            "optimization_workspace_versions",
            ["workspace_id"],
        )

    inspector = inspect(bind)
    if not _table_exists(inspector, "app_meta"):
        op.create_table(
            "app_meta",
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("value", json_type, nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.PrimaryKeyConstraint("key"),
        )

    inspector = inspect(bind)
    if _table_exists(inspector, "optimization_workspaces") and not _column_exists(inspector, "optimization_workspaces", "company_id"):
        op.add_column("optimization_workspaces", sa.Column("company_id", sa.String(length=64), nullable=True))
    inspector = inspect(bind)
    if _table_exists(inspector, "optimization_workspaces") and not _index_exists(inspector, "optimization_workspaces", "ix_optimization_workspaces_company_id"):
        op.create_index("ix_optimization_workspaces_company_id", "optimization_workspaces", ["company_id"])

    # Seed default company and backfill workspace company_id.
    bind.execute(
        sa.text(
            "INSERT INTO companies (id, name, is_default, created_at, updated_at) "
            "SELECT :id, :name, :is_default, :created_at, :updated_at "
            "WHERE NOT EXISTS (SELECT 1 FROM companies WHERE id = :id)"
        ),
        {
            "id": DEFAULT_COMPANY_ID,
            "name": DEFAULT_COMPANY_NAME,
            "is_default": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
    )
    if _table_exists(inspector, "optimization_workspaces"):
        bind.execute(
            sa.text(
                "UPDATE optimization_workspaces "
                "SET company_id = :id "
                "WHERE company_id IS NULL OR company_id = ''"
            ),
            {"id": DEFAULT_COMPANY_ID},
        )
        if dialect != "sqlite":
            try:
                op.alter_column("optimization_workspaces", "company_id", existing_type=sa.String(length=64), nullable=False)
            except Exception:
                pass
            inspector = inspect(bind)
            if not _fk_exists(inspector, "optimization_workspaces", ["company_id"], "companies"):
                try:
                    op.create_foreign_key(
                        "fk_optimization_workspaces_company_id",
                        "optimization_workspaces",
                        "companies",
                        ["company_id"],
                        ["id"],
                        ondelete="RESTRICT",
                    )
                except Exception:
                    pass

    inspector = inspect(bind)
    if not _table_exists(inspector, "fleet_vehicles"):
        op.create_table(
            "fleet_vehicles",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("vehicle_code", sa.String(length=32), nullable=False),
            sa.Column("plate", sa.String(length=32), nullable=False),
            sa.Column("brand", sa.String(length=80), nullable=True),
            sa.Column("model", sa.String(length=80), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("seats_min", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("seats_max", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("fuel_type", sa.String(length=32), nullable=True),
            sa.Column("accessibility", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("mileage_km", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("gps_provider", sa.String(length=64), nullable=True),
            sa.Column("gps_external_id", sa.String(length=120), nullable=True),
            sa.Column("gps_last_seen_at", sa.DateTime(), nullable=True),
            sa.Column("gps_last_position", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("company_id", "vehicle_code", name="uq_fleet_vehicle_company_code"),
            sa.UniqueConstraint("company_id", "plate", name="uq_fleet_vehicle_company_plate"),
        )
        op.create_index("ix_fleet_vehicles_company_id", "fleet_vehicles", ["company_id"])

    inspector = inspect(bind)
    if not _table_exists(inspector, "fleet_vehicle_documents"):
        op.create_table(
            "fleet_vehicle_documents",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("vehicle_id", uuid_type, nullable=False),
            sa.Column("doc_type", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("reference", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("issue_date", sa.String(length=32), nullable=True),
            sa.Column("expiry_date", sa.String(length=32), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.ForeignKeyConstraint(["vehicle_id"], ["fleet_vehicles.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_fleet_vehicle_documents_vehicle_id", "fleet_vehicle_documents", ["vehicle_id"])

    inspector = inspect(bind)
    if not _table_exists(inspector, "published_fleet_assignments"):
        op.create_table(
            "published_fleet_assignments",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("workspace_id", uuid_type, nullable=False),
            sa.Column("workspace_version_id", uuid_type, nullable=False),
            sa.Column("day", sa.String(length=8), nullable=False),
            sa.Column("bus_id", sa.String(length=64), nullable=False),
            sa.Column("route_id", sa.String(length=64), nullable=False),
            sa.Column("start_minute", sa.Integer(), nullable=False),
            sa.Column("end_minute", sa.Integer(), nullable=False),
            sa.Column("assigned_vehicle_id", sa.String(length=96), nullable=True),
            sa.Column("assignment_type", sa.String(length=16), nullable=False, server_default="virtual"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("metadata", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["workspace_id"], ["optimization_workspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["workspace_version_id"], ["optimization_workspace_versions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pfa_company_id", "published_fleet_assignments", ["company_id"])
        op.create_index("ix_pfa_workspace_id", "published_fleet_assignments", ["workspace_id"])
        op.create_index("ix_pfa_workspace_version_id", "published_fleet_assignments", ["workspace_version_id"])
        op.create_index("ix_pfa_day", "published_fleet_assignments", ["day"])
        op.create_index("ix_pfa_assigned_vehicle_id", "published_fleet_assignments", ["assigned_vehicle_id"])
        op.create_index("ix_pfa_active", "published_fleet_assignments", ["active"])


def downgrade() -> None:
    # Keep downgrade conservative to avoid destructive drops in mixed legacy deployments.
    pass
