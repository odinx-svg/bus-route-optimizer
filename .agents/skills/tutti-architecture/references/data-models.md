# Modelos de Datos Tutti

## Pydantic Models (backend/models.py)

### Stop
```python
class Stop(BaseModel):
    name: str
    lat: float
    lon: float
    order: int
    time_from_start: int  # minutos
    passengers: int = 0
    is_school: bool = False
```

### Route
```python
class Route(BaseModel):
    id: str
    name: str
    stops: List[Stop]
    school_id: str
    school_name: str
    arrival_time: Optional[time]      # Para entradas
    departure_time: Optional[time]    # Para salidas
    capacity_needed: int
    vehicle_capacity_min: Optional[int]
    vehicle_capacity_max: Optional[int]
    vehicle_capacity_range: Optional[str]
    contract_id: str
    type: str                         # "entry" | "exit"
    days: List[str] = Field(default_factory=list)
    
    @computed_field
    def num_students(self) -> int:
        return sum(stop.passengers for stop in self.stops)
```

### ScheduleItem
```python
class ScheduleItem(BaseModel):
    route_id: str
    start_time: time
    end_time: time
    type: str
    original_start_time: Optional[time]
    time_shift_minutes: int = 0
    deadhead_minutes: int = 0
    positioning_minutes: int = 0
    capacity_needed: int = 0
    vehicle_capacity_min/max/range: Optional[int/str]
    school_name: Optional[str]
    stops: List[Stop]
    contract_id: Optional[str]
```

### BusSchedule
```python
class BusSchedule(BaseModel):
    bus_id: str
    items: List[ScheduleItem]
    last_loc: Optional[Tuple[float, float]]
    min_required_seats: Optional[int]
    uses_fleet_profile: bool = False
    assigned_vehicle_id/code/plate: Optional[str]
    assigned_vehicle_seats_min/max: Optional[int]
```

## SQLAlchemy Models (backend/db/models.py)

### RouteModel
```python
class RouteModel(Base):
    __tablename__ = "routes"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    school_id = Column(String, nullable=False)
    school_name = Column(String, nullable=False)
    arrival_time = Column(Time, nullable=True)
    departure_time = Column(Time, nullable=True)
    capacity_needed = Column(Integer, default=0)
    contract_id = Column(String, nullable=False)
    days = Column(DaysArrayType, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    stops = relationship("StopModel", back_populates="route")
```

### OptimizationWorkspaceModel
```python
class OptimizationWorkspaceModel(Base):
    __tablename__ = "optimization_workspaces"
    
    id = Column(UUIDType, primary_key=True)
    name = Column(String, nullable=False)
    city_label = Column(String, nullable=True)
    archived = Column(Boolean, default=False)
    published_version_id = Column(UUIDType, ForeignKey(...), nullable=True)
    working_version_id = Column(UUIDType, ForeignKey(...), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    versions = relationship("OptimizationWorkspaceVersionModel", ...)
    published_version = relationship(..., foreign_keys=[published_version_id])
    working_version = relationship(..., foreign_keys=[working_version_id])
```

### OptimizationWorkspaceVersionModel
```python
class OptimizationWorkspaceVersionModel(Base):
    __tablename__ = "optimization_workspace_versions"
    
    id = Column(UUIDType, primary_key=True)
    workspace_id = Column(UUIDType, ForeignKey("optimization_workspaces.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    save_kind = Column(String, default="autosave")  # autosave|save|publish|migration
    checkpoint_name = Column(String, nullable=True)
    routes_payload = Column(JSON, default=list)
    schedule_by_day = Column(JSON, default=dict)
    parse_report = Column(JSON, nullable=True)
    validation_report = Column(JSON, nullable=True)
    fleet_snapshot = Column(JSON, nullable=True)
    summary_metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

## Bloques Temporales (Optimizer V6)

| Bloque | Tipo | Horario | Flexibilidad |
|--------|------|---------|--------------|
| 1 | Entrada mañana | 08:00-09:30 | ±5 min |
| 2 | Salida temprana | 14:00-16:10 | -5/+10 min |
| 3 | Entrada tarde | 16:20-16:40 | ±5 min |
| 4 | Salida tarde | 18:20-18:40 | -5/+10 min |

## Estructura schedule_by_day

```json
{
  "L": {
    "schedule": [BusSchedule...],
    "stats": {
      "total_buses": 10,
      "total_entries": 15,
      "total_exits": 12,
      "avg_routes_per_bus": 2.7
    },
    "metadata": {},
    "unassigned_routes": []
  },
  "M": {...},
  "Mc": {...},
  "X": {...},
  "V": {...}
}
```
