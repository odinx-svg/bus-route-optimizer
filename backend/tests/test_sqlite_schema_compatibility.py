from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from db import database as db_database


def test_create_tables_applies_sqlite_compatibility_patch(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE companies (
                    id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    is_default BOOLEAN,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE optimization_workspaces (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    archived BOOLEAN,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE fleet_vehicles (
                    id VARCHAR(36) PRIMARY KEY,
                    company_id VARCHAR(64),
                    vehicle_code VARCHAR(32),
                    plate VARCHAR(32),
                    seats_min INTEGER,
                    seats_max INTEGER,
                    status VARCHAR(32),
                    accessibility BOOLEAN,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO optimization_workspaces (id, name, archived, created_at, updated_at)
                VALUES ('ws_1', 'Workspace legacy', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO fleet_vehicles (
                    id, company_id, vehicle_code, plate, seats_min, seats_max, status, accessibility, created_at, updated_at
                ) VALUES (
                    'veh_1', 'company_legacy', 'BUS-01', '1111AAA', 50, 55, 'active', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            )
        )

    monkeypatch.setattr(db_database, "engine", engine)
    db_database.create_tables()

    with engine.connect() as conn:
        inspector = inspect(conn)
        fleet_cols = {col["name"] for col in inspector.get_columns("fleet_vehicles")}
        workspace_cols = {col["name"] for col in inspector.get_columns("optimization_workspaces")}

        assert "seats_base" in fleet_cols
        assert "seats_pmr" in fleet_cols
        assert "company_id" in workspace_cols

        seats = conn.execute(
            text(
                "SELECT seats_min, seats_max, seats_base, seats_pmr "
                "FROM fleet_vehicles WHERE id = 'veh_1'"
            )
        ).first()
        assert seats is not None
        assert int(seats.seats_base or 0) == 55
        assert int(seats.seats_pmr or 0) == 0

        company = conn.execute(
            text("SELECT id FROM companies WHERE id = :id"),
            {"id": db_database.DEFAULT_COMPANY_ID},
        ).first()
        assert company is not None

        workspace_company = conn.execute(
            text("SELECT company_id FROM optimization_workspaces WHERE id = 'ws_1'")
        ).first()
        assert workspace_company is not None
        assert str(workspace_company.company_id) == db_database.DEFAULT_COMPANY_ID

