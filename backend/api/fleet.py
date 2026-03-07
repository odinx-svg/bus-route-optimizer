"""
Fleet Management API.

Provides CRUD endpoints for vehicle profiles used by operations/planning.
DB-first with JSON fallback.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator

from services.fleet_repository import FleetRepository
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
    vehicle_code: str = Field(min_length=1, max_length=32)
    plate: str = Field(min_length=1, max_length=32)
    brand: Optional[str] = Field(default=None, max_length=80)
    model: Optional[str] = Field(default=None, max_length=80)
    year: Optional[int] = Field(default=None, ge=1980, le=2100)
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
        vehicle_code=str(vehicle.get("vehicle_code", "") or ""),
        plate=str(vehicle.get("plate", "") or ""),
        brand=vehicle.get("brand"),
        model=vehicle.get("model"),
        year=year,
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


@router.get("/vehicles", response_model=FleetListResponse)
async def list_vehicles(company_id: Optional[str] = Query(default=None)) -> FleetListResponse:
    vehicles_raw = fleet_repository.list_vehicles(company_id=company_id)
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

