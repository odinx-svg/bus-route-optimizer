"""Add UTE schema and fleet seats base/pmr columns.

Revision ID: 004
Revises: 003
Create Date: 2026-03-11 18:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name
    now_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")
    uuid_type = postgresql.UUID(as_uuid=False) if dialect == "postgresql" else sa.String(36)

    if not _table_exists(inspector, "utes"):
        op.create_table(
            "utes",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("owner_company_id", sa.String(length=64), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.ForeignKeyConstraint(["owner_company_id"], ["companies.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_ute_name"),
        )
        op.create_index("ix_utes_owner_company_id", "utes", ["owner_company_id"])

    inspector = inspect(bind)
    if not _table_exists(inspector, "ute_members"):
        op.create_table(
            "ute_members",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("ute_id", sa.String(length=64), nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="partner"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now_default),
            sa.ForeignKeyConstraint(["ute_id"], ["utes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ute_id", "company_id", name="uq_ute_member"),
        )
        op.create_index("ix_ute_members_ute_id", "ute_members", ["ute_id"])
        op.create_index("ix_ute_members_company_id", "ute_members", ["company_id"])

    inspector = inspect(bind)
    if _table_exists(inspector, "fleet_vehicles") and not _column_exists(inspector, "fleet_vehicles", "seats_base"):
        op.add_column("fleet_vehicles", sa.Column("seats_base", sa.Integer(), nullable=True))

    inspector = inspect(bind)
    if _table_exists(inspector, "fleet_vehicles") and not _column_exists(inspector, "fleet_vehicles", "seats_pmr"):
        op.add_column("fleet_vehicles", sa.Column("seats_pmr", sa.Integer(), nullable=True))

    # Backfill seats_base/pmr from current seats_max and keep min/max consistency.
    if _table_exists(inspector, "fleet_vehicles"):
        bind.execute(sa.text("UPDATE fleet_vehicles SET seats_base = seats_max WHERE seats_base IS NULL"))
        bind.execute(sa.text("UPDATE fleet_vehicles SET seats_pmr = 0 WHERE seats_pmr IS NULL"))
        bind.execute(sa.text("UPDATE fleet_vehicles SET seats_min = seats_base WHERE seats_base IS NOT NULL"))
        bind.execute(sa.text("UPDATE fleet_vehicles SET seats_max = seats_base + COALESCE(seats_pmr, 0) WHERE seats_base IS NOT NULL"))

    inspector = inspect(bind)
    if _table_exists(inspector, "utes") and not _index_exists(inspector, "utes", "ix_utes_owner_company_id"):
        op.create_index("ix_utes_owner_company_id", "utes", ["owner_company_id"])
    inspector = inspect(bind)
    if _table_exists(inspector, "ute_members") and not _index_exists(inspector, "ute_members", "ix_ute_members_ute_id"):
        op.create_index("ix_ute_members_ute_id", "ute_members", ["ute_id"])
    inspector = inspect(bind)
    if _table_exists(inspector, "ute_members") and not _index_exists(inspector, "ute_members", "ix_ute_members_company_id"):
        op.create_index("ix_ute_members_company_id", "ute_members", ["company_id"])


def downgrade() -> None:
    # Conservative downgrade to avoid destructive data loss in mixed environments.
    pass
