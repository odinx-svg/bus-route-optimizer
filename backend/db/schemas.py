"""
Pydantic schemas for database operations.

These schemas are used for:
- Request validation (input data)
- Response serialization (output data)
- Type safety between API and database

Note: These are separate from the domain models in models.py (Route, Stop, etc.)
"""

from datetime import datetime, time
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


# =============================================================================
# Stop Schemas
# =============================================================================

class StopBase(BaseModel):
    """Base schema for Stop (common fields)"""
    name: str
    lat: float
    lon: float
    order: int
    time_from_start: int = 0
    passengers: int = 0
    is_school: bool = False


class StopCreate(StopBase):
    """Schema for creating a new stop"""
    pass


class StopResponse(StopBase):
    """Schema for stop response from database with frontend-compatible fields"""
    id: UUID
    route_id: str
    
    # Computed fields for frontend compatibility
    @computed_field
    @property
    def stop_id(self) -> str:
        """Stop ID alias for frontend."""
        return str(self.id)
    
    @computed_field
    @property
    def stop_name(self) -> str:
        """Stop name alias for frontend."""
        return self.name
    
    @computed_field
    @property
    def latitude(self) -> float:
        """Latitude alias for frontend."""
        return self.lat
    
    @computed_field
    @property
    def longitude(self) -> float:
        """Longitude alias for frontend."""
        return self.lon

    class Config:
        from_attributes = True


# =============================================================================
# Route Schemas
# =============================================================================

class RouteBase(BaseModel):
    """Base schema for Route (common fields)"""
    id: str
    name: str
    type: str  # 'entry' or 'exit'
    school_id: str
    school_name: str
    arrival_time: Optional[time] = None
    departure_time: Optional[time] = None
    capacity_needed: int = 0
    contract_id: str
    days: List[str] = Field(default_factory=list)


class RouteCreate(RouteBase):
    """Schema for creating a new route with stops"""
    stops: List[StopCreate] = Field(default_factory=list)


class RouteResponse(RouteBase):
    """Schema for route response from database"""
    created_at: datetime
    stops: List[StopResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class RouteSummary(BaseModel):
    """Lightweight route schema for lists"""
    id: str
    name: str
    type: str
    school_name: str
    arrival_time: Optional[time] = None
    departure_time: Optional[time] = None
    capacity_needed: int
    stops_count: int

    class Config:
        from_attributes = True


# =============================================================================
# Route Editor Schemas
# =============================================================================

class StopEditorSchema(BaseModel):
    """Schema for editing a stop in a route"""
    name: str
    lat: float
    lon: float
    order: int
    time_from_start: int = 0
    passengers: int = 0
    is_school: bool = False


class RouteUpdateRequest(BaseModel):
    """Schema for PATCH /api/routes/{route_id} - Update route data"""
    start_time: Optional[str] = Field(None, description="Start time in HH:MM format")
    end_time: Optional[str] = Field(None, description="End time in HH:MM format")
    stops: Optional[List[StopEditorSchema]] = Field(None, description="Updated list of stops")
    is_locked: Optional[bool] = Field(None, description="Lock/unlock the route")
    bus_id: Optional[str] = Field(None, description="Assigned bus ID")
    time_shift_minutes: Optional[int] = Field(None, description="Time shift in minutes (positive or negative)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_time": "08:30",
                "end_time": "09:15",
                "stops": [
                    {"name": "Stop 1", "lat": 42.23, "lon": -8.72, "order": 1, "time_from_start": 0, "passengers": 5},
                    {"name": "School", "lat": 42.24, "lon": -8.73, "order": 2, "time_from_start": 15, "is_school": True}
                ],
                "is_locked": True,
                "bus_id": "B001",
                "time_shift_minutes": 5
            }
        }


class RouteUpdateResponse(BaseModel):
    """Schema for route update response"""
    success: bool
    route_id: str
    message: str
    changes: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class ToggleLockRequest(BaseModel):
    """Schema for POST /api/routes/{route_id}/toggle-lock"""
    is_locked: Optional[bool] = Field(None, description="Set specific lock state, or toggle if null")
    reason: Optional[str] = Field(None, description="Optional reason for locking")


class ToggleLockResponse(BaseModel):
    """Schema for toggle lock response"""
    success: bool
    route_id: str
    is_locked: bool
    message: str
    previous_state: Optional[bool] = None
    reason: Optional[str] = None


