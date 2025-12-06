from pydantic import BaseModel
from typing import List, Optional, Tuple
from datetime import time

class Stop(BaseModel):
    name: str
    lat: float
    lon: float
    order: int
    time_from_start: int  # minutes
    is_school: bool = False

class Route(BaseModel):
    id: str
    name: str
    stops: List[Stop]
    school_id: str
    school_name: str
    arrival_time: Optional[time] = None  # For entry routes
    departure_time: Optional[time] = None # For exit routes
    capacity_needed: int
    contract_id: str
    type: str # "entry" or "exit"

class Bus(BaseModel):
    id: str
    capacity: int
    plate: Optional[str] = None

class ScheduleItem(BaseModel):
    route_id: str
    start_time: time
    end_time: time
    type: str
    original_start_time: Optional[time] = None
    time_shift_minutes: int = 0
    deadhead_minutes: int = 0

class BusSchedule(BaseModel):
    bus_id: str
    items: List[ScheduleItem]
    last_loc: Optional[Tuple[float, float]] = None
