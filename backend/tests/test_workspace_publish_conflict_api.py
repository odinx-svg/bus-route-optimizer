from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import workspaces as workspaces_api
from db import crud, models, schemas


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
    return crud.create_workspace(
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

    def _preview_ok(db, company_id, schedule_by_day, exclude_workspace_id=None, scope_company_ids=None):
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


def test_publish_workspace_passes_ute_scope_company_ids(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = _seed_workspace(db)
    finally:
        db.close()

    monkeypatch.setattr(
        workspaces_api,
        "resolve_workspace_fleet_scope",
        lambda db, workspace: {
            "scope_mode": "ute",
            "scope_company_ids": ["company_main", "company_partner"],
            "primary_company_id": "company_main",
            "ute_id": "ute_demo",
            "ute_name": "UTE Demo",
        },
    )

    captured = {}

    def _preview_blocked(db, company_id, scope_company_ids, schedule_by_day, exclude_workspace_id=None):
        captured["company_id"] = company_id
        captured["scope_company_ids"] = list(scope_company_ids or [])
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
    body = response.json()
    fleet_publication = body["detail"]["fleet_publication"]
    assert fleet_publication["scope_mode"] == "ute"
    assert fleet_publication["scope_company_ids"] == ["company_main", "company_partner"]
    assert captured["company_id"] == "company_main"
    assert captured["scope_company_ids"] == ["company_main", "company_partner"]


def test_fleet_preview_respects_ute_scope(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = _seed_workspace(db)
    finally:
        db.close()

    monkeypatch.setattr(
        workspaces_api,
        "resolve_workspace_fleet_scope",
        lambda db, workspace: {
            "scope_mode": "ute",
            "scope_company_ids": ["company_main", "company_partner"],
            "primary_company_id": "company_main",
            "ute_id": "ute_demo",
            "ute_name": "UTE Demo",
        },
    )

    captured = {}

    def _preview_ok(db, company_id, scope_company_ids, schedule_by_day, exclude_workspace_id=None):
        captured["company_id"] = company_id
        captured["scope_company_ids"] = list(scope_company_ids or [])
        return {
            "blocked": False,
            "conflicts": [],
            "real_assigned": 1,
            "virtual_created": 0,
            "days": {"L": {"fleet_assigned": 1, "virtual_buses": 0}},
            "schedule_by_day": schedule_by_day,
            "candidate_rows": [],
        }

    monkeypatch.setattr(workspaces_api, "preview_workspace_publication", _preview_ok)

    response = client.get(f"/api/workspaces/{workspace.id}/fleet-preview")
    assert response.status_code == 200
    body = response.json()
    assert body["scope_mode"] == "ute"
    assert body["scope_company_ids"] == ["company_main", "company_partner"]
    assert captured["company_id"] == "company_main"
    assert captured["scope_company_ids"] == ["company_main", "company_partner"]
