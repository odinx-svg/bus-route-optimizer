---
name: tutti-backend-dev
description: Desarrollo backend para Tutti Fleet Optimizer. Usar cuando se necesite crear, modificar o debuggear codigo Python en el backend FastAPI, incluyendo modelos Pydantic, optimizadores (V6), servicios de routing OSRM, logica de negocio, endpoints API, o integracion con base de datos SQLAlchemy.
---

# Tutti Backend Development Skill

## Convenciones de Codigo Python

### Imports (ordenados)
```python
# 1. Standard library
from typing import List, Optional, Dict, Any
from datetime import time, datetime
import logging

# 2. Third party
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import pulp
import pandas as pd

# 3. Local modules
from models import Route, Stop
from router_service import get_real_travel_time
```

### Type Hints
- Siempre usar type hints en funciones y clases
- Usar `Optional[T]` para valores nullable
- Usar `Dict[str, Any]` para diccionarios dinamicos
- Retornar `List[BusSchedule]` en optimizadores

### Docstrings
```python
def optimize_routes(
    routes: List[Route],
    progress_callback: Optional[callable] = None
) -> List[BusSchedule]:
    """
    Optimize routes using ILP.
    
    Args:
        routes: List of Route objects
        progress_callback: Optional callback for progress updates
        
    Returns:
        List of BusSchedule with optimized assignments
    """
```

## Estructura de Modulos

### Creando un Nuevo Endpoint

1. Si es un router grande, crear en `api/nuevo_modulo.py`:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/nuevo", tags=["nuevo"])

@router.get("/items")
async def list_items() -> Dict[str, Any]:
    return {"items": []}
```

2. Registrar en `main.py`:
```python
from api.nuevo_modulo import router as nuevo_router
app.include_router(nuevo_router)
```

### Creando un Nuevo Servicio

Crear en `services/mi_servicio.py`:
```python
"""
Descripcion del servicio.
"""
from typing import List
from models import Route

logger = logging.getLogger(__name__)

def mi_funcion(routes: List[Route]) -> bool:
    """Docstring descriptivo."""
    return True
```

## Optimizer V6 - Guia de Extension

### Constantes Clave (optimizer_v6.py)
```python
MAX_ENTRY_SHIFT_MINUTES = 5          # Entradas: +/- 5 min
MAX_EXIT_EARLY_SHIFT_MINUTES = 5     # Salidas: hasta 5 min antes
MAX_EXIT_LATE_SHIFT_MINUTES = 10     # Salidas: hasta 10 min despues
MIN_CONNECTION_BUFFER_MINUTES = 5    # Buffer entre rutas
CAPACITY_MAX_DIFF = 20               # Diferencia maxima capacidad
```

### Funciones de Feasibility

Para modificar logica de factibilidad entre rutas:

```python
def _build_feasibility_entry(jobs, travel_times):
    """
    Modificar para cambiar cuando una entrada puede seguir a otra.
    Retorna dict[(i,j)] = bool
    """
    feasible = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if not _jobs_capacity_compatible(jobs[i], jobs[j]):
                continue
            # Tu logica aqui
            if puede_conectar:
                feasible[(i, j)] = True
    return feasible
```

### Modificando Scoring

Para ajustar prioridad de emparejamientos:

```python
def _pair_priority_bonus(job_a, job_b) -> float:
    """
    Retornar bonus positivo para emparejamientos deseables.
    """
    bonus = 0.0
    if mismo_colegio(job_a, job_b):
        bonus += 2.0
    if capacidades_similares(job_a, job_b):
        bonus += 1.0
    return bonus
```

## Router Service - OSRM

### Agregando un Nuevo Metodo

```python
def get_custom_metric(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> Optional[int]:
    """
    Get custom routing metric.
    Returns None when OSRM unavailable.
    """
    if _is_circuit_open():
        return None
    
    key = _get_cache_key(lat1, lon1, lat2, lon2)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    
    # Llamada a OSRM
    url = f"{OSRM_API_URL}/..."
    try:
        response = requests.get(url, timeout=OSRM_REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            # Procesar respuesta
            _travel_time_cache[key] = result
            return result
    except Exception as exc:
        _register_osrm_failure()
        logger.warning("Request failed: %s", exc)
    
    return None
```

## Base de Datos

### Agregando un Nuevo Modelo

En `db/models.py`:
```python
class NuevoModelo(Base):
    __tablename__ = "nueva_tabla"
    
    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### CRUD Basico

En `db/crud.py`:
```python
def create_nuevo_item(db: Session, payload: schemas.NuevoCreate) -> NuevoModelo:
    item = NuevoModelo(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def get_nuevo_item(db: Session, item_id: str) -> Optional[NuevoModelo]:
    return db.query(NuevoModelo).filter(NuevoModelo.id == item_id).first()
```

## WebSockets

### Estructura de Mensajes

```python
# Mensaje de progreso
{
    "type": "progress",
    "job_id": "uuid",
    "phase": "baseline_optimize",
    "progress": 45,
    "message": "Optimizando bloque 2/4",
    "stage": "running_v6",
    "day": "L",
    "metrics": {...}
}

# Mensaje completado
{
    "type": "completed",
    "job_id": "uuid",
    "result": {...},
    "stats": {...}
}

# Mensaje error
{
    "type": "error",
    "job_id": "uuid",
    "error_code": "PIPELINE_FAILED",
    "message": "Descripcion del error"
}
```

## Configuracion

Variables de entorno importantes (config.py):
- `CELERY_ENABLED`: Habilitar tareas async
- `USE_DATABASE`: Usar DB (PostgreSQL/SQLite)
- `DATABASE_URL`: URL de conexion
- `OSRM_URL` / `OSRM_TABLE_URL`: Endpoints OSRM
- `APP_RUNTIME_MODE`: "stable" o modo debug

## Testing Backend

Ver skill `tutti-testing` para guia completa de testing.

## Referencias

- `references/optimizer-patterns.md`: Patrones de optimizacion
- `references/db-migrations.md`: Guia de migraciones
