"""
Fleet Management API.

Provides CRUD endpoints for vehicle profiles used by operations/planning.
DB-first with JSON fallback.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, model_validator

from db import crud as db_crud
from db import models as db_models
from db.database import SessionLocal, is_database_available
from services.fleet_repository import FleetRepository
from services.fleet_excel_import import commit_fleet_excel_import, parse_fleet_excel_preview
from services.telematics_provider import test_telematics_link

router = APIRouter(prefix="/api/fleet", tags=["fleet"])
fleet_repository = FleetRepository()


class VehicleDocument(BaseModel):
    id: Optional[str] = None
    doc_type: str = Field(default="", max_length=80)
    reference: str = Field(default="", max_length=120)
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class FleetVehicleBase(BaseModel):
    company_id: Optional[str] = Field(default=None, max_length=64)
    company_name: Optional[str] = Field(default=None, max_length=120)
    vehicle_code: str = Field(min_length=1, max_length=32)
    plate: str = Field(min_length=1, max_length=32)
    brand: Optional[str] = Field(default=None, max_length=80)
    model: Optional[str] = Field(default=None, max_length=80)
    year: Optional[int] = Field(default=None, ge=1980, le=2100)
    seats_base: Optional[int] = Field(default=None, ge=1, le=200)
    seats_pmr: Optional[int] = Field(default=0, ge=0, le=50)
    seats_min: int = Field(ge=1, le=200)
    seats_max: int = Field(ge=1, le=200)
    status: Literal["active", "maintenance", "inactive"] = "active"
    fuel_type: Optional[str] = Field(default=None, max_length=32)
    accessibility: bool = False
    mileage_km: Optional[int] = Field(default=None, ge=0, le=2_000_000)
    notes: Optional[str] = Field(default=None, max_length=1200)
    gps_provider: Optional[str] = Field(default=None, max_length=64)
    gps_external_id: Optional[str] = Field(default=None, max_length=120)
    gps_last_seen_at: Optional[str] = None
    gps_last_position: Optional[dict] = None
    documents: List[VehicleDocument] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_seat_range(self) -> "FleetVehicleBase":
        if self.seats_min > self.seats_max:
            raise ValueError("seats_min no puede ser mayor que seats_max")
        if self.seats_base is not None and self.seats_base <= 0:
            raise ValueError("seats_base debe ser mayor que 0")
        if self.seats_pmr is not None and self.seats_pmr < 0:
            raise ValueError("seats_pmr no puede ser negativo")
        return self


class FleetVehicleCreate(FleetVehicleBase):
    pass


class FleetVehicleUpdate(FleetVehicleBase):
    pass


class FleetVehicleResponse(FleetVehicleBase):
    id: str
    created_at: str
    updated_at: str
    age_years: Optional[int] = None


class FleetSummary(BaseModel):
    total: int
    active: int
    maintenance: int
    inactive: int
    total_seats_max: int
    avg_seats_max: float


class FleetListResponse(BaseModel):
    vehicles: List[FleetVehicleResponse]
    summary: FleetSummary


class UTEMemberResponse(BaseModel):
    company_id: str
    company_name: Optional[str] = None
    role: str = "partner"


class UTEResponse(BaseModel):
    id: str
    name: str
    owner_company_id: str
    owner_company_name: Optional[str] = None
    active: bool = True
    members: List[UTEMemberResponse] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UTECreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    owner_company_id: str = Field(min_length=1, max_length=64)
    member_company_ids: List[str] = Field(default_factory=list)


class UTEUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    owner_company_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    member_company_ids: Optional[List[str]] = None
    active: Optional[bool] = None


class FleetImportPreviewResponse(BaseModel):
    sheet_names: List[str] = Field(default_factory=list)
    companies_detected: List[str] = Field(default_factory=list)
    sheets: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class FleetImportCommitResponse(BaseModel):
    primary_company_id: str
    ute_id: str
    ute_name: str
    scope_mode_suggested: str = "company"
    companies_count: int = 0
    total_created: int = 0
    total_updated: int = 0
    total_invalid: int = 0
    summary_by_company: List[Dict[str, Any]] = Field(default_factory=list)


class TelematicsLinkTestRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    external_vehicle_id: str = Field(min_length=1, max_length=120)
    config: Optional[dict] = None


class TelematicsLinkTestResponse(BaseModel):
    ok: bool
    provider: str
    external_vehicle_id: Optional[str] = None
    message: str
    checked_at: Optional[str] = None


def _to_response(vehicle: dict) -> FleetVehicleResponse:
    current_year = datetime.utcnow().year
    year = vehicle.get("year")
    age_years: Optional[int] = None
    if isinstance(year, int) and 1980 <= year <= 2100:
        age_years = max(0, current_year - year)
    return FleetVehicleResponse(
        id=str(vehicle.get("id", "")),
        company_id=str(vehicle.get("company_id", "") or "") or None,
        company_name=str(vehicle.get("company_name", "") or "") or None,
        vehicle_code=str(vehicle.get("vehicle_code", "") or ""),
        plate=str(vehicle.get("plate", "") or ""),
        brand=vehicle.get("brand"),
        model=vehicle.get("model"),
        year=year,
        seats_base=int(vehicle.get("seats_base") or vehicle.get("seats_min") or 1),
        seats_pmr=int(vehicle.get("seats_pmr") or 0),
        seats_min=int(vehicle.get("seats_min") or 0),
        seats_max=int(vehicle.get("seats_max") or 0),
        status=str(vehicle.get("status", "active") or "active"),  # type: ignore[arg-type]
        fuel_type=vehicle.get("fuel_type"),
        accessibility=bool(vehicle.get("accessibility", False)),
        mileage_km=vehicle.get("mileage_km"),
        notes=vehicle.get("notes"),
        gps_provider=vehicle.get("gps_provider"),
        gps_external_id=vehicle.get("gps_external_id"),
        gps_last_seen_at=vehicle.get("gps_last_seen_at"),
        gps_last_position=vehicle.get("gps_last_position") if isinstance(vehicle.get("gps_last_position"), dict) else None,
        documents=[VehicleDocument(**doc) for doc in (vehicle.get("documents", []) or [])],
        created_at=str(vehicle.get("created_at", "")),
        updated_at=str(vehicle.get("updated_at", "")),
        age_years=age_years,
    )


def _build_summary(vehicles: List[FleetVehicleResponse]) -> FleetSummary:
    total = len(vehicles)
    active = sum(1 for v in vehicles if v.status == "active")
    maintenance = sum(1 for v in vehicles if v.status == "maintenance")
    inactive = sum(1 for v in vehicles if v.status == "inactive")
    total_seats_max = sum(max(0, int(v.seats_max or 0)) for v in vehicles)
    avg_seats_max = round((total_seats_max / total), 2) if total > 0 else 0.0
    return FleetSummary(
        total=total,
        active=active,
        maintenance=maintenance,
        inactive=inactive,
        total_seats_max=total_seats_max,
        avg_seats_max=avg_seats_max,
    )


def _to_ute_response(ute) -> UTEResponse:
    members = []
    for member in (ute.members or []):
        members.append(
            UTEMemberResponse(
                company_id=str(member.company_id),
                company_name=str(member.company.name or "") if member.company else None,
                role=str(member.role or "partner"),
            )
        )
    return UTEResponse(
        id=str(ute.id),
        name=str(ute.name or ""),
        owner_company_id=str(ute.owner_company_id),
        owner_company_name=str(ute.owner_company.name or "") if ute.owner_company else None,
        active=bool(ute.active),
        members=members,
        created_at=ute.created_at.isoformat() if ute.created_at else None,
        updated_at=ute.updated_at.isoformat() if ute.updated_at else None,
    )


def _require_db():
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")


def _assert_companies_exist(db, company_ids: List[str]) -> List[str]:
    normalized: List[str] = []
    missing: List[str] = []
    for raw in company_ids:
        company_id = str(raw or "").strip()
        if not company_id:
            continue
        if company_id in normalized:
            continue
        normalized.append(company_id)
        if db_crud.get_company(db, company_id) is None:
            missing.append(company_id)
    if missing:
        raise HTTPException(status_code=404, detail=f"Empresas no encontradas: {', '.join(missing)}")
    return normalized


@router.get("/vehicles", response_model=FleetListResponse)
async def list_vehicles(
    company_id: Optional[str] = Query(default=None),
    company_ids: Optional[str] = Query(default=None, description="Comma-separated company ids"),
) -> FleetListResponse:
    company_ids_list = [
        item.strip() for item in str(company_ids or "").split(",")
        if item and item.strip()
    ]
    vehicles_raw = fleet_repository.list_vehicles(company_id=company_id, company_ids=company_ids_list or None)
    vehicles = [_to_response(v) for v in vehicles_raw]
    return FleetListResponse(vehicles=vehicles, summary=_build_summary(vehicles))


@router.get("/vehicles/{vehicle_id}", response_model=FleetVehicleResponse)
async def get_vehicle(vehicle_id: str, company_id: Optional[str] = Query(default=None)) -> FleetVehicleResponse:
    vehicle = fleet_repository.get_vehicle(vehicle_id, company_id=company_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado")
    return _to_response(vehicle)


@router.post("/vehicles", response_model=FleetVehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(payload: FleetVehicleCreate, company_id: Optional[str] = Query(default=None)) -> FleetVehicleResponse:
    try:
        created = fleet_repository.create_vehicle(payload.model_dump(), company_id=company_id or payload.company_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(created)


@router.put("/vehicles/{vehicle_id}", response_model=FleetVehicleResponse)
async def update_vehicle(
    vehicle_id: str,
    payload: FleetVehicleUpdate,
    company_id: Optional[str] = Query(default=None),
) -> FleetVehicleResponse:
    try:
        updated = fleet_repository.update_vehicle(
            vehicle_id,
            payload.model_dump(),
            company_id=company_id or payload.company_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(updated)


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: str, company_id: Optional[str] = Query(default=None)) -> dict:
    deleted = fleet_repository.delete_vehicle(vehicle_id, company_id=company_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado")
    return {"success": True, "vehicle_id": vehicle_id}


@router.post("/import/preview", response_model=FleetImportPreviewResponse)
async def preview_fleet_import(file: UploadFile = File(...)) -> FleetImportPreviewResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacio")
    try:
        preview = parse_fleet_excel_preview(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo analizar Excel: {exc}") from exc
    return FleetImportPreviewResponse(**preview)


@router.post("/import/commit", response_model=FleetImportCommitResponse)
async def commit_fleet_import(
    file: UploadFile = File(...),
    primary_sheet_name: str = Form(...),
    ute_name: Optional[str] = Form(default=None),
) -> FleetImportCommitResponse:
    _require_db()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacio")

    db = SessionLocal()
    try:
        payload = commit_fleet_excel_import(
            db,
            file_bytes=content,
            primary_sheet_name=primary_sheet_name,
            ute_name=ute_name,
            repository=fleet_repository,
        )
        return FleetImportCommitResponse(**payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"No se pudo importar flota: {exc}") from exc
    finally:
        db.close()


@router.get("/utes", response_model=List[UTEResponse])
async def list_utes(active_only: bool = Query(default=True)) -> List[UTEResponse]:
    _require_db()
    db = SessionLocal()
    try:
        rows = db_crud.list_utes(db, active_only=active_only)
        return [_to_ute_response(row) for row in rows]
    finally:
        db.close()


@router.post("/utes", response_model=UTEResponse, status_code=status.HTTP_201_CREATED)
async def create_ute(payload: UTECreateRequest) -> UTEResponse:
    _require_db()
    db = SessionLocal()
    try:
        owner_company_id = str(payload.owner_company_id).strip()
        _assert_companies_exist(db, [owner_company_id])
        member_ids = [str(item).strip() for item in payload.member_company_ids if str(item).strip()]
        member_ids.append(owner_company_id)
        member_ids = _assert_companies_exist(db, member_ids)
        ute = db_crud.create_or_update_ute(
            db,
            ute_name=payload.name,
            owner_company_id=owner_company_id,
            member_company_ids=member_ids,
        )
        db.commit()
        return _to_ute_response(ute)
    finally:
        db.close()


@router.get("/utes/{ute_id}", response_model=UTEResponse)
async def get_ute(ute_id: str) -> UTEResponse:
    _require_db()
    db = SessionLocal()
    try:
        ute = db_crud.get_ute(db, ute_id)
        if ute is None:
            raise HTTPException(status_code=404, detail="UTE no encontrada")
        return _to_ute_response(ute)
    finally:
        db.close()


@router.put("/utes/{ute_id}", response_model=UTEResponse)
async def update_ute(ute_id: str, payload: UTEUpdateRequest) -> UTEResponse:
    _require_db()
    db = SessionLocal()
    try:
        ute = db.query(db_models.UTEModel).filter(db_models.UTEModel.id == str(ute_id)).first()
        if ute is None:
            raise HTTPException(status_code=404, detail="UTE no encontrada")

        owner_company_id = str(payload.owner_company_id or ute.owner_company_id)
        _assert_companies_exist(db, [owner_company_id])

        ute.name = str(payload.name or ute.name).strip() or ute.name
        ute.owner_company_id = owner_company_id
        if payload.active is not None:
            ute.active = bool(payload.active)
        ute.updated_at = datetime.utcnow()

        if payload.member_company_ids is not None:
            member_ids = [str(item).strip() for item in payload.member_company_ids if str(item).strip()]
            if owner_company_id not in member_ids:
                member_ids.insert(0, owner_company_id)
            member_ids = _assert_companies_exist(db, member_ids)
            db.query(db_models.UTEMemberModel).filter(
                db_models.UTEMemberModel.ute_id == str(ute.id)
            ).delete()
            now = datetime.utcnow()
            seen = set()
            for company_id in member_ids:
                if company_id in seen:
                    continue
                seen.add(company_id)
                db.add(
                    db_models.UTEMemberModel(
                        id=str(uuid4()),
                        ute_id=str(ute.id),
                        company_id=company_id,
                        role="owner" if company_id == owner_company_id else "partner",
                        created_at=now,
                        updated_at=now,
                    )
                )

        db.commit()
        hydrated = db_crud.get_ute(db, str(ute.id))
        if hydrated is None:
            raise HTTPException(status_code=500, detail="UTE actualizada pero no recuperable")
        return _to_ute_response(hydrated)
    finally:
        db.close()


@router.post("/telematics/test-link", response_model=TelematicsLinkTestResponse)
async def test_telematics_binding(payload: TelematicsLinkTestRequest) -> TelematicsLinkTestResponse:
    result = test_telematics_link(
        provider_name=payload.provider,
        external_vehicle_id=payload.external_vehicle_id,
        config=payload.config,
    )
    return TelematicsLinkTestResponse(
        ok=bool(result.get("ok", False)),
        provider=str(result.get("provider", payload.provider)),
        external_vehicle_id=result.get("external_vehicle_id"),
        message=str(result.get("message", "")),
        checked_at=result.get("checked_at"),
    )
