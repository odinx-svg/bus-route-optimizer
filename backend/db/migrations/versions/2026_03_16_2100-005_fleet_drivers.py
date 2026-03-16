"""Add fleet drivers and recurring vehicle-driver assignments.

Revision ID: 005
Revises: 004
Create Date: 2026-03-16 21:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name
    now_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")
    uuid_type = postgresql.UUID(as_uuid=False) if dialect == "postgresql" else sa.String(36)

    if not _table_exists(inspector, "fleet_drivers"):
        op.create_table(
            "fleet_drivers",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("full_name", sa.String(length=120), nullable=False),
            sa.Column("phone", sa.String(length=40), nullable=True),
            sa.Column("email", sa.String(length=120), nullable=True),
            sa.Column("preferred_channel", sa.String(length=32), nullable=False, server_default="manual"),
            sa.Column("whatsapp_phone", sa.String(length=40), nullable=True),
            sa.Column("telegram_chat_id", sa.String(length=120), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_fleet_drivers_company_id", "fleet_drivers", ["company_id"])

    inspector = inspect(bind)
    if not _table_exists(inspector, "fleet_vehicle_driver_assignments"):
        op.create_table(
            "fleet_vehicle_driver_assignments",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("vehicle_id", uuid_type, nullable=False),
            sa.Column("driver_id", uuid_type, nullable=False),
            sa.Column("day_code", sa.String(length=16), nullable=False, server_default="default"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.ForeignKeyConstraint(["vehicle_id"], ["fleet_vehicles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["driver_id"], ["fleet_drivers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("vehicle_id", "day_code", name="uq_vehicle_driver_assignment_day"),
        )
        op.create_index("ix_fleet_vehicle_driver_assignments_vehicle_id", "fleet_vehicle_driver_assignments", ["vehicle_id"])
        op.create_index("ix_fleet_vehicle_driver_assignments_driver_id", "fleet_vehicle_driver_assignments", ["driver_id"])

    inspector = inspect(bind)
    if _table_exists(inspector, "fleet_drivers") and not _index_exists(inspector, "fleet_drivers", "ix_fleet_drivers_company_id"):
        op.create_index("ix_fleet_drivers_company_id", "fleet_drivers", ["company_id"])

    inspector = inspect(bind)
    if _table_exists(inspector, "fleet_vehicle_driver_assignments") and not _index_exists(inspector, "fleet_vehicle_driver_assignments", "ix_fleet_vehicle_driver_assignments_vehicle_id"):
        op.create_index("ix_fleet_vehicle_driver_assignments_vehicle_id", "fleet_vehicle_driver_assignments", ["vehicle_id"])
    inspector = inspect(bind)
    if _table_exists(inspector, "fleet_vehicle_driver_assignments") and not _index_exists(inspector, "fleet_vehicle_driver_assignments", "ix_fleet_vehicle_driver_assignments_driver_id"):
        op.create_index("ix_fleet_vehicle_driver_assignments_driver_id", "fleet_vehicle_driver_assignments", ["driver_id"])


def downgrade() -> None:
    pass
