from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import crud, models, schemas
from services import fleet_repository as fleet_repo_module
from services.fleet_excel_import import commit_fleet_excel_import, parse_fleet_excel_preview
from services.fleet_scope import resolve_workspace_fleet_scope


def _make_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _build_excel_bytes():
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "AAV & COND'BUS"
    ws1.append(["MATRICULA", "PLAZAS"])
    ws1.append(["1111AAA", "55+1+1"])
    ws1.append(["2222BBB", "50"])
    ws1.append(["2222BBB", "50"])  # duplicate in sheet -> invalid

    ws2 = wb.create_sheet("MELYTOUR")
    ws2.append(["MATRICULA", "PLAZAS"])
    ws2.append(["3333CCC", "47"])
    ws2.append(["", "55"])  # invalid

    payload = BytesIO()
    wb.save(payload)
    return payload.getvalue()


def test_parse_fleet_excel_preview_supports_multisheet_and_pmr():
    preview = parse_fleet_excel_preview(_build_excel_bytes())

    assert len(preview["sheet_names"]) == 2
    assert len(preview["sheets"]) == 2

    first_sheet = preview["sheets"][0]
    assert first_sheet["sheet_name"] == "AAV & COND'BUS"
    assert first_sheet["header_detected"] is True
    assert int(first_sheet["valid_rows"]) == 2
    assert int(first_sheet["invalid_rows"]) == 1

    first_vehicle = first_sheet["vehicles"][0]
    assert first_vehicle["plate"] == "1111AAA"
    assert int(first_vehicle["seats_base"]) == 55
    assert int(first_vehicle["seats_pmr"]) == 2
    assert int(first_vehicle["seats_total"]) == 57


def test_commit_fleet_excel_import_creates_companies_vehicles_and_ute(monkeypatch):
    Session = _make_session_factory()
    monkeypatch.setattr(fleet_repo_module, "SessionLocal", Session)
    monkeypatch.setattr(fleet_repo_module, "is_database_available", lambda: True)

    db = Session()
    try:
        result = commit_fleet_excel_import(
            db,
            file_bytes=_build_excel_bytes(),
            primary_sheet_name="AAV & COND'BUS",
            ute_name="UTE Test",
        )
        assert result["companies_count"] == 2
        assert result["total_created"] == 3
        assert result["total_updated"] == 0
        assert result["total_invalid"] == 2

        companies = crud.list_companies(db, active_only=False)
        assert len(companies) >= 2

        vehicles = db.query(models.FleetVehicleModel).all()
        assert len(vehicles) == 3
        by_plate = {v.plate: v for v in vehicles}
        assert int(by_plate["1111AAA"].seats_base or 0) == 55
        assert int(by_plate["1111AAA"].seats_pmr or 0) == 2
        assert int(by_plate["1111AAA"].seats_max or 0) == 57

        ute = crud.get_ute(db, result["ute_id"])
        assert ute is not None
        assert ute.name == "UTE Test"
        assert len(ute.members) == 2

        # Re-import with same file -> upsert, no duplicates.
        second = commit_fleet_excel_import(
            db,
            file_bytes=_build_excel_bytes(),
            primary_sheet_name="AAV & COND'BUS",
            ute_name="UTE Test",
        )
        assert second["total_created"] == 0
        assert second["total_updated"] == 3
        assert db.query(models.FleetVehicleModel).count() == 3
    finally:
        db.close()


def test_commit_fleet_excel_import_promotes_primary_company_when_default_is_empty(monkeypatch):
    Session = _make_session_factory()
    monkeypatch.setattr(fleet_repo_module, "SessionLocal", Session)
    monkeypatch.setattr(fleet_repo_module, "is_database_available", lambda: True)

    db = Session()
    try:
        default_company = crud.ensure_default_company(db)
        workspace = crud.create_workspace(
            db,
            schemas.WorkspaceCreateRequest(
                name="Workspace Legacy Default",
                company_id=str(default_company.id),
            ),
        )
        db.commit()

        result = commit_fleet_excel_import(
            db,
            file_bytes=_build_excel_bytes(),
            primary_sheet_name="AAV & COND'BUS",
            ute_name="UTE Test",
        )
        db.commit()

        hydrated_workspace = crud.get_workspace(db, str(workspace.id))
        primary_company = crud.get_company(db, result["primary_company_id"])
        default_company_after = crud.get_company(db, crud.DEFAULT_COMPANY_ID)

        assert hydrated_workspace is not None
        assert primary_company is not None
        assert default_company_after is not None
        assert str(hydrated_workspace.company_id) == str(primary_company.id)
        assert bool(primary_company.is_default) is True
        assert bool(default_company_after.is_default) is False
    finally:
        db.close()


def test_resolve_workspace_fleet_scope_company_and_ute_modes():
    Session = _make_session_factory()
    db = Session()
    try:
        owner = crud.ensure_company(db, name="Owner SA", preferred_id="company_owner")
        partner = crud.ensure_company(db, name="Partner SA", preferred_id="company_partner")
        db.commit()

        workspace = crud.create_workspace(
            db,
            schemas.WorkspaceCreateRequest(
                name="WS Scope",
                company_id=str(owner.id),
            ),
        )
        hydrated = crud.get_workspace(db, str(workspace.id))
        assert hydrated is not None

        ute = crud.create_or_update_ute(
            db,
            ute_name="UTE Scope",
            owner_company_id=str(owner.id),
            member_company_ids=[str(owner.id), str(partner.id)],
        )
        db.commit()

        company_scope = resolve_workspace_fleet_scope(
            db,
            hydrated,
            {"fleet_scope_mode": "company"},
        )
        assert company_scope["scope_mode"] == "company"
        assert company_scope["scope_company_ids"] == [str(owner.id)]

        ute_scope = resolve_workspace_fleet_scope(
            db,
            hydrated,
            {"fleet_scope_mode": "ute", "fleet_scope_ute_id": str(ute.id)},
        )
        assert ute_scope["scope_mode"] == "ute"
        assert str(owner.id) in ute_scope["scope_company_ids"]
        assert str(partner.id) in ute_scope["scope_company_ids"]

        fallback_scope = resolve_workspace_fleet_scope(
            db,
            hydrated,
            {"fleet_scope_mode": "ute", "fleet_scope_ute_id": "ute_missing"},
        )
        assert fallback_scope["scope_mode"] == "company"
        assert fallback_scope.get("scope_fallback_reason") == "ute_not_found_or_inactive"
    finally:
        db.close()
