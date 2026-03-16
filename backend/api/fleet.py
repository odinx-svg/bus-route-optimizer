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


class VehicleDriverAssignmentResponse(BaseModel):
    id: Optional[str] = None
    day_code: str
    day_label: str
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    driver_status: Optional[str] = None
    preferred_channel: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    notes: Optional[str] = None


class FleetVehicleResponse(FleetVehicleBase):
    id: str
    created_at: str
    updated_at: str
    age_years: Optional[int] = None
    default_driver_id: Optional[str] = None
    default_driver_name: Optional[str] = None
    default_driver_phone: Optional[str] = None
    default_driver_channel: Optional[str] = None
    driver_assignments: List[VehicleDriverAssignmentResponse] = Field(default_factory=list)


class FleetDriverBase(BaseModel):
    company_id: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=120)
    preferred_channel: Literal["manual", "whatsapp", "telegram", "call"] = "manual"
    whatsapp_phone: Optional[str] = Field(default=None, max_length=40)
    telegram_chat_id: Optional[str] = Field(default=None, max_length=120)
    status: Literal["active", "inactive"] = "active"
    notes: Optional[str] = Field(default=None, max_length=1200)


class FleetDriverCreate(FleetDriverBase):
    pass


class FleetDriverUpdate(FleetDriverBase):
    pass


class FleetDriverResponse(FleetDriverBase):
    id: str
    company_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class VehicleDriverAssignmentInput(BaseModel):
    day_code: Literal["default", "L", "M", "Mc", "X", "V"]
    driver_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class VehicleDriverAssignmentsUpdateRequest(BaseModel):
    default_driver_id: Optional[str] = None
    assignments: List[VehicleDriverAssignmentInput] = Field(default_factory=list)


class VehicleDriverAssignmentsResponse(BaseModel):
    vehicle_id: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    default_driver_id: Optional[str] = None
    default_driver_name: Optional[str] = None
    driver_assignments: List[VehicleDriverAssignmentResponse] = Field(default_factory=list)


class FleetSummary(BaseModel):
    total: int
    active: int
    maintenance: int
    inactive: int
    total_seats_max: int
    avg_seats_max: float


class CompanyFleetSummaryResponse(BaseModel):
    id: str
    name: str
    is_default: bool = False
    vehicle_count: int = 0
    active_vehicle_count: int = 0
    total_seats_max: int = 0


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


class VehicleWeeklyPlanAssignmentResponse(BaseModel):
    day: str
    day_label: str
    bus_id: str
    route_id: str
    start_minute: int
    end_minute: int
    start_time: str
    end_time: str
    workspace_id: str
    workspace_name: Optional[str] = None
    workspace_version_id: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    assignment_type: str = "real"
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    preferred_channel: Optional[str] = None


class VehicleWeeklyPlanDayResponse(BaseModel):
    day: str
    day_label: str
    route_count: int = 0
    first_start_minute: Optional[int] = None
    last_end_minute: Optional[int] = None
    assignments: List[VehicleWeeklyPlanAssignmentResponse] = Field(default_factory=list)


class VehicleWeeklyPlanResponse(BaseModel):
    vehicle_id: str
    vehicle_code: Optional[str] = None
    plate: Optional[str] = None
    total_assignments: int = 0
    total_routes: int = 0
    total_days_with_service: int = 0
    total_workspaces: int = 0
    default_driver_id: Optional[str] = None
    default_driver_name: Optional[str] = None
    default_driver_phone: Optional[str] = None
    default_driver_channel: Optional[str] = None
    days: List[VehicleWeeklyPlanDayResponse] = Field(default_factory=list)


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
        default_driver_id=str(vehicle.get("default_driver_id", "") or "") or None,
        default_driver_name=str(vehicle.get("default_driver_name", "") or "") or None,
        default_driver_phone=str(vehicle.get("default_driver_phone", "") or "") or None,
        default_driver_channel=str(vehicle.get("default_driver_channel", "") or "") or None,
        driver_assignments=[_serialize_driver_assignment(item) for item in (vehicle.get("driver_assignments", []) or []) if isinstance(item, dict)],
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


