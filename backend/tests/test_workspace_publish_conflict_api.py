from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import crud, models, schemas
from api import workspaces as workspaces_api


def _build_test_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(workspaces_api, "SessionLocal", Session)
    monkeypatch.setattr(workspaces_api, "is_database_available", lambda: True)
    monkeypatch.setattr(workspaces_api, "create_tables", lambda: None)

    app = FastAPI()
    app.include_router(workspaces_api.router)
    return TestClient(app), Session


def _seed_workspace(db):
    workspace = crud.create_workspace(
        db,
        schemas.WorkspaceCreateRequest(
            name="Workspace API",
            schedule_by_day={
                "L": {
                    "schedule": [
                        {
                            "bus_id": "B001",
                            "items": [
                                {
                                    "route_id": "R001",
                                    "start_time": "08:00:00",
                                    "end_time": "09:00:00",
                                    "type": "entry",
                                }
                            ],
                        }
                    ]
                }
            },
        ),
    )
    return workspace


def test_publish_workspace_returns_409_on_fleet_conflict(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = _seed_workspace(db)
    finally:
        db.close()

    def _preview_blocked(*args, **kwargs):
        return {
            "blocked": True,
            "conflicts": [{"day": "L", "vehicle_id": "veh-001"}],
            "real_assigned": 1,
            "virtual_created": 0,
            "days": {"L": {"fleet_assigned": 1, "virtual_buses": 0}},
            "schedule_by_day": {"L": {"schedule": []}},
            "candidate_rows": [],
        }

    monkeypatch.setattr(workspaces_api, "preview_workspace_publication", _preview_blocked)

    response = client.post(f"/api/workspaces/{workspace.id}/publish", json={})
    assert response.status_code == 409
    payload = response.json()
    publication = payload["detail"]["fleet_publication"]
    assert publication["blocked"] is True
    assert len(publication["conflicts"]) == 1


def test_publish_workspace_persists_assignments_when_no_conflict(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = _seed_workspace(db)
    finally:
        db.close()

    def _preview_ok(db, company_id, schedule_by_day, exclude_workspace_id=None):
        return {
            "blocked": False,
            "conflicts": [],
            "real_assigned": 1,
            "virtual_created": 0,
            "days": {"L": {"fleet_assigned": 1, "virtual_buses": 0}},
            "schedule_by_day": schedule_by_day,
            "candidate_rows": [
                {
                    "day": "L",
                    "bus_id": "B001",
                    "route_id": "R001",
                    "start_minute": 8 * 60,
                    "end_minute": 9 * 60,
                    "assigned_vehicle_id": "veh-001",
                    "assignment_type": "real",
                }
            ],
        }

    monkeypatch.setattr(workspaces_api, "preview_workspace_publication", _preview_ok)

    response = client.post(
        f"/api/workspaces/{workspace.id}/publish",
        json={
            "save_kind": "publish",
            "schedule_by_day": {
                "L": {
                    "schedule": [
                        {
                            "bus_id": "B001",
                            "items": [
                                {
                                    "route_id": "R001",
                                    "start_time": "08:00:00",
                                    "end_time": "09:00:00",
                                    "type": "entry",
                                }
                            ],
                        }
                    ]
                }
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["save_kind"] == "publish"
    assert body["fleet_publication"]["blocked"] is False

    db = Session()
    try:
        hydrated = crud.get_workspace(db, str(workspace.id))
        assert hydrated is not None
        assert hydrated.published_version_id is not None
        rows = db.query(models.PublishedFleetAssignmentModel).filter(
            models.PublishedFleetAssignmentModel.workspace_id == str(workspace.id),
            models.PublishedFleetAssignmentModel.active.is_(True),
        ).all()
        assert len(rows) == 1
        assert rows[0].assigned_vehicle_id == "veh-001"
    finally:
        db.close()
