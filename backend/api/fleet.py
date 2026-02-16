"""
Fleet Management API.

Provides CRUD endpoints for vehicle profiles used by operations/planning.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from services.fleet_registry import FleetRegistry

router = APIRouter(prefix="/api/fleet", tags=["fleet"])
fleet_registry = FleetRegistry()


class VehicleDocument(BaseModel):
    id: Optional[str] = None
    doc_type: str = Field(default="", max_length=80)
    reference: str = Field(default="", max_length=120)
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class FleetVehicleBase(BaseModel):
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


def _to_response(vehicle: dict) -> FleetVehicleResponse:
    current_year = datetime.utcnow().year
    year = vehicle.get("year")
    age_years: Optional[int] = None
    if isinstance(year, int) and 1980 <= year <= 2100:
        age_years = max(0, current_year - year)
    return FleetVehicleResponse(
        id=str(vehicle.get("id", "")),
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
async def list_vehicles() -> FleetListResponse:
    vehicles_raw = fleet_registry.list_vehicles()
    vehicles = [_to_response(v) for v in vehicles_raw]
    return FleetListResponse(vehicles=vehicles, summary=_build_summary(vehicles))


@router.get("/vehicles/{vehicle_id}", response_model=FleetVehicleResponse)
async def get_vehicle(vehicle_id: str) -> FleetVehicleResponse:
    vehicle = fleet_registry.get_vehicle(vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado")
    return _to_response(vehicle)


@router.post("/vehicles", response_model=FleetVehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(payload: FleetVehicleCreate) -> FleetVehicleResponse:
    try:
        created = fleet_registry.create_vehicle(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(created)


@router.put("/vehicles/{vehicle_id}", response_model=FleetVehicleResponse)
async def update_vehicle(vehicle_id: str, payload: FleetVehicleUpdate) -> FleetVehicleResponse:
    try:
        updated = fleet_registry.update_vehicle(vehicle_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(updated)


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: str) -> dict:
    deleted = fleet_registry.delete_vehicle(vehicle_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado")
    return {"success": True, "vehicle_id": vehicle_id}

