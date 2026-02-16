"""
Pydantic models for Tutti bus route optimization.
"""

from pydantic import BaseModel, Field, computed_field
from typing import List, Optional, Tuple
from datetime import time


class Stop(BaseModel):
    """Represents a bus stop with geographic coordinates and timing info."""
    
    name: str
    lat: float
    lon: float
    order: int
    time_from_start: int  # minutes
    passengers: int = 0  # number of passengers boarding at this stop
    is_school: bool = False
    
    @computed_field
    @property
    def latitude(self) -> float:
        """Latitude alias for frontend compatibility."""
        return self.lat
    
    @computed_field
    @property
    def longitude(self) -> float:
        """Longitude alias for frontend compatibility."""
        return self.lon


class Route(BaseModel):
    """Represents a bus route with multiple stops."""
    
    id: str
    name: str
    stops: List[Stop]
    school_id: str
    school_name: str
    arrival_time: Optional[time] = None  # For entry routes
    departure_time: Optional[time] = None  # For exit routes
    capacity_needed: int
    vehicle_capacity_min: Optional[int] = None
    vehicle_capacity_max: Optional[int] = None
    vehicle_capacity_range: Optional[str] = None
    contract_id: str
    type: str  # "entry" or "exit"
    days: List[str] = Field(default_factory=list)  # e.g. ["L","M","Mc","X","V"] for weekdays this route runs
    
    @computed_field
    @property
    def num_students(self) -> int:
        """Total students across all stops."""
        return sum(stop.passengers for stop in self.stops)


class Bus(BaseModel):
    """Represents a bus with capacity and identification."""
    
    id: str
    capacity: int
    plate: Optional[str] = None


class ScheduleItem(BaseModel):
    """Represents a single scheduled route assignment for a bus."""
    
    route_id: str
    start_time: time
    end_time: time
    type: str
    original_start_time: Optional[time] = None
    time_shift_minutes: int = 0
    deadhead_minutes: int = 0
    positioning_minutes: int = 0
    capacity_needed: int = 0
    vehicle_capacity_min: Optional[int] = None
    vehicle_capacity_max: Optional[int] = None
    vehicle_capacity_range: Optional[str] = None
    school_name: Optional[str] = None
    stops: List[Stop] = Field(default_factory=list)
    contract_id: Optional[str] = None


class BusSchedule(BaseModel):
    """Represents a complete schedule for one bus across multiple routes."""
    
    bus_id: str
    items: List[ScheduleItem]
    last_loc: Optional[Tuple[float, float]] = None
    min_required_seats: Optional[int] = None
    uses_fleet_profile: bool = False
    assigned_vehicle_id: Optional[str] = None
    assigned_vehicle_code: Optional[str] = None
    assigned_vehicle_plate: Optional[str] = None
    assigned_vehicle_seats_min: Optional[int] = None
    assigned_vehicle_seats_max: Optional[int] = None


# Type aliases for common patterns
RouteList = List[Route]
StopList = List[Stop]
BusScheduleList = List[BusSchedule]
