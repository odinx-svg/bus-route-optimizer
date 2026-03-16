from io import BytesIO
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import fleet as fleet_api
from db import models
from services import fleet_repository as fleet_repo_module


def _build_test_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(fleet_api, "SessionLocal", Session)
    monkeypatch.setattr(fleet_api, "is_database_available", lambda: True)
    monkeypatch.setattr(fleet_repo_module, "SessionLocal", Session)
    monkeypatch.setattr(fleet_repo_module, "is_database_available", lambda: True)

    app = FastAPI()
    app.include_router(fleet_api.router)
    return TestClient(app), Session


def _build_excel_file():
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "AAV & COND'BUS"
    ws1.append(["MATRICULA", "PLAZAS"])
    ws1.append(["1111AAA", "55+1+1"])
    ws1.append(["2222BBB", "50"])

    ws2 = wb.create_sheet("MELYTOUR")
    ws2.append(["MATRICULA", "PLAZAS"])
    ws2.append(["3333CCC", "47"])

    payload = BytesIO()
    wb.save(payload)
    payload.seek(0)
    return payload


def test_fleet_import_preview_endpoint(monkeypatch):
    client, _ = _build_test_client(monkeypatch)
    fileobj = _build_excel_file()

    response = client.post(
        "/api/fleet/import/preview",
        files={"file": ("fleet.xlsx", fileobj.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["sheet_names"]) == 2
    assert len(body["sheets"]) == 2
    first = body["sheets"][0]
    assert first["header_detected"] is True
    assert first["valid_rows"] == 2


def test_fleet_import_commit_and_ute_catalog_endpoints(monkeypatch):
    client, Session = _build_test_client(monkeypatch)
    fileobj = _build_excel_file()

    response = client.post(
        "/api/fleet/import/commit",
        files={"file": ("fleet.xlsx", fileobj.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={
            "primary_sheet_name": "AAV & COND'BUS",
            "ute_name": "UTE API Test",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["companies_count"] == 2
    assert body["total_created"] == 3
    assert body["ute_name"] == "UTE API Test"

    list_response = client.get("/api/fleet/utes")
    assert list_response.status_code == 200
    utes = list_response.json()
    assert len(utes) == 1
    assert utes[0]["name"] == "UTE API Test"
    assert len(utes[0]["members"]) == 2

    db = Session()
    try:
        assert db.query(models.FleetVehicleModel).count() == 3
    finally:
        db.close()

    vehicles_response = client.get("/api/fleet/vehicles")
    assert vehicles_response.status_code == 200
    vehicles_body = vehicles_response.json()
    assert len(vehicles_body["vehicles"]) == 3


def test_vehicle_weekly_plan_endpoint(monkeypatch):
    client, Session = _build_test_client(monkeypatch)
    db = Session()
    try:
        company = models.CompanyModel(id="company_a", name="AAV & COND'BUS", is_default=False)
        db.add(company)
        driver = models.DriverModel(
            id=str(uuid4()),
            company_id="company_a",
            full_name="Juan Perez",
            phone="600111222",
            preferred_channel="whatsapp",
            status="active",
        )
        workspace = models.OptimizationWorkspaceModel(
            id=str(uuid4()),
            name="Vigo - Mos",
            company_id="company_a",
            working_version_id=None,
            published_version_id=None,
            archived=False,
        )
        version = models.OptimizationWorkspaceVersionModel(
            id=str(uuid4()),
            workspace_id=str(workspace.id),
            version_number=1,
            save_kind="publish",
            routes_payload=[],
            schedule_by_day={"L": {"schedule": []}},
            fleet_snapshot={},
            summary_metrics={},
        )
        vehicle = models.FleetVehicleModel(
            id="veh-a-1",
            company_id="company_a",
            vehicle_code="BUS-A1",
            plate="1234ABC",
            seats_base=55,
            seats_pmr=0,
            seats_min=55,
            seats_max=55,
            status="active",
        )
        driver_assignment = models.FleetVehicleDriverAssignmentModel(
            id=str(uuid4()),
            vehicle_id="veh-a-1",
            driver_id=str(driver.id),
            day_code="default",
        )
        assignment = models.PublishedFleetAssignmentModel(
            id=str(uuid4()),
            company_id="company_a",
            workspace_id=str(workspace.id),
            workspace_version_id=str(version.id),
            day="L",
            bus_id="B001",
            route_id="R001",
            start_minute=480,
            end_minute=540,
            assigned_vehicle_id="veh-a-1",
            assignment_type="real",
            active=True,
            details={},
        )
        db.add_all([company, driver, workspace, version, vehicle, driver_assignment, assignment])
        db.commit()
    finally:
        db.close()

    response = client.get("/api/fleet/vehicles/veh-a-1/weekly-plan")
    assert response.status_code == 200
    body = response.json()
    assert body["vehicle_code"] == "BUS-A1"
    assert body["plate"] == "1234ABC"
    assert body["total_assignments"] == 1
    assert body["default_driver_name"] == "Juan Perez"
    monday = next(day for day in body["days"] if day["day"] == "L")
    assert monday["route_count"] == 1
    assert monday["assignments"][0]["workspace_name"] == "Vigo - Mos"
    assert monday["assignments"][0]["start_time"] == "08:00"
    assert monday["assignments"][0]["driver_name"] == "Juan Perez"


def test_driver_crud_and_vehicle_assignment_endpoint(monkeypatch):
    client, Session = _build_test_client(monkeypatch)
    db = Session()
    try:
        company = models.CompanyModel(id="company_a", name="AAV & COND'BUS", is_default=False)
        vehicle = models.FleetVehicleModel(
            id="veh-a-1",
            company_id="company_a",
            vehicle_code="BUS-A1",
            plate="1234ABC",
            seats_base=55,
            seats_pmr=0,
            seats_min=55,
            seats_max=55,
            status="active",
        )
        db.add_all([company, vehicle])
        db.commit()
    finally:
        db.close()

    create_response = client.post(
        "/api/fleet/drivers",
        json={
            "company_id": "company_a",
            "full_name": "Laura Diaz",
            "phone": "699000111",
            "email": "laura@example.com",
            "preferred_channel": "telegram",
            "telegram_chat_id": "driver_laura",
            "status": "active",
            "notes": "Conduce lunes y martes",
        },
    )
    assert create_response.status_code == 201
    driver = create_response.json()
    assert driver["full_name"] == "Laura Diaz"

    list_response = client.get("/api/fleet/drivers?company_id=company_a")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1

    assign_response = client.put(
        "/api/fleet/vehicles/veh-a-1/drivers",
        json={
            "default_driver_id": driver["id"],
            "assignments": [
                {"day_code": "L", "driver_id": driver["id"]},
                {"day_code": "M", "driver_id": driver["id"]},
            ],
        },
    )
    assert assign_response.status_code == 200
    assigned = assign_response.json()
    assert assigned["default_driver_name"] == "Laura Diaz"
    assert len(assigned["driver_assignments"]) == 3

    vehicle_response = client.get("/api/fleet/vehicles/veh-a-1")
    assert vehicle_response.status_code == 200
    vehicle_body = vehicle_response.json()
    assert vehicle_body["default_driver_name"] == "Laura Diaz"
    assert len(vehicle_body["driver_assignments"]) == 3
