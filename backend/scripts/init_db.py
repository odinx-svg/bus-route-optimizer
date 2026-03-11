#!/usr/bin/env python3
"""
Initialize Tutti database schema and backfills.

This script aligns runtime DB state with migrations and current SQLAlchemy models:
1. Connects to database
2. Runs Alembic migrations (PostgreSQL by default)
3. Ensures runtime tables exist (create_tables safety net)
4. Backfills default company/workspace company_id
5. Imports legacy fleet_profiles.json into relational fleet table when empty
6. Verifies required production tables
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List

from sqlalchemy import inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from db import crud as db_crud  # noqa: E402
from db import models as db_models  # noqa: E402
from db.database import (  # noqa: E402
    DATABASE_URL,
    SessionLocal,
    USE_DATABASE,
    create_tables,
    init_engine,
    is_database_available,
)
from services.fleet_repository import FleetRepository  # noqa: E402


REQUIRED_TABLES: List[str] = [
    "companies",
    "utes",
    "ute_members",
    "fleet_vehicles",
    "fleet_vehicle_documents",
    "published_fleet_assignments",
    "optimization_workspaces",
    "optimization_workspace_versions",
    "app_meta",
]


def _run_alembic_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    migrations_dir = BACKEND_ROOT / "db" / "migrations"
    alembic_ini = migrations_dir / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(cfg, "head")


def _run_backfill() -> None:
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        default_company = db_crud.ensure_default_company(db)
        updated = db.query(db_models.OptimizationWorkspaceModel).filter(
            (db_models.OptimizationWorkspaceModel.company_id.is_(None))
            | (db_models.OptimizationWorkspaceModel.company_id == "")
        ).update({"company_id": str(default_company.id)})
        db.commit()
        print(f"[backfill] default company ensured: {default_company.id}")
        print(f"[backfill] workspace company_id updated: {int(updated or 0)}")
    finally:
        db.close()

    repository = FleetRepository()
    result = repository.sync_json_fleet_into_db(company_id=db_crud.DEFAULT_COMPANY_ID)
    print(
        "[backfill] fleet import from JSON -> DB: "
        f"imported={int(result.get('imported', 0))}, skipped={int(result.get('skipped', 0))}"
    )


def _verify(engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing = [table for table in REQUIRED_TABLES if table not in tables]
    if missing:
        raise RuntimeError(f"Missing required tables: {', '.join(missing)}")
    print("[verify] required tables present")

    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        null_company_count = db.query(db_models.OptimizationWorkspaceModel).filter(
            (db_models.OptimizationWorkspaceModel.company_id.is_(None))
            | (db_models.OptimizationWorkspaceModel.company_id == "")
        ).count()
    finally:
        db.close()
    if int(null_company_count or 0) > 0:
        raise RuntimeError(
            f"Verification failed: {int(null_company_count)} workspaces without company_id"
        )
    print("[verify] workspace company_id consistency ok")


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize Tutti database schema")
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip Alembic migrations",
    )
    parser.add_argument(
        "--skip-backfill",
        action="store_true",
        help="Skip default company/workspace/fleet backfills",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip post-initialization verification checks",
    )
    args = parser.parse_args()

    print("=" * 68)
    print("Tutti DB initialization")
    print("=" * 68)
    print(f"DATABASE_URL={DATABASE_URL}")
    print(f"USE_DATABASE={USE_DATABASE}")

    if not USE_DATABASE:
        print("[info] USE_DATABASE=false. Skipping DB initialization.")
        return 0

    engine = init_engine()
    if engine is None or not is_database_available():
        print("[error] Database is not available.")
        return 1
    print("[ok] Database connection established")

    is_sqlite = DATABASE_URL.startswith("sqlite")
    is_sqlite_memory = is_sqlite and ":memory:" in DATABASE_URL
    if not args.skip_migrations:
        if is_sqlite:
            print("[info] SQLite detected: skipping Alembic and using create_tables fallback")
        else:
            try:
                _run_alembic_upgrade()
                print("[ok] Alembic upgrade head completed")
            except Exception as exc:
                print(f"[error] Alembic migration failed: {exc}")
                return 1
    else:
        print("[skip] Alembic migrations skipped by flag")

    try:
        create_tables()
        print("[ok] create_tables safety net completed")
    except Exception as exc:
        print(f"[error] create_tables failed: {exc}")
        return 1

    if is_sqlite_memory and not args.skip_backfill:
        print("[info] SQLite in-memory detected: skipping backfill phase")
    elif not args.skip_backfill:
        try:
            _run_backfill()
        except Exception as exc:
            print(f"[error] Backfill failed: {exc}")
            return 1
    else:
        print("[skip] Backfills skipped by flag")

    if not args.skip_verify:
        try:
            _verify(engine)
        except Exception as exc:
            print(f"[error] Verification failed: {exc}")
            return 1
    else:
        print("[skip] Verification skipped by flag")

    print("=" * 68)
    print("DB initialization completed successfully")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