DAY_LABELS = {
    "default": "Habitual",
    "L": "Lunes",
    "M": "Martes",
    "Mc": "Miercoles",
    "X": "Jueves",
    "V": "Viernes",
}


def _minute_to_hhmm(value: int) -> str:
    safe = max(0, int(value or 0))
    hours = safe // 60
    minutes = safe % 60
    return f"{hours:02d}:{minutes:02d}"


def _serialize_driver_assignment(raw: Dict[str, Any]) -> VehicleDriverAssignmentResponse:
    day_code = str(raw.get("day_code", "default") or "default")
    return VehicleDriverAssignmentResponse(
        id=str(raw.get("id", "") or "") or None,
        day_code=day_code,
        day_label=DAY_LABELS.get(day_code, day_code),
        driver_id=str(raw.get("driver_id", "") or "") or None,
        driver_name=str(raw.get("driver_name", "") or "") or None,
        driver_phone=str(raw.get("driver_phone", "") or "") or None,
        driver_status=str(raw.get("driver_status", "") or "") or None,
        preferred_channel=str(raw.get("preferred_channel", "") or "") or None,
        company_id=str(raw.get("company_id", "") or "") or None,
        company_name=str(raw.get("company_name", "") or "") or None,
        notes=str(raw.get("notes", "") or "") or None,
    )


def _driver_assignment_map(vehicle: dict) -> Dict[str, Dict[str, Any]]:
    assignments = vehicle.get("driver_assignments", []) or []
    mapping: Dict[str, Dict[str, Any]] = {}
    for raw in assignments:
        if isinstance(raw, dict):
            day_code = str(raw.get("day_code", "default") or "default").strip() or "default"
            mapping[day_code] = raw
    return mapping


def _resolve_driver_for_day(vehicle: dict, day: str) -> Optional[Dict[str, Any]]:
    mapping = _driver_assignment_map(vehicle)
    return mapping.get(day) or mapping.get("default")


def _serialize_driver(driver) -> FleetDriverResponse:
    return FleetDriverResponse(
        id=str(driver.id),
        company_id=str(driver.company_id),
        company_name=str(driver.company.name or "") if driver.company else None,
        full_name=str(driver.full_name or ""),
        phone=str(driver.phone or "") or None,
        email=str(driver.email or "") or None,
        preferred_channel=str(driver.preferred_channel or "manual"),
        whatsapp_phone=str(driver.whatsapp_phone or "") or None,
        telegram_chat_id=str(driver.telegram_chat_id or "") or None,
        status=str(driver.status or "active"),
        notes=str(driver.notes or "") or None,
        created_at=driver.created_at.isoformat() if driver.created_at else None,
        updated_at=driver.updated_at.isoformat() if driver.updated_at else None,
    )


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


@router.get("/companies", response_model=List[CompanyFleetSummaryResponse])
async def list_fleet_companies(active_only: bool = Query(default=True)) -> List[CompanyFleetSummaryResponse]:
    _require_db()
    db = SessionLocal()
    try:
        companies = db_crud.list_companies(db, active_only=active_only)
        rows: List[CompanyFleetSummaryResponse] = []
        for company in companies:
            vehicles = fleet_repository.list_vehicles(company_id=str(company.id))
            active_vehicles = [
                vehicle for vehicle in vehicles
                if str(vehicle.get("status", "active") or "active").strip().lower() == "active"
            ]
            rows.append(
                CompanyFleetSummaryResponse(
                    id=str(company.id),
                    name=str(company.name or ""),
                    is_default=bool(company.is_default),
                    vehicle_count=len(vehicles),
                    active_vehicle_count=len(active_vehicles),
                    total_seats_max=sum(int(vehicle.get("seats_max", 0) or 0) for vehicle in active_vehicles),
                )
            )
        return rows
    finally:
        db.close()


