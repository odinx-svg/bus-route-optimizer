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


def test_publish_workspace_blocks_when_virtual_policy_is_block(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = _seed_workspace(db)
    finally:
        db.close()

    monkeypatch.setattr(
        workspaces_api,
        "get_workspace_optimization_options",
        lambda db, workspace_id: {"virtual_bus_publish_policy": "block"},
    )

    def _preview_virtual(*args, **kwargs):
        return {
            "blocked": False,
            "conflicts": [],
            "real_assigned": 0,
            "virtual_created": 2,
            "days": {"L": {"fleet_assigned": 0, "virtual_buses": 2}},
            "schedule_by_day": {"L": {"schedule": []}},
            "candidate_rows": [],
            "reconciliation": {
                "pending_count": 2,
                "items": [
                    {
                        "day": "L",
                        "bus_id": "B-V1",
                        "required_seats": 44,
                        "start_minute": 480,
                        "end_minute": 560,
                        "route_ids": ["R001"],
                        "suggestions": [],
                    }
                ],
            },
        }

    monkeypatch.setattr(workspaces_api, "preview_workspace_publication", _preview_virtual)

    response = client.post(f"/api/workspaces/{workspace.id}/publish", json={})
    assert response.status_code == 409
    body = response.json()
    assert body["detail"]["reason"] == "virtual_reconciliation_required"
    publication = body["detail"]["fleet_publication"]
    assert publication["blocked"] is True
    assert publication["virtual_created"] == 2
    assert publication["virtual_publish_policy"] == "block"
    assert publication["reconciliation"]["pending_count"] == 2


def test_fleet_preview_includes_reconciliation_when_policy_block(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = _seed_workspace(db)
    finally:
        db.close()

    monkeypatch.setattr(
        workspaces_api,
        "get_workspace_optimization_options",
        lambda db, workspace_id: {"virtual_bus_publish_policy": "block"},
    )

    def _preview_virtual(*args, **kwargs):
        return {
            "blocked": False,
            "conflicts": [],
            "real_assigned": 1,
            "virtual_created": 1,
            "days": {"L": {"fleet_assigned": 1, "virtual_buses": 1}},
            "schedule_by_day": {"L": {"schedule": []}},
            "candidate_rows": [],
            "reconciliation": {
                "pending_count": 1,
                "by_day": {"L": {"pending_virtual": 1, "items": [{"bus_id": "B-V1"}]}},
                "items": [{"day": "L", "bus_id": "B-V1", "required_seats": 40}],
            },
        }

    monkeypatch.setattr(workspaces_api, "preview_workspace_publication", _preview_virtual)

    response = client.get(f"/api/workspaces/{workspace.id}/fleet-preview")
    assert response.status_code == 200
    body = response.json()
    assert body["virtual_publish_policy"] == "block"
    assert body["requires_reconciliation"] is True
    assert body["reconciliation"]["pending_count"] == 1


def test_workspace_list_and_detail_include_readiness_fields(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = _seed_workspace(db)
        workspace = crud.get_workspace(db, str(workspace.id))
        assert workspace is not None
        assert workspace.working_version is not None
        workspace.working_version.summary_metrics = {
            "fleet_virtual_created": 2,
            "fleet_virtual_publish_policy": "block",
        }
        workspace.working_version.fleet_snapshot = {
            "scope_mode": "ute",
            "scope_company_ids": ["company_main", "company_partner"],
            "ute_id": "ute_demo",
            "ute_name": "UTE Demo",
            "virtual_publish_policy": "block",
            "virtual_created": 2,
            "conflicts": [],
            "reconciliation": {
                "pending_count": 2,
            },
        }
        db.commit()
    finally:
        db.close()

    list_response = client.get("/api/workspaces")
    assert list_response.status_code == 200
    item = list_response.json()["items"][0]
    assert item["workflow_stage"] == "pending_reconciliation"
    assert item["readiness_state"] == "warning"
    assert item["blocking_reason"] == "virtual_reconciliation_required"
    assert item["next_recommended_action"] == "reconcile"
    assert item["pending_virtual_count"] == 2
    assert item["scope_summary"]["mode"] == "ute"
    assert item["scope_summary"]["label"] == "UTE · UTE Demo"

    detail_response = client.get(f"/api/workspaces/{item['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["readiness_summary"]["workflow_stage"] == "pending_reconciliation"
    assert detail["readiness_summary"]["next_recommended_action"] == "reconcile"
    assert detail["readiness_summary"]["pending_virtual_count"] == 2


def test_fleet_reconciliation_endpoint_normalizes_pending_assignments(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = _seed_workspace(db)
    finally:
        db.close()

    def _preview_virtual(*args, **kwargs):
        return {
            "blocked": False,
            "conflicts": [],
            "real_assigned": 1,
            "virtual_created": 1,
            "days": {"L": {"fleet_assigned": 1, "virtual_buses": 1}},
            "schedule_by_day": {"L": {"schedule": []}},
            "candidate_rows": [],
            "reconciliation": {
                "pending_count": 1,
                "company_mix": {
                    "total_pending_buses": 1,
                    "recommended_companies": [
                        {
                            "company_id": "company_a",
                            "company_name": "Empresa A",
                            "recommended_count": 1,
                            "coverable_assignments": 1,
                            "candidate_vehicle_count": 1,
                            "vehicle_codes": ["B001"],
                        }
                    ],
                    "companies_with_options": 1,
                    "uncovered_buses": 0,
                },
                "by_day": {
                    "L": {
                        "pending_virtual": 1,
                        "company_mix": {
                            "total_pending_buses": 1,
                            "recommended_companies": [
                                {
                                    "company_id": "company_a",
                                    "company_name": "Empresa A",
                                    "recommended_count": 1,
                                    "coverable_assignments": 1,
                                    "candidate_vehicle_count": 1,
                                    "vehicle_codes": ["B001"],
                                }
                            ],
                            "companies_with_options": 1,
                            "uncovered_buses": 0,
                        },
                        "items": [
                            {
                                "day": "L",
                                "bus_id": "B-V1",
                                "required_seats": 40,
                                "start_minute": 480,
                                "end_minute": 560,
                                "suggestions": [{"vehicle_id": "veh-1", "vehicle_code": "B001", "seats_max": 55}],
                            }
                        ],
                    }
                },
                "items": [
                    {
                        "day": "L",
                        "bus_id": "B-V1",
                        "required_seats": 40,
                        "start_minute": 480,
                        "end_minute": 560,
                        "suggestions": [{"vehicle_id": "veh-1", "vehicle_code": "B001", "seats_max": 55}],
                    }
                ],
            },
        }

    monkeypatch.setattr(workspaces_api, "preview_workspace_publication", _preview_virtual)

    response = client.get(f"/api/workspaces/{workspace.id}/fleet-reconciliation?day=L")
    assert response.status_code == 200
    body = response.json()
    assert body["pending_assignments"][0]["required_capacity"] == 40
    assert body["pending_assignments"][0]["time_window"] == {"start_minute": 480, "end_minute": 560}
    assert body["pending_assignments"][0]["suggested_real_vehicles"][0]["vehicle_code"] == "B001"
    assert body["reconciliation"]["company_mix"]["total_pending_buses"] == 1
    assert body["reconciliation"]["company_mix"]["recommended_companies"][0]["company_name"] == "Empresa A"
    assert body["reconciliation_day"]["company_mix"]["recommended_companies"][0]["recommended_count"] == 1


def test_apply_fleet_reconciliation_persists_selected_real_assignments(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = crud.create_workspace(
            db,
            schemas.WorkspaceCreateRequest(
                name="Workspace Reconciliation",
                schedule_by_day={
                    "L": {
                        "schedule": [
                            {
                                "bus_id": "B-V1",
                                "fleet_assignment_type": "virtual",
                                "items": [
                                    {
                                        "route_id": "R001",
                                        "start_time": "08:00:00",
                                        "end_time": "09:00:00",
                                        "type": "entry",
                                        "capacity_needed": 40,
                                    }
                                ],
                            }
                        ]
                    }
                },
            ),
        )
    finally:
        db.close()

    def _preview_for_apply(db, company_id, schedule_by_day, exclude_workspace_id=None, scope_company_ids=None):
        bus_payload = (((schedule_by_day or {}).get("L") or {}).get("schedule") or [{}])[0]
        already_real = str(bus_payload.get("assigned_vehicle_id") or "").strip() == "veh-1"
        if already_real:
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
                        "bus_id": "B-V1",
                        "route_id": "R001",
                        "start_minute": 8 * 60,
                        "end_minute": 9 * 60,
                        "assigned_vehicle_id": "veh-1",
                        "assignment_type": "real",
                    }
                ],
                "reconciliation": {
                    "pending_count": 0,
                    "by_day": {"L": {"pending_virtual": 0, "items": [], "company_mix": {"total_pending_buses": 0, "recommended_companies": [], "companies_with_options": 0, "uncovered_buses": 0}}},
                    "items": [],
                    "company_mix": {"total_pending_buses": 0, "recommended_companies": [], "companies_with_options": 0, "uncovered_buses": 0},
                },
            }
        return {
            "blocked": False,
            "conflicts": [],
            "real_assigned": 0,
            "virtual_created": 1,
            "days": {"L": {"fleet_assigned": 0, "virtual_buses": 1}},
            "schedule_by_day": schedule_by_day,
            "candidate_rows": [],
            "reconciliation": {
                "pending_count": 1,
                "by_day": {
                    "L": {
                        "pending_virtual": 1,
                        "company_mix": {
                            "total_pending_buses": 1,
                            "recommended_companies": [
                                {
                                    "company_id": "company_a",
                                    "company_name": "Empresa A",
                                    "recommended_count": 1,
                                    "coverable_assignments": 1,
                                    "candidate_vehicle_count": 1,
                                    "vehicle_codes": ["B001"],
                                }
                            ],
                            "companies_with_options": 1,
                            "uncovered_buses": 0,
                        },
                        "items": [
                            {
                                "day": "L",
                                "bus_id": "B-V1",
                                "required_seats": 40,
                                "start_minute": 480,
                                "end_minute": 540,
                                "suggestions": [
                                    {
                                        "vehicle_id": "veh-1",
                                        "vehicle_code": "B001",
                                        "company_id": "company_a",
                                        "company_name": "Empresa A",
                                        "seats_base": 55,
                                        "seats_pmr": 0,
                                        "seats_min": 55,
                                        "seats_max": 55,
                                    }
                                ],
                            }
                        ],
                    }
                },
                "items": [
                    {
                        "day": "L",
                        "bus_id": "B-V1",
                        "required_seats": 40,
                        "start_minute": 480,
                        "end_minute": 540,
                        "suggestions": [
                            {
                                "vehicle_id": "veh-1",
                                "vehicle_code": "B001",
                                "company_id": "company_a",
                                "company_name": "Empresa A",
                                "seats_base": 55,
                                "seats_pmr": 0,
                                "seats_min": 55,
                                "seats_max": 55,
                            }
                        ],
                    }
                ],
                "company_mix": {
                    "total_pending_buses": 1,
                    "recommended_companies": [
                        {
                            "company_id": "company_a",
                            "company_name": "Empresa A",
                            "recommended_count": 1,
                            "coverable_assignments": 1,
                            "candidate_vehicle_count": 1,
                            "vehicle_codes": ["B001"],
                        }
                    ],
                    "companies_with_options": 1,
                    "uncovered_buses": 0,
                },
            },
        }

    monkeypatch.setattr(workspaces_api, "preview_workspace_publication", _preview_for_apply)

    response = client.post(
        f"/api/workspaces/{workspace.id}/fleet-reconciliation/apply",
        json={
            "day": "L",
            "company_allocations": [{"company_id": "company_a", "count": 1}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["applied_count"] == 1
    assert body["remaining_pending"] == 0
    assert body["applied_by_company"][0]["company_name"] == "Empresa A"
    assigned_bus = body["schedule_by_day"]["L"]["schedule"][0]
    assert assigned_bus["assigned_vehicle_id"] == "veh-1"
    assert assigned_bus["fleet_assignment_type"] == "real"
