from fastapi import FastAPI
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import workspaces as workspaces_api
from db import crud, models, schemas
from services import fleet_repository as fleet_repository_module


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
    monkeypatch.setattr(fleet_repository_module, "SessionLocal", Session)
    monkeypatch.setattr(fleet_repository_module, "is_database_available", lambda: True)

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


def _seed_vehicle(
    db,
    *,
    company_id: str,
    vehicle_id: str,
    vehicle_code: str,
    seats_max: int = 55,
    brand: str | None = None,
    model: str | None = None,
    gps_provider: str | None = None,
):
    db.add(
        models.FleetVehicleModel(
            id=vehicle_id,
            company_id=company_id,
            vehicle_code=vehicle_code,
            plate=f"{vehicle_code}-PLATE",
            brand=brand,
            model=model,
            seats_base=seats_max,
            seats_pmr=0,
            seats_min=seats_max,
            seats_max=seats_max,
            status="active",
            gps_provider=gps_provider,
        )
    )
    db.commit()


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
    assert "capacity_summary" in detail["readiness_summary"]
    assert "blocking_issues" in detail["readiness_summary"]


def test_fleet_reconciliation_endpoint_normalizes_pending_assignments(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = crud.create_workspace(
            db,
            schemas.WorkspaceCreateRequest(
                name="Workspace Reconciliation Snapshot",
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
                                        "end_time": "09:20:00",
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
        company = crud.ensure_company(db, name="Empresa A", preferred_id="company_a")
        workspace.company_id = str(company.id)
        db.commit()
        _seed_vehicle(db, company_id=str(company.id), vehicle_id="veh-1", vehicle_code="B001", seats_max=55)
        workspace_id = str(workspace.id)
    finally:
        db.close()

    response = client.get(f"/api/workspaces/{workspace_id}/fleet-reconciliation?day=L")
    assert response.status_code == 200
    body = response.json()
    assert body["required_bus_count"] == 1
    assert body["pending_real_reconciliation_count"] == 1
    assert body["pending_assignments"][0]["required_capacity"] == 40
    assert body["pending_assignments"][0]["time_window"] == {"start_minute": 480, "end_minute": 560}
    assert body["pending_assignments"][0]["suggested_real_vehicles"][0]["vehicle_code"] == "B001"
    assert body["reconciliation"]["company_mix"]["total_pending_buses"] == 1
    assert body["reconciliation"]["company_mix"]["recommended_companies"][0]["company_name"] == "Empresa A"
    assert body["reconciliation_day"]["company_mix"]["recommended_companies"][0]["recommended_count"] == 1
    assert "operational_summary" in body
    assert "candidate_rejection_reasons" in body
    assert "candidate_rejection_reasons" in body["reconciliation_day"]


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
        company = crud.ensure_company(db, name="Empresa A", preferred_id="company_a")
        workspace.company_id = str(company.id)
        db.commit()
        _seed_vehicle(db, company_id=str(company.id), vehicle_id="veh-1", vehicle_code="B001", seats_max=55)
        workspace_id = str(workspace.id)
    finally:
        db.close()

    response = client.post(
        f"/api/workspaces/{workspace_id}/fleet-reconciliation/apply",
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


def test_apply_fleet_reconciliation_respects_exact_vehicle_selection(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = crud.create_workspace(
            db,
            schemas.WorkspaceCreateRequest(
                name="Workspace Exact Vehicle",
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
        company = crud.ensure_company(db, name="Empresa A", preferred_id="company_a")
        workspace.company_id = str(company.id)
        db.commit()
        _seed_vehicle(db, company_id=str(company.id), vehicle_id="veh-1", vehicle_code="B001", seats_max=55)
        _seed_vehicle(db, company_id=str(company.id), vehicle_id="veh-2", vehicle_code="B002", seats_max=57)
        workspace_id = str(workspace.id)
    finally:
        db.close()

    response = client.post(
        f"/api/workspaces/{workspace_id}/fleet-reconciliation/apply",
        json={
            "day": "L",
            "company_allocations": [{"company_id": "company_a", "count": 1}],
            "bus_selections": [
                {
                    "day": "L",
                    "bus_id": "B-V1",
                    "vehicle_id": "veh-2",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assigned_bus = body["schedule_by_day"]["L"]["schedule"][0]
    assert assigned_bus["assigned_vehicle_id"] == "veh-2"
    assert assigned_bus["assigned_vehicle_code"] == "B002"


def test_preview_fleet_reconciliation_plan_returns_candidate_metadata(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = crud.create_workspace(
            db,
            schemas.WorkspaceCreateRequest(
                name="Workspace Preview Plan",
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
        company = crud.ensure_company(db, name="Empresa A", preferred_id="company_a")
        workspace.company_id = str(company.id)
        db.commit()
        _seed_vehicle(
            db,
            company_id=str(company.id),
            vehicle_id="veh-1",
            vehicle_code="B001",
            seats_max=55,
            brand="Iveco",
            model="Wing",
            gps_provider="geotab",
        )
        db.add(
            models.FleetVehicleDocumentModel(
                vehicle_id="veh-1",
                doc_type="seguro",
                reference="DOC-1",
            )
        )
        db.commit()
        workspace_id = str(workspace.id)
    finally:
        db.close()

    response = client.post(
        f"/api/workspaces/{workspace_id}/fleet-reconciliation/plan",
        json={
            "day": "L",
            "company_allocations": [{"company_id": "company_a", "count": 1}],
            "bus_selections": [
                {
                    "day": "L",
                    "bus_id": "B-V1",
                    "vehicle_id": "veh-1",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["selected_assignments"][0]["vehicle_id"] == "veh-1"
    assert body["items"][0]["planned_assignment"]["vehicle_id"] == "veh-1"
    candidate = body["items"][0]["suggested_real_vehicles"][0]
    assert candidate["vehicle_code"] == "B001"
    assert candidate["brand"] == "Iveco"
    assert candidate["model"] == "Wing"
    assert candidate["gps_provider"] == "geotab"
    assert candidate["has_pending_documents"] is False
    assert candidate["documents_count"] == 1


def test_update_workspace_company_changes_primary_company(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        workspace = _seed_workspace(db)
        company = crud.ensure_company(db, name="Empresa Demo", preferred_id="company_demo")
        db.commit()
        workspace_id = str(workspace.id)
        company_id = str(company.id)
    finally:
        db.close()

    response = client.post(
        f"/api/workspaces/{workspace_id}/company",
        json={"company_id": company_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["company_id"] == "company_demo"


def test_get_workspace_repairs_legacy_default_company_to_single_ute_owner(monkeypatch):
    client, Session = _build_test_client(monkeypatch)

    db = Session()
    try:
        default_company = crud.ensure_default_company(db)
        owner = crud.ensure_company(db, name="AAV & COND'BUS", preferred_id="company_aav")
        partner = crud.ensure_company(db, name="AUTNA", preferred_id="company_autna")
        workspace = crud.create_workspace(
            db,
            schemas.WorkspaceCreateRequest(
                name="Workspace Legacy Scope",
                company_id=str(default_company.id),
            ),
        )
        crud.create_or_update_ute(
            db,
            ute_name="UTE AAV",
            owner_company_id=str(owner.id),
            member_company_ids=[str(owner.id), str(partner.id)],
        )
        db.add(
            models.FleetVehicleModel(
                id="veh-aav-1",
                company_id=str(owner.id),
                vehicle_code="B001",
                plate="1111AAA",
                seats_base=55,
                seats_pmr=0,
                seats_min=55,
                seats_max=55,
                status="active",
            )
        )
        db.commit()
        workspace_id = str(workspace.id)
    finally:
        db.close()

    response = client.get(f"/api/workspaces/{workspace_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["company_id"] == "company_aav"