@router.get("/drivers", response_model=List[FleetDriverResponse])
async def list_fleet_drivers(
    company_id: Optional[str] = Query(default=None),
    active_only: bool = Query(default=False),
) -> List[FleetDriverResponse]:
    _require_db()
    db = SessionLocal()
    try:
        query = db.query(db_models.DriverModel).outerjoin(db_models.CompanyModel)
        if company_id:
            query = query.filter(db_models.DriverModel.company_id == str(company_id).strip())
        if active_only:
            query = query.filter(db_models.DriverModel.status == "active")
        rows = query.order_by(db_models.DriverModel.full_name.asc()).all()
        return [_serialize_driver(row) for row in rows]
    finally:
        db.close()


@router.post("/drivers", response_model=FleetDriverResponse, status_code=status.HTTP_201_CREATED)
async def create_fleet_driver(payload: FleetDriverCreate) -> FleetDriverResponse:
    _require_db()
    db = SessionLocal()
    try:
        company = db_crud.get_company(db, str(payload.company_id).strip())
        if company is None:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        now = datetime.utcnow()
        driver = db_models.DriverModel(
            id=str(uuid4()),
            company_id=str(payload.company_id).strip(),
            full_name=str(payload.full_name).strip(),
            phone=str(payload.phone or "").strip() or None,
            email=str(payload.email or "").strip() or None,
            preferred_channel=str(payload.preferred_channel or "manual"),
            whatsapp_phone=str(payload.whatsapp_phone or "").strip() or None,
            telegram_chat_id=str(payload.telegram_chat_id or "").strip() or None,
            status=str(payload.status or "active"),
            notes=str(payload.notes or "").strip() or None,
            created_at=now,
            updated_at=now,
        )
        db.add(driver)
        db.commit()
        db.refresh(driver)
        return _serialize_driver(driver)
    finally:
        db.close()


@router.put("/drivers/{driver_id}", response_model=FleetDriverResponse)
async def update_fleet_driver(driver_id: str, payload: FleetDriverUpdate) -> FleetDriverResponse:
    _require_db()
    db = SessionLocal()
    try:
        driver = db.query(db_models.DriverModel).filter(db_models.DriverModel.id == str(driver_id)).first()
        if driver is None:
            raise HTTPException(status_code=404, detail="Conductor no encontrado")
        company = db_crud.get_company(db, str(payload.company_id).strip())
        if company is None:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        driver.company_id = str(payload.company_id).strip()
        driver.full_name = str(payload.full_name).strip()
        driver.phone = str(payload.phone or "").strip() or None
        driver.email = str(payload.email or "").strip() or None
        driver.preferred_channel = str(payload.preferred_channel or "manual")
        driver.whatsapp_phone = str(payload.whatsapp_phone or "").strip() or None
        driver.telegram_chat_id = str(payload.telegram_chat_id or "").strip() or None
        driver.status = str(payload.status or "active")
        driver.notes = str(payload.notes or "").strip() or None
        driver.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(driver)
        return _serialize_driver(driver)
    finally:
        db.close()


@router.delete("/drivers/{driver_id}")
async def delete_fleet_driver(driver_id: str) -> dict:
    _require_db()
    db = SessionLocal()
    try:
        driver = db.query(db_models.DriverModel).filter(db_models.DriverModel.id == str(driver_id)).first()
        if driver is None:
            raise HTTPException(status_code=404, detail="Conductor no encontrado")
        db.delete(driver)
        db.commit()
        return {"success": True, "driver_id": str(driver_id)}
    finally:
        db.close()


