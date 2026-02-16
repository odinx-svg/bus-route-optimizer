# Setup de Base de Datos - Tutti

Guía completa para configurar PostgreSQL en el backend de Tutti.

## Requisitos Previos

- Docker Desktop instalado (para PostgreSQL)
- Python 3.11+ con el entorno virtual activado
- Dependencias instaladas: `pip install -r requirements.txt`

## Quick Start

### 1. Iniciar PostgreSQL con Docker

```bash
cd c:\Users\Juanjo\Desktop\ODINX LABS\bus-route-optimizer
docker-compose up -d postgres
```

Esto inicia PostgreSQL en el puerto 5432 con:
- Database: `tutti`
- User: `tutti`
- Password: `tutti`

### 2. Verificar que PostgreSQL está corriendo

```bash
docker-compose ps
```

Deberías ver `tutti-postgres` con estado `Up`.

### 3. Configurar variables de entorno

```bash
cd backend
copy .env.example .env
```

Asegúrate de que `.env` tenga:
```env
USE_DATABASE=true
DATABASE_URL=postgresql://tutti:tutti@localhost:5432/tutti
```

### 4. Ejecutar migraciones

```bash
# Desde el directorio backend
cd db/migrations
alembic upgrade head
```

O desde cualquier directorio:
```bash
cd backend/db/migrations
python -m alembic upgrade head
```

### 5. Verificar instalación

```bash
# Health check del API
curl http://localhost:8000/health

# Debería retornar:
{
  "status": "ok",
  "service": "tutti-backend",
  "database": "connected",
  "database_enabled": true
}
```

### 6. Probar con datos

```bash
# Subir archivo Excel y guardar en DB
curl -X POST "http://localhost:8000/upload?save_to_db=true" \
  -F "files=@ruta/al/archivo.xlsx"

# Listar rutas guardadas
curl http://localhost:8000/routes

# Verificar en PostgreSQL directamente
docker exec -it tutti-postgres psql -U tutti -c "SELECT COUNT(*) FROM routes;"
```

## Comandos Útiles

### PostgreSQL

```bash
# Conectar a la base de datos
docker exec -it tutti-postgres psql -U tutti -d tutti

# Ver tablas
\dt

# Ver rutas
SELECT * FROM routes LIMIT 10;

# Ver stops de una ruta
SELECT * FROM stops WHERE route_id = 'ID_RUTA';

# Salir
\q
```

### Migraciones (Alembic)

```bash
cd backend/db/migrations

# Ver estado actual
alembic current

# Crear nueva migración automáticamente
alembic revision --autogenerate -m "descripcion del cambio"

# Aplicar migraciones
alembic upgrade head

# Downgrade (revertir última migración)
alembic downgrade -1

# Ver historial
alembic history --verbose

# Reset completo
alembic downgrade base
```

### Docker

```bash
# Iniciar servicios
docker-compose up -d

# Ver logs
docker-compose logs -f postgres
docker-compose logs -f backend

# Detener servicios
docker-compose down

# Detener y eliminar datos (CUIDADO!)
docker-compose down -v

# Reconstruir imagen del backend
docker-compose build backend
```

## Modo Legacy (sin Base de Datos)

Para ejecutar sin PostgreSQL:

```bash
# Opción 1: Variable de entorno
set USE_DATABASE=false
uvicorn main:app --reload

# Opción 2: Modificar .env
# USE_DATABASE=false
uvicorn main:app --reload
```

En modo legacy:
- Los datos solo se mantienen en memoria
- No hay persistencia entre reinicios
- Los endpoints de DB retornan 503

## Estructura de la Base de Datos

### Tablas

```
routes
  - id (PK): string
  - name: string
  - type: string ('entry' | 'exit')
  - school_id: string
  - school_name: string
  - arrival_time: time (nullable)
  - departure_time: time (nullable)
  - capacity_needed: int
  - contract_id: string
  - days: array[string]
  - created_at: datetime

stops
  - id (PK): uuid
  - route_id (FK): string
  - name: string
  - lat: float
  - lon: float
  - order: int
  - time_from_start: int
  - passengers: int
  - is_school: boolean

optimization_jobs
  - id (PK): uuid
  - status: string ('pending' | 'running' | 'completed' | 'failed')
  - algorithm: string ('v2', 'v4', 'v5', 'v6')
  - input_data: json
  - result: json
  - stats: json
  - error_message: text
  - created_at: datetime
  - started_at: datetime
  - completed_at: datetime

optimization_results
  - id (PK): uuid
  - job_id (FK): uuid
  - route_id (FK): string
  - bus_id: string
  - start_time: time
  - end_time: time
  - time_shift_minutes: int
  - deadhead_minutes: int
```

### Relaciones

- `Route` 1:N `Stop` (una ruta tiene muchas paradas)
- `Route` 1:N `OptimizationResult` (una ruta puede tener múltiples resultados)
- `OptimizationJob` 1:N `OptimizationResult` (un job tiene múltiples resultados)

## API Endpoints de Base de Datos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del servicio incluyendo DB |
| GET | `/routes` | Listar rutas (con paginación) |
| GET | `/routes/{id}` | Obtener ruta específica |
| DELETE | `/routes/{id}` | Eliminar ruta |
| DELETE | `/routes` | Eliminar todas las rutas |
| POST | `/upload` | Subir Excel y parsear (opcional: guardar en DB) |
| POST | `/routes/from-excel` | Subir Excel y guardar en DB |
| GET | `/jobs` | Listar jobs de optimización |
| GET | `/jobs/{id}` | Obtener job específico |
| GET | `/jobs/{id}/results` | Obtener resultados de un job |
| DELETE | `/jobs/{id}` | Eliminar job |

## Solución de Problemas

### Error: "Database not available"

```bash
# Verificar que PostgreSQL está corriendo
docker-compose ps

# Ver logs
docker-compose logs postgres

# Verificar conexión desde Python
python -c "
from db.database import is_database_available
print('DB Available:', is_database_available())
"
```

### Error: "relation 'routes' does not exist"

```bash
# Las tablas no existen - ejecutar migraciones
cd backend/db/migrations
alembic upgrade head
```

### Error: "connection refused"

```bash
# Verificar que el puerto no está ocupado
netstat -ano | findstr 5432

# Reiniciar PostgreSQL
docker-compose restart postgres
```

### Reset completo de la base de datos

```bash
# Detener y eliminar volumen
docker-compose down -v

# Reiniciar
docker-compose up -d postgres

# Ejecutar migraciones
cd backend/db/migrations
alembic upgrade head
```

## Notas de Implementación

1. **Compatibilidad**: El código existente sigue funcionando sin cambios
2. **Feature Flag**: `USE_DATABASE` permite deshabilitar la DB fácilmente
3. **Dependencia Opcional**: `Depends(get_db)` retorna `None` si DB está deshabilitada
4. **Batch Operations**: Las operaciones en masa usan `create_routes_batch` para eficiencia
5. **Relaciones**: Las relaciones SQLAlchemy están configuradas con `cascade="all, delete-orphan"` para mantener consistencia