class ScheduleItemEditorSchema(BaseModel):
    """Schema for schedule item in editor"""
    route_id: str
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format
    type: str  # "entry" or "exit"
    original_start_time: Optional[str] = None
    time_shift_minutes: int = 0
    deadhead_minutes: int = 0
    school_name: Optional[str] = None
    stops: List[StopEditorSchema] = Field(default_factory=list)
    contract_id: Optional[str] = None
    is_locked: bool = False


class BusEditorSchema(BaseModel):
    """Schema for bus in schedule editor"""
    bus_id: str
    items: List[ScheduleItemEditorSchema]
    capacity: Optional[int] = None
    plate: Optional[str] = None


class UnassignedRouteSchema(BaseModel):
    """Schema for unassigned routes in schedule update"""
    route_id: str
    reason: Optional[str] = None
    suggested_buses: List[str] = Field(default_factory=list)


class ScheduleUpdateRequest(BaseModel):
    """Schema for POST /api/schedules/update - Save schedule changes"""
    day: str = Field(..., description="Day code: L, M, Mc, X, V")
    buses: List[BusEditorSchema]
    unassigned_routes: List[UnassignedRouteSchema] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata like optimizer version")
    
    class Config:
        json_schema_extra = {
            "example": {
                "day": "L",
                "buses": [
                    {
                        "bus_id": "B001",
                        "capacity": 55,
                        "items": [
                            {
                                "route_id": "R001",
                                "start_time": "08:00",
                                "end_time": "08:45",
                                "type": "entry",
                                "stops": []
                            }
                        ]
                    }
                ],
                "unassigned_routes": []
            }
        }


class ValidationError(BaseModel):
    """Schema for validation errors"""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ScheduleUpdateResponse(BaseModel):
    """Schema for schedule update response"""
    success: bool
    day: str
    saved_at: datetime
    total_buses: int
    total_routes: int
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)


class RouteConflict(BaseModel):
    """Schema for route conflicts in validation"""
    route_id: str
    conflict_type: str  # "time_overlap", "invalid_coordinates", "time_shift_exceeded"
    bus_id: str
    conflicting_with: Optional[str] = None
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Schema for validation results"""
    is_valid: bool
    conflicts: List[RouteConflict] = Field(default_factory=list)
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)


# =============================================================================
# Optimization Job Schemas
# =============================================================================

class OptimizationJobBase(BaseModel):
    """Base schema for Optimization Job"""
    algorithm: str = "v6"
    input_data: Optional[Dict[str, Any]] = None


class OptimizationJobCreate(OptimizationJobBase):
    """Schema for creating a new optimization job"""
    pass


class OptimizationJobUpdate(BaseModel):
    """Schema for updating job status"""
    status: str  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class OptimizationJobResponse(OptimizationJobBase):
    """Schema for job response from database"""
    id: UUID
    status: str
    result: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Optimization Result Schemas
# =============================================================================

class OptimizationResultBase(BaseModel):
    """Base schema for Optimization Result"""
    route_id: str
    bus_id: str
    start_time: time
    end_time: time
    time_shift_minutes: int = 0
    deadhead_minutes: int = 0


class OptimizationResultCreate(OptimizationResultBase):
    """Schema for creating a new optimization result"""
    job_id: UUID


class OptimizationResultResponse(OptimizationResultBase):
    """Schema for result response from database"""
    id: UUID
    job_id: UUID
    route: Optional[RouteSummary] = None

    class Config:
        from_attributes = True


# =============================================================================
# Schedule Item Schema (for optimization input/output)
# =============================================================================

class ScheduleItemSchema(BaseModel):
    """Schema for schedule item (matches optimizer output)"""
    route_id: str
    start_time: time
    end_time: time
    type: str
    original_start_time: Optional[time] = None
    time_shift_minutes: int = 0
    deadhead_minutes: int = 0
    school_name: Optional[str] = None
    stops: List[StopBase] = Field(default_factory=list)
    contract_id: Optional[str] = None


class BusScheduleSchema(BaseModel):
    """Schema for bus schedule (matches optimizer output)"""
    bus_id: str
    items: List[ScheduleItemSchema]
    last_loc: Optional[tuple] = None


# =============================================================================
# Statistics Schema
# =============================================================================

class OptimizationStats(BaseModel):
    """Schema for optimization statistics"""
    total_buses: int
    total_routes: int
    total_entries: int
    total_exits: int
    max_entries_per_bus: int
    max_exits_per_bus: int
    buses_with_both: int
    avg_routes_per_bus: float
    total_early_shift_minutes: int


class OptimizationResponse(BaseModel):
    """Complete optimization response"""
    schedule: List[BusScheduleSchema]
    stats: OptimizationStats
