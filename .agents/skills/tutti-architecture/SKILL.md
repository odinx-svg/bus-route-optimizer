---
name: tutti-architecture
description: Arquitectura completa del proyecto Tutti Fleet Optimizer. Usar cuando se necesite entender, modificar o extender la estructura del sistema, sus componentes, flujos de datos o decisiones de diseño. Incluye conocimiento del backend FastAPI, frontend React, modelo de datos, pipeline de optimizacion y arquitectura desktop.
---

# Tutti Architecture Skill

## Vision General

Tutti Fleet Optimizer es un sistema de optimizacion de rutas escolares con distribucion multiplataforma:

- **Desktop App**: Windows EXE con backend embebido (PyInstaller + WebView)
- **Landing Page**: Vercel para marketing y descargas
- **Modo Desarrollo**: Backend + Frontend por separado

## Estructura de Directorios

```
bus-route-optimizer/
├── backend/                   # Python FastAPI
│   ├── main.py               # Entry point
│   ├── models.py             # Pydantic models (Route, Stop, BusSchedule)
│   ├── parser.py             # Parser Excel gallego
│   ├── optimizer_v6.py       # Optimizador ILP principal
│   ├── router_service.py     # Integracion OSRM
│   ├── api/                  # Routers adicionales
│   ├── db/                   # SQLAlchemy models y CRUD
│   ├── services/             # Logica de negocio
│   └── websocket/            # WebSockets
├── frontend/                  # React + Vite
│   ├── src/
│   │   ├── App.jsx           # Componente raiz
│   │   ├── components/       # Componentes React
│   │   ├── stores/           # Zustand stores
│   │   └── services/         # Clientes API
│   └── package.json
├── landing/                   # Landing page (Vercel)
├── scripts/desktop/           # Desktop launcher y build
└── .agents/skills/           # Skills del proyecto
```

## Stack Tecnologico

| Capa | Tecnologia |
|------|------------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Frontend | React 18, Vite, Tailwind CSS |
| Estado | Zustand |
| DB | PostgreSQL (prod) / SQLite (desktop) |
| Optimizacion | PuLP (ILP), CBC solver |
| Mapas | Leaflet, OSRM |
| PDF | ReportLab |
| Desktop | PyInstaller, pywebview |

## Flujo de Datos Principal

```
Excel (.xlsx)
    |
    v
parser.py → Route[]
    |
    v
optimizer_v6.py → BusSchedule[]
    |
    v
router_service.py (OSRM validation)
    |
    v
Workspace (DB) → PDF Export
```

## Modelos de Datos Core

Ver `references/data-models.md` para detalles completos.

### Route
- id, name, type (entry|exit), stops[]
- arrival_time / departure_time
- capacity_needed, vehicle_capacity_min/max
- school_id, school_name, contract_id
- days[] (L, M, Mc, X, V)

### BusSchedule
- bus_id, items[] (ScheduleItem)
- assigned_vehicle_id/plate
- uses_fleet_profile

## Pipeline de Optimizacion

1. **Ingest**: Parser de Excel
2. **Baseline**: Optimizer V6 (ILP)
3. **OSRM Validate**: Verificacion tiempos reales
4. **Reoptimize**: Iteraciones de mejora
5. **Select Best**: Scoring y seleccion
6. **Publish**: Guardar workspace

## Arquitectura Desktop

```
desktop_launcher.py
├── DesktopRuntime
│   └── start_backend() → uvicorn @ :8000
├── WebView Window
│   └── http://127.0.0.1:8000
└── AutoUpdater
    └── GitHub Releases API
```

Variables clave desktop:
- `SERVE_FRONTEND_DIST=true`
- `DATABASE_URL=sqlite:///.tutti_desktop.db`
- `CELERY_ENABLED=false`

## Sistema de Workspaces

Versionado inmutable con estados:
- **draft**: En edicion
- **active**: Publicado y en operacion
- **inactive**: Archivado

Entidades:
- `OptimizationWorkspace`: Root entity
- `OptimizationWorkspaceVersion`: Snapshots inmutables
- `AppMeta`: Flags de migracion

## OSRM Integration

- Base URL: `http://187.77.33.218:5000`
- Cache persistente: `osrm_cache.json`
- Circuit breaker para fallos
- Fallback a Haversine

## Convenciones Importantes

1. **Nunca** modificar archivos fuera del working directory
2. **Siempre** actualizar AGENTS.md al hacer cambios significativos
3. **Siempre** mantener compatibilidad con modo desktop
4. Usar type hints en Python
5. Usar destructuring con defaults en React
