from datetime import time
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import crud, models, schemas
from models import BusSchedule, ScheduleItem
from services import fleet_publication


def _make_test_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session()


def _create_workspace_with_version(db, name: str):
    workspace = crud.create_workspace(
        db,
        schemas.WorkspaceCreateRequest(name=name),
    )
    version = crud.create_workspace_version(
        db,
        str(workspace.id),
        schemas.WorkspaceVersionCreate(
            save_kind="publish",
            schedule_by_day={"L": {"schedule": []}},
        ),
    )
    assert version is not None
    return workspace, version


def test_detect_publication_conflicts_with_overlap():
    db = _make_test_session()
    try:
        workspace, version = _create_workspace_with_version(db, "Publicado-1")
        company = crud.ensure_default_company(db)

        db.add(
            models.PublishedFleetAssignmentModel(
                id=str(uuid4()),
                company_id=str(company.id),
                workspace_id=str(workspace.id),
                workspace_version_id=str(version.id),
                day="L",
                bus_id="B001",
                route_id="R_EXIST",
                start_minute=8 * 60,
                end_minute=9 * 60,
                assigned_vehicle_id="veh-001",
                assignment_type="real",
                active=True,
                details={},
            )
        )
        db.commit()

        conflicts = fleet_publication.detect_publication_conflicts(
            db,
            company_id=str(company.id),
            candidate_rows=[
                {
                    "day": "L",
                    "bus_id": "B099",
                    "route_id": "R_NEW",
                    "start_minute": (8 * 60) + 15,
                    "end_minute": (9 * 60) + 10,
                    "assigned_vehicle_id": "veh-001",
                    "assignment_type": "real",
                }
            ],
            exclude_workspace_id=None,
        )

        assert len(conflicts) == 1
        assert conflicts[0]["vehicle_id"] == "veh-001"
        assert conflicts[0]["conflicting_workspace_id"] == str(workspace.id)
    finally:
        db.close()


def test_preview_workspace_publication_marks_blocked(monkeypatch):
    db = _make_test_session()
    try:
        workspace, version = _create_workspace_with_version(db, "Publicado-2")
        company = crud.ensure_default_company(db)

        db.add(
            models.PublishedFleetAssignmentModel(
                id=str(uuid4()),
                company_id=str(company.id),
                workspace_id=str(workspace.id),
                workspace_version_id=str(version.id),
                day="L",
                bus_id="B001",
                route_id="R_EXIST",
                start_minute=8 * 60,
                end_minute=9 * 60,
                assigned_vehicle_id="veh-001",
                assignment_type="real",
                active=True,
                details={},
            )
        )
        db.commit()

        def _fake_assign(
            schedule_by_day,
            fleet_profiles=None,
            company_id=None,
            scope_company_ids=None,
            binding_state="preview",
        ):
            bus = BusSchedule(
                bus_id="B010",
                items=[
                    ScheduleItem(
                        route_id="R_NEW",
                        start_time=time(8, 30),
                        end_time=time(9, 20),
                        type="entry",
                    )
                ],
                assigned_vehicle_id="veh-001",
                assigned_vehicle_code="BUS-REAL-001",
                fleet_assignment_type="real",
                fleet_binding_state=binding_state,
                uses_fleet_profile=True,
            )
            assigned = {day: [] for day in fleet_publication.ALL_DAYS}
            assigned["L"] = [bus]
            return assigned, {
                "total_assigned": 1,
                "total_virtual_buses": 0,
                "days": {"L": {"fleet_assigned": 1, "virtual_buses": 0}},
            }

        monkeypatch.setattr(
            fleet_publication,
            "_assign_schedule_by_day_preserving_existing",
            _fake_assign,
        )

        preview = fleet_publication.preview_workspace_publication(
            db,
            company_id=str(company.id),
            schedule_by_day={"L": {"schedule": [{"bus_id": "B010", "items": []}]}},
            exclude_workspace_id=str(uuid4()),
        )

        assert preview["blocked"] is True
        assert len(preview["conflicts"]) == 1
        assert preview["real_assigned"] == 1
        assert preview["virtual_created"] == 0
    finally:
        db.close()


def test_persist_publication_assignments_replaces_previous_workspace_rows():
    db = _make_test_session()
    try:
        workspace, version = _create_workspace_with_version(db, "Publicado-3")
        company = crud.ensure_default_company(db)

        old_row = models.PublishedFleetAssignmentModel(
            id=str(uuid4()),
            company_id=str(company.id),
            workspace_id=str(workspace.id),
            workspace_version_id=str(version.id),
            day="L",
            bus_id="B001",
            route_id="R_OLD",
            start_minute=7 * 60,
            end_minute=8 * 60,
            assigned_vehicle_id="veh-old",
            assignment_type="real",
            active=True,
            details={},
        )
        db.add(old_row)
        db.commit()

        fleet_publication.persist_publication_assignments(
            db,
            workspace_id=str(workspace.id),
            workspace_version_id=str(version.id),
            company_id=str(company.id),
            candidate_rows=[
                {
                    "day": "L",
                    "bus_id": "B002",
                    "route_id": "R_NEW",
                    "start_minute": 9 * 60,
                    "end_minute": 10 * 60,
                    "assigned_vehicle_id": "veh-new",
                    "assignment_type": "real",
                }
            ],
        )
        db.commit()

        rows = db.query(models.PublishedFleetAssignmentModel).filter(
            models.PublishedFleetAssignmentModel.workspace_id == str(workspace.id)
        ).all()
        assert len(rows) == 2
        active_rows = [row for row in rows if row.active]
        assert len(active_rows) == 1
        assert active_rows[0].route_id == "R_NEW"
    finally:
        db.close()
