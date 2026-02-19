from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import crud, models, schemas


def _make_test_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session()


def test_workspace_save_publish_semantics():
    db = _make_test_session()
    try:
        workspace = crud.create_workspace(
            db,
            schemas.WorkspaceCreateRequest(
                name="Vigo",
                routes_payload=[{"id": "R1"}],
                schedule_by_day={"L": {"schedule": [{"bus_id": "B001", "items": []}]}},
            ),
        )
        assert workspace.working_version_id is not None
        assert workspace.published_version_id is None

        save_version = crud.create_workspace_version(
            db,
            str(workspace.id),
            schemas.WorkspaceVersionCreate(
                save_kind="save",
                checkpoint_name="checkpoint-1",
                schedule_by_day={"L": {"schedule": [{"bus_id": "B010", "items": []}]}},
            ),
        )
        assert save_version is not None
        assert save_version.save_kind == "save"

        publish_version = crud.create_workspace_version(
            db,
            str(workspace.id),
            schemas.WorkspaceVersionCreate(
                save_kind="publish",
                checkpoint_name="go-live",
            ),
        )
        assert publish_version is not None
        hydrated = crud.get_workspace(db, str(workspace.id))
        assert hydrated is not None
        assert str(hydrated.working_version_id) == str(publish_version.id)
        assert str(hydrated.published_version_id) == str(publish_version.id)

        active = crud.list_workspaces(db, status="active")
        assert len(active) == 1
        assert str(active[0].id) == str(workspace.id)
    finally:
        db.close()


def test_legacy_migration_is_idempotent_and_overrides_manual_day():
    db = _make_test_session()
    try:
        legacy_job = models.OptimizationJob(
            status="completed",
            algorithm="pipeline-v6-osrm",
            input_data=[{"id": "R1", "days": ["L"]}],
            result={
                "schedule_by_day": {
                    "L": {"schedule": [{"bus_id": "B001", "items": [{"route_id": "R1"}]}]},
                },
                "summary_metrics": {"best_buses": 1},
            },
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add(legacy_job)
        db.add(
            models.ManualScheduleModel(
                day="L",
                payload={
                    "day": "L",
                    "buses": [{"bus_id": "B099", "items": [{"route_id": "R1"}]}],
                    "metadata": {"source": "manual"},
                    "unassigned_routes": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
        )
        db.commit()

        success, migrated, workspace, details = crud.migrate_legacy_workspace_bootstrap(db)
        assert success is True
        assert migrated is True
        assert workspace is not None
        assert "L" in details.get("manual_days_applied", [])

        hydrated = crud.get_workspace(db, str(workspace.id))
        assert hydrated is not None
        assert hydrated.working_version is not None
        schedule_by_day = hydrated.working_version.schedule_by_day or {}
        assert schedule_by_day["L"]["schedule"][0]["bus_id"] == "B099"

        success2, migrated2, workspace2, details2 = crud.migrate_legacy_workspace_bootstrap(db)
        assert success2 is True
        assert migrated2 is False
        assert workspace2 is None
        assert details2.get("reason") in {"already_migrated", "workspaces_already_exist"}
    finally:
        db.close()


def test_workspace_hard_delete_removes_versions():
    db = _make_test_session()
    try:
        workspace = crud.create_workspace(
            db,
            schemas.WorkspaceCreateRequest(
                name="Eliminar-Me",
                routes_payload=[{"id": "R1"}],
                schedule_by_day={"L": {"schedule": [{"bus_id": "B001", "items": [{"route_id": "R1"}]}]}},
            ),
        )
        workspace_id = str(workspace.id)
        assert crud.get_workspace(db, workspace_id) is not None

        versions_before = crud.get_workspace_versions(db, workspace_id)
        assert len(versions_before) >= 1

        deleted_name = crud.delete_workspace_hard(db, workspace_id)
        assert deleted_name == "Eliminar-Me"
        assert crud.get_workspace(db, workspace_id) is None

        versions_after = db.query(models.OptimizationWorkspaceVersionModel).filter(
            models.OptimizationWorkspaceVersionModel.workspace_id == workspace_id
        ).all()
        assert versions_after == []
    finally:
        db.close()