@router.put("/vehicles/{vehicle_id}/drivers", response_model=VehicleDriverAssignmentsResponse)
async def update_vehicle_driver_assignments(
    vehicle_id: str,
    payload: VehicleDriverAssignmentsUpdateRequest,
    company_id: Optional[str] = Query(default=None),
) -> VehicleDriverAssignmentsResponse:
    _require_db()
    db = SessionLocal()
    try:
        vehicle = db.query(db_models.FleetVehicleModel).filter(
            db_models.FleetVehicleModel.id == str(vehicle_id)
        ).first()
        if vehicle is None:
            raise HTTPException(status_code=404, detail="Vehiculo no encontrado")
        if company_id and str(vehicle.company_id) != str(company_id).strip():
            raise HTTPException(status_code=404, detail="Vehiculo no encontrado")

        requested_driver_ids: List[str] = []
        if payload.default_driver_id:
            requested_driver_ids.append(str(payload.default_driver_id).strip())
        for item in payload.assignments:
            if item.driver_id:
                requested_driver_ids.append(str(item.driver_id).strip())

        drivers_by_id: Dict[str, Any] = {}
        if requested_driver_ids:
            rows = db.query(db_models.DriverModel).filter(db_models.DriverModel.id.in_(requested_driver_ids)).all()
            drivers_by_id = {str(row.id): row for row in rows}
            missing = [driver_id for driver_id in requested_driver_ids if driver_id not in drivers_by_id]
            if missing:
                raise HTTPException(status_code=404, detail=f"Conductores no encontrados: {', '.join(missing)}")
            if any(str(row.company_id) != str(vehicle.company_id) for row in rows):
                raise HTTPException(status_code=400, detail="Todos los conductores deben pertenecer a la empresa del vehiculo")

        db.query(db_models.FleetVehicleDriverAssignmentModel).filter(
            db_models.FleetVehicleDriverAssignmentModel.vehicle_id == str(vehicle.id)
        ).delete()

        now = datetime.utcnow()
        persisted: List[VehicleDriverAssignmentResponse] = []

        def _store(day_code: str, driver_id: str, notes: Optional[str] = None) -> None:
            driver = drivers_by_id.get(driver_id)
            row = db_models.FleetVehicleDriverAssignmentModel(
                id=str(uuid4()),
                vehicle_id=str(vehicle.id),
                driver_id=str(driver_id),
                day_code=str(day_code),
                notes=str(notes or "").strip() or None,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            persisted.append(
                VehicleDriverAssignmentResponse(
                    id=str(row.id),
                    day_code=str(day_code),
                    day_label=DAY_LABELS.get(str(day_code), str(day_code)),
                    driver_id=str(driver_id),
                    driver_name=str(driver.full_name or "") if driver else None,
                    driver_phone=(str(driver.phone or "") or None) if driver else None,
                    driver_status=str(driver.status or "active") if driver else None,
                    preferred_channel=str(driver.preferred_channel or "manual") if driver else None,
                    company_id=str(driver.company_id) if driver else None,
                    company_name=str(driver.company.name or "") if driver and driver.company else None,
                    notes=str(notes or "").strip() or None,
                )
            )

        if payload.default_driver_id:
            _store("default", str(payload.default_driver_id).strip())

        seen_days = set()
        for item in payload.assignments:
            day_code = str(item.day_code or "").strip()
            if day_code == "default" or day_code in seen_days or not item.driver_id:
                continue
            seen_days.add(day_code)
            _store(day_code, str(item.driver_id).strip(), item.notes)

        db.commit()

        default_assignment = next((item for item in persisted if item.day_code == "default"), None)
        return VehicleDriverAssignmentsResponse(
            vehicle_id=str(vehicle.id),
            company_id=str(vehicle.company_id),
            company_name=str(vehicle.company.name or "") if vehicle.company else None,
            default_driver_id=default_assignment.driver_id if default_assignment else None,
            default_driver_name=default_assignment.driver_name if default_assignment else None,
            driver_assignments=sorted(
                persisted,
                key=lambda item: (0 if item.day_code == "default" else 1, item.day_code),
            ),
        )
    finally:
        db.close()


@router.get("/vehicles/{vehicle_id}", response_model=FleetVehicleResponse)
async def get_vehicle(vehicle_id: str, company_id: Optional[str] = Query(default=None)) -> FleetVehicleResponse:
    vehicle = fleet_repository.get_vehicle(vehicle_id, company_id=company_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado")
    return _to_response(vehicle)


@router.get("/vehicles/{vehicle_id}/weekly-plan", response_model=VehicleWeeklyPlanResponse)
async def get_vehicle_weekly_plan(vehicle_id: str, company_id: Optional[str] = Query(default=None)) -> VehicleWeeklyPlanResponse:
    _require_db()
    vehicle = fleet_repository.get_vehicle(vehicle_id, company_id=company_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehiculo no encontrado")

    db = SessionLocal()
    try:
        rows = (
            db.query(
                db_models.PublishedFleetAssignmentModel,
                db_models.OptimizationWorkspaceModel.name,
                db_models.CompanyModel.name,
            )
            .outerjoin(
                db_models.OptimizationWorkspaceModel,
                db_models.OptimizationWorkspaceModel.id == db_models.PublishedFleetAssignmentModel.workspace_id,
            )
            .outerjoin(
                db_models.CompanyModel,
                db_models.CompanyModel.id == db_models.PublishedFleetAssignmentModel.company_id,
            )
            .filter(
                db_models.PublishedFleetAssignmentModel.assigned_vehicle_id == str(vehicle_id),
                db_models.PublishedFleetAssignmentModel.active.is_(True),
            )
            .order_by(
                db_models.PublishedFleetAssignmentModel.day.asc(),
                db_models.PublishedFleetAssignmentModel.start_minute.asc(),
                db_models.PublishedFleetAssignmentModel.route_id.asc(),
            )
            .all()
        )

        assignments_by_day: Dict[str, List[VehicleWeeklyPlanAssignmentResponse]] = {day: [] for day in DAY_LABELS}
        workspace_ids = set()
        for assignment_row, workspace_name, company_name in rows:
            day = str(assignment_row.day or "").strip()
            driver_for_day = _resolve_driver_for_day(vehicle, day)
            assignment = VehicleWeeklyPlanAssignmentResponse(
                day=day,
                day_label=DAY_LABELS.get(day, day),
                bus_id=str(assignment_row.bus_id or ""),
                route_id=str(assignment_row.route_id or ""),
                start_minute=int(assignment_row.start_minute or 0),
                end_minute=int(assignment_row.end_minute or 0),
                start_time=_minute_to_hhmm(int(assignment_row.start_minute or 0)),
                end_time=_minute_to_hhmm(int(assignment_row.end_minute or 0)),
                workspace_id=str(assignment_row.workspace_id or ""),
                workspace_name=str(workspace_name or "") or None,
                workspace_version_id=str(assignment_row.workspace_version_id or ""),
                company_id=str(assignment_row.company_id or "") or None,
                company_name=str(company_name or "") or None,
                assignment_type=str(assignment_row.assignment_type or "real"),
                driver_id=str(driver_for_day.get("driver_id", "") or "") or None if driver_for_day else None,
                driver_name=str(driver_for_day.get("driver_name", "") or "") or None if driver_for_day else None,
                driver_phone=str(driver_for_day.get("driver_phone", "") or "") or None if driver_for_day else None,
                preferred_channel=str(driver_for_day.get("preferred_channel", "") or "") or None if driver_for_day else None,
            )
            assignments_by_day.setdefault(day, []).append(assignment)
            workspace_ids.add(str(assignment_row.workspace_id or ""))

        days: List[VehicleWeeklyPlanDayResponse] = []
        for day in ("L", "M", "Mc", "X", "V"):
            assignments = assignments_by_day.get(day, [])
            days.append(
                VehicleWeeklyPlanDayResponse(
                    day=day,
                    day_label=DAY_LABELS.get(day, day),
                    route_count=len(assignments),
                    first_start_minute=min((item.start_minute for item in assignments), default=None),
                    last_end_minute=max((item.end_minute for item in assignments), default=None),
                    assignments=assignments,
                )
            )

        total_assignments = sum(day.route_count for day in days)
        return VehicleWeeklyPlanResponse(
            vehicle_id=str(vehicle_id),
            vehicle_code=str(vehicle.get("vehicle_code", "") or "") or None,
            plate=str(vehicle.get("plate", "") or "") or None,
            total_assignments=total_assignments,
            total_routes=total_assignments,
            total_days_with_service=sum(1 for day in days if day.route_count > 0),
            total_workspaces=len([workspace_id for workspace_id in workspace_ids if workspace_id]),
            default_driver_id=str(vehicle.get("default_driver_id", "") or "") or None,
            default_driver_name=str(vehicle.get("default_driver_name", "") or "") or None,
            default_driver_phone=str(vehicle.get("default_driver_phone", "") or "") or None,
            default_driver_channel=str(vehicle.get("default_driver_channel", "") or "") or None,
            days=days,
        )
    finally:
        db.close()


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
