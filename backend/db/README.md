# Tutti Database Module

Módulo de base de datos PostgreSQL para el backend de Tutti usando SQLAlchemy.

## Estructura

```
db/
├── __init__.py              # Exports principales
├── models.py                # Modelos SQLAlchemy
├── database.py              # Configuración de conexión
├── schemas.py               # Schemas Pydantic
├── crud.py                  # Operaciones CRUD
├── migrations/              # Alembic migrations
│   ├── env.py
│   ├── alembic.ini
│   ├── script.py.mako
│   └── versions/
│       └── 2025_02_10_1944-001_initial_migration.py
└── README.md               # Este archivo
```

## Configuración

Variables de entorno:

```bash
# Habilitar/deshabilitar base de datos
USE_DATABASE=true

# URL de conexión PostgreSQL
DATABASE_URL=postgresql://tutti:tutti@localhost:5432/tutti

# Debug SQL
SQLALCHEMY_ECHO=false
```

## Setup Inicial

### 1. Iniciar PostgreSQL (con Docker)

```bash
cd c:\Users\Juanjo\Desktop\ODINX LABS\bus-route-optimizer
docker-compose up -d postgres
```

### 2. Crear Base de Datos (si no existe)

```bash
psql -U postgres -c "CREATE DATABASE tutti;"
psql -U postgres -c "CREATE USER tutti WITH PASSWORD 'tutti';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE tutti TO tutti;"
```

### 3. Ejecutar Migraciones

```bash
cd backend
cd db/migrations
alembic upgrade head
```

O desde el directorio raíz del backend:

```bash
cd backend
python -c "from db.database import create_tables; create_tables()"
```

## Uso

### En FastAPI

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from db.database import get_db
from db import crud, schemas

@app.post("/routes")
def create_route(route: schemas.RouteCreate, db: Session = Depends(get_db)):
    if db is None:
        # Modo sin base de datos - comportamiento legacy
        return {"message": "Database disabled"}
    
    return crud.create_route(db, route)
```

### Guardar rutas desde Excel

```python
from parser import parse_routes
from db import crud, schemas

routes = parse_routes("archivo.xlsx")
for route in routes:
    route_create = schemas.RouteCreate(
        id=route.id,
        name=route.name,
        type=route.type,
        school_id=route.school_id,
        school_name=route.school_name,
        arrival_time=route.arrival_time,
        departure_time=route.departure_time,
        capacity_needed=route.capacity_needed,
        contract_id=route.contract_id,
        days=route.days,
        stops=[
            schemas.StopCreate(
                name=s.name,
                lat=s.lat,
                lon=s.lon,
                order=s.order,
                time_from_start=s.time_from_start,
                passengers=s.passengers,
                is_school=s.is_school
            )
            for s in route.stops
        ]
    )
    crud.create_route(db, route_create)
```

### Tracking de Optimización

```python
from db import crud, schemas
from uuid import uuid4

# Crear job
job = crud.create_optimization_job(db, schemas.OptimizationJobCreate(
    algorithm="v6",
    input_data={"route_ids": [r.id for r in routes]}
))

# Actualizar estado
crud.update_job_status(db, job.id, "running")

# Guardar resultados
crud.create_optimization_results_batch(db, job.id, schedule)

# Completar
crud.update_job_status(db, job.id, "completed", result=result_dict, stats=stats_dict)
```

## Modo Legacy (sin DB)

Para ejecutar sin base de datos:

```bash
USE_DATABASE=false uvicorn main:app --reload
```

El sistema funcionará en modo "in-memory" sin persistencia.

## Comandos Útiles

```bash
# Ver estado de migraciones
alembic current

# Crear nueva migración
alembic revision --autogenerate -m "add new table"

# Upgrade a última versión
alembic upgrade head

# Downgrade una versión
alembic downgrade -1

# Reset completo
alembic downgrade base

# Ver historial
alembic history --verbose
```
