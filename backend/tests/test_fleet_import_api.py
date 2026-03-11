from io import BytesIO

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

