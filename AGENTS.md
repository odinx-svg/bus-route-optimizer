# Tutti Fleet Optimizer - Agent Documentation

> **Guía para agentes de código:** Este documento describe la arquitectura, convenciones y procedimientos para mantener el proyecto Tutti.

---

## 📋 Índice

1. [Inicio Rápido](#inicio-rápido)
2. [Skills del Proyecto](#skills-del-proyecto)
3. [Arquitectura del Proyecto](#arquitectura-del-proyecto)
4. [Cuándo Actualizar `start-tutti.bat`](#cuándo-actualizar-start-tuttibat)
5. [Checklist de Cambios Importantes](#checklist-de-cambios-importantes)
6. [Estructura del Proyecto](#estructura-del-proyecto)
7. [Convenciones de Código](#convenciones-de-código)
8. [Solución de Problemas Comunes](#solución-de-problemas-comunes)

---

## 🚀 Inicio Rápido

```bash
# Windows - Doble clic o desde terminal
start-tutti.bat

# URLs de acceso
Backend:   http://localhost:8000
Frontend:  http://localhost:5173
API Docs:  http://localhost:8000/docs
```

---

## 🎓 Skills del Proyecto

El proyecto incluye skills especializadas en `.agents/skills/` para facilitar el desarrollo:

| Skill | Descripción | Cuándo Usar |
|-------|-------------|-------------|
| `tutti-architecture` | Arquitectura completa del sistema | Entender estructura, flujos de datos |
| `tutti-domain-model` | Dominio operativo e invariantes | Cambios en entidades, payloads y semántica |
| `tutti-excel-ingestion` | Parser Excel y datos sucios | Importación de archivos, columnas y normalización |
| `tutti-optimizer-dev` | Optimizador V6 y constraints | Solver, chaining, feasibility, load balance |
| `tutti-backend-dev` | Desarrollo backend FastAPI/Python | Crear endpoints, optimizadores, modelos |
| `tutti-workspace-workflow` | Save/publish/archive y readiness | Versionado, publish, estados operativos |
| `tutti-fleet-operations` | Flota real/virtual y reconciliación | Conflictos, snapshots, publicación de flota |
| `tutti-frontend-dev` | Desarrollo frontend React | Componentes UI, stores, hooks |
| `tutti-frontend-design` | Diseño UI/UX y estilos | Paleta de colores, animaciones, responsive |
| `tutti-pdf-exports` | Exportación PDF operativa | ReportLab, tablas por bus, links Google Maps |
| `tutti-routing-maps` | OSRM, geometrías y mapas | Tiempos, caché, Leaflet, visualización geoespacial |
| `image-ui-analyzer` | Análisis de imágenes UI | Extraer diseño de screenshots para replicar |
| `tutti-build-deploy` | Build y deployment | Generar EXE, releases, landing |
| `tutti-debug-troubleshoot` | Debugging y troubleshooting | Diagnosticar errores, logs |
| `tutti-testing` | Testing y calidad | Escribir tests, cobertura |
| `tutti-skill-governance` | Gobernanza de skills | Crear, dividir y mantener la librería de skills |
| `tutti-drivers-messaging` | Conductores y mensajería futura | Modelado futuro de drivers y envíos automáticos |

Estas skills se activan automáticamente según el contexto y proporcionan conocimiento especializado para cada área del proyecto.

---

## 🏗️ Arquitectura del Proyecto

### Tech Stack

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Backend | Python + FastAPI | 3.11+ |
| Frontend | React + Vite | 18+ |
| Base de datos | PostgreSQL / SQLite | 15+ / 3.x |
| Optimización | PuLP (ILP) | 2.8+ |
| PDF | ReportLab | 4.0+ |
| Mapas | Leaflet + OSRM | - |

### Flujo de Datos

```
Excel (.xlsx)
  -> Parser (parser.py)
  -> Routes (models)
  -> Optimizer V6 / Pipeline
  -> Schedule con asignacion de flota PREVIEW (real + virtual)
  -> Workspace save (no reserva operativa)
  -> Workspace publish
      -> Fleet commit (services/fleet_publication.py)
      -> Validacion de conflictos contra published_fleet_assignments
      -> Si hay conflicto real: bloquea con HTTP 409
      -> Si falta flota real: crea virtuales por version publicada
  -> Consumo en PDF / Map / Timeline / Control Hub
```

---

## 🔄 Cuándo Actualizar `start-tutti.bat`

**DEBES actualizar `start-tutti.bat` cuando:**

### 1. Nuevas Dependencias Críticas

Si agregas una dependencia que es **esencial para el funcionamiento**:

```python
# Ejemplo: Se agregó pillow para soporte de imágenes en PDF
"%VENV_PIP%" install -q reportlab pillow >nul 2>&1
```

**Checklist:**
- [ ] Agregar instalación de la dependencia en Step 3
- [ ] Agregar verificación de importación (como se hace con reportlab, httpx, pulp)

### 2. Nuevos Puertos o Servicios

Si el proyecto usa nuevos puertos:

```batch
:: Ejemplo: Si se agrega un servicio de WebSocket en puerto 8001
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8001.*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
```

### 3. Cambios en Estructura de Archivos

Si se mueven archivos críticos del backend:

```batch
:: Ejemplo: Verificar nuevos archivos en Step 5
if not exist "%BACKEND%\nuevo_modulo.py" (
    echo        WARNING: nuevo_modulo.py not found
)
```

### 4. Cambios en Variables de Entorno

Si se requieren nuevas variables de entorno:

```batch
:: En el futuro, si se necesitan variables de entorno
set "VITE_OSRM_URL=http://localhost:5000"
```

### 5. Cambios en Comandos de Inicio

Si cambia la forma de iniciar el backend o frontend:

```batch
:: Ejemplo: Si se agrega un parámetro nuevo a uvicorn
start "Tutti-Backend" cmd /k "... --workers 2"
```

### 6. Cambios de Migraciones o Backfills DB

Si agregas migraciones de Alembic o cambias la inicialización de base de datos:

```batch
:: Verificar llamada a init_db.py y flags
"%VENV_PYTHON%" "%BACKEND%\scripts\init_db.py" --skip-verify
```

---

## ✅ Checklist de Cambios Importantes

### Antes de hacer cambios significativos:

```markdown
## Backend
- [ ] ¿Modifiqué models.py? → Verificar schemas
- [ ] ¿Agregué endpoints? → Agregar tests
- [ ] ¿Cambié el optimizador? → Verificar anti-overlap sigue funcionando
- [ ] ¿Toqué publish/restore/archive? → Verificar reservas en published_fleet_assignments
- [ ] ¿Toqué Fleet API? → Verificar fallback JSON y compatibilidad company_id
- [ ] ¿Agregué dependencias? → Actualizar requirements.txt Y start-tutti.bat

## Frontend
- [ ] ¿Agregué componentes nuevos? → Verificar imports
- [ ] ¿Modifiqué stores? → Verificar persistencia
- [ ] ¿Cambié el mapa? → Verificar OSRM integration
- [ ] ¿Agregué librerías? → Documentar en package.json

## General
- [ ] ¿Cambié la estructura de carpetas? → Actualizar imports
- [ ] ¿Agregué archivos de configuración? → Documentar
- [ ] ¿Cambié puertos? → Actualizar CORS y start-tutti.bat
```

---

## 📁 Estructura del Proyecto

```
bus-route-optimizer/
│
├── 📄 AGENTS.md                 # Este archivo
├── 📄 start-tutti.bat           # Script de inicio (ACTUALIZAR cuando sea necesario)
├── 📄 start.bat                 # Script alternativo
├── 📄 docker-compose.yml        # Config Docker dev
├── 📄 docker-compose.prod.yml   # Config Docker prod
│
├── 🐍 backend/                  # Python FastAPI
│   ├── 📄 main.py              # Entry point, endpoints
│   ├── 📄 models.py            # Pydantic models (Route, Stop, Bus, etc)
│   ├── 📄 parser.py            # Excel parser
│   ├── 📄 optimizer_v6.py      # Optimizador principal (ILP)
│   ├── 📁 optimizer/           # Capa nueva de motor pluggable (config/engine/solvers)
│   ├── 📄 pdf_service.py       # Generación de PDFs
│   ├── 📄 router_service.py    # OSRM integration
│   ├── 📄 requirements.txt     # Dependencias Python
│   ├── 📁 scripts/
│   │   └── 📄 init_db.py       # Init DB + migraciones + backfill flota
│   │
│   ├── 📁 api/                 # Routers adicionales
│   │   ├── 📄 routes_editor.py # Editor de rutas
│   │   ├── 📄 fleet.py         # CRUD flota (DB-first + fallback JSON)
│   │   └── 📄 workspaces.py    # Save/publish + fleet commit operativo
│   │
│   ├── 📁 db/                  # Database
│   │   ├── 📄 models.py        # SQLAlchemy models
│   │   ├── 📄 schemas.py       # Pydantic schemas
│   │   ├── 📄 crud.py          # Operaciones CRUD
│   │   └── 📁 migrations/      # Alembic migrations (001/002/003+)
│   │
│   ├── 📁 services/            # Servicios auxiliares
│   │   ├── 📄 fleet_repository.py   # Repositorio DB-first de flota
│   │   ├── 📄 fleet_publication.py  # Commit de flota al publicar
│   │   ├── 📄 fleet_reconciliation.py # Reconciliacion operativa por dia (Empresa/UTE)
│   │   └── 📄 telematics_provider.py # Contrato GPS (contract-first)
│   ├── 📁 validation/          # Validación Monte Carlo
│   ├── 📁 websocket/           # WebSockets
│   └── 📁 tests/               # Tests
│
├── ⚛️ frontend/                 # React + Vite
│   ├── 📄 package.json         # Dependencias Node
│   ├── 📄 vite.config.js       # Config Vite
│   │
│   ├── 📁 src/
│   │   ├── 📁 components/      # Componentes React
│   │   │   ├── 📁 timeline-editable/
│   │   │   │   ├── 📄 RouteEditorDrawer.jsx
│   │   │   │   └── 📄 WorkspaceToolbar.jsx
│   │   │   ├── 📄 MapView.jsx
│   │   │   ├── 📄 RouteStopsLayer.jsx    # NUEVO: Marcadores de paradas
│   │   │   └── 📄 MapLegend.jsx
│   │   │
│   │   ├── 📁 stores/          # Zustand stores
│   │   │   └── 📄 timelineEditableStore.ts
│   │   │
│   │   ├── 📁 services/        # Servicios frontend
│   │   │   └── 📄 RouteService.js        # OSRM client
│   │   │
│   │   └── 📄 index.css        # Estilos globales
│   │
│   └── 📁 dist/                # Build production
│
└── 📁 .venv/                    # Virtual environment (no commitear)
```

---

## 📝 Convenciones de Código

### Python (Backend)

```python
# Imports ordenados
from typing import List, Optional, Dict, Any
from datetime import time, datetime

from pydantic import BaseModel  # 3rd party

from models import Route, Stop  # local


# Funciones: docstrings con tipo
async def optimize_routes(
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
    pass


# Clases: type hints explícitos
class Route(BaseModel):
    id: str
    stops: List[Stop]
    arrival_time: Optional[time] = None
```

### JavaScript/React (Frontend)

```javascript
// Imports ordenados
import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';  // 3rd party

import RouteStopsLayer from './RouteStopsLayer';  // local


// Props destructuring con defaults
const MapView = ({ 
  routes = [], 
  schedule = null,
  selectedBusId = null,
  onBusSelect = () => {}
}) => {
  // Estados con nombres descriptivos
  const [mapRoutes, setMapRoutes] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // useEffect con cleanup
  useEffect(() => {
    let isMounted = true;
    // ...
    return () => { isMounted = false; };
  }, [dependencies]);
};
```

---

## 🔧 Solución de Problemas Comunes

### Error 500 en PDF

**Causa:** Datos nulos o dependencias faltantes

**Solución:**
```bash
# Verificar reportlab
.\.venv\Scripts\python -c "import reportlab; print('OK')"

# Instalar si falta
.\.venv\Scripts\pip install reportlab pillow
```

### Rutas solapadas en el mismo bus

**Causa:** Optimizador permite solapamientos

**Solución:** Verificar que `build_full_schedule()` en `optimizer_v6.py` incluye `_check_overlap_items()`

### Mapa muestra líneas rectas

**Causa:** `RouteStopsLayer` no recibe `positions` de OSRM

**Solución:** Verificar que `MapView.jsx` pasa `positions` a `RouteStopsLayer`

### Backend no responde

**Causa:** Puerto 8000 ocupado o error de importación

**Solución:**
```bash
# Limpiar puertos
for /f "tokens=5" %a in ('netstat -aon ^| findstr ":8000"') do taskkill /F /PID %a

# Verificar imports
.\.venv\Scripts\python -c "import main"
```

---

## 📌 Notas de Versión

### v2.3 (2026-03-22)

**Cambios mayores:**
- ✅ Nueva capa `backend/optimizer/` para desacoplar configuracion, engine, solver adapters y warm starts
- ✅ `optimization_pipeline_service.py` ya usa `OptimizerEngine` como orquestador estable sobre `optimizer_v6`
- ✅ Primer `greedy_builder` deterministico para seed / fallback controlado
- ✅ Nuevos contratos de config para migracion futura a otros solvers (`preferred_solver`, `enable_greedy_warm_start`, `time_limit_seconds`)
- ✅ Adapter `CP-SAT` operativo en `backend/optimizer/solver_cpsat.py` usando `ortools`
- ✅ Benchmark de comparacion entre backends en `backend/benchmarks/compare_optimizer_backends.py`
- ✅ Tests de fase 1 para config, engine, greedy builder e integracion del pipeline

**Nuevas notas del motor:**
- `preferred_solver=auto` ya selecciona entre `pulp_v6` y `cp_sat` con heuristica compartida
- Los endpoints directos y el pipeline devuelven `selected_solver`, `solver_selection_reason` y `solver_selection`
- La UI ya distingue entre solver pedido y solver realmente usado por dia

**Compatibilidad:**
- No se rompe `optimizer_v6`; sigue siendo el backend productivo bajo la nueva interfaz
- Los payloads actuales del pipeline siguen siendo compatibles; los nuevos campos son aditivos
- `start-tutti.bat` y `backend/requirements.txt` ya contemplan `ortools`
- Esta fase prepara el camino para CP-SAT / estrategias hibridas sin migracion destructiva
- `preferred_solver` debe tratarse como `auto | pulp_v6 | cp_sat`

### v2.2 (2026-03-15)

**Cambios mayores:**
- ✅ UX operativa más clara en navegación (`Panel`, `Flota`, `Planificacion`)
- ✅ Estados derivados de workspace en API (`workflow_stage`, `readiness_state`, `next_recommended_action`)
- ✅ `ControlHubPage` pasa a ser panel operativo con filtros, siguiente paso y bloque "que falta hoy"
- ✅ `FleetPage` reorganizada con importación guiada, filtros rápidos, grupos por empresa colapsables y detalle por pestañas
- ✅ `Studio` gana resumen operativo, estado de publicación y acceso directo a reconciliación de flota

**Compatibilidad:**
- No se rompen endpoints existentes
- Nombres técnicos internos (`preview`, `committed`, `virtual`) se mantienen en backend por compatibilidad
- La capa UI muestra etiquetas más claras (`Simulacion`, `Publicado`, `Provisional`)

### v2.1 (2026-03-07)

**Cambios mayores:**
- ✅ Flota DB-first (`fleet_vehicles`, `fleet_vehicle_documents`) con fallback JSON
- ✅ Publicación operativa: commit de flota al publicar workspace
- ✅ Bloqueo por conflictos reales entre optimizaciones publicadas (`published_fleet_assignments`)
- ✅ Endpoint de preview de flota por workspace (`/api/workspaces/{id}/fleet-preview`)
- ✅ Base contract-first para GPS (`telematics_provider.py`)

### v2.2 (2026-03-16)

**Cambios mayores:**
- ✅ Reconciliacion operativa E2E por dia (`services/fleet_reconciliation.py`)
- ✅ La reconciliacion ya no depende solo de buses `virtual`, ahora distingue:
  - buses requeridos del dia
  - ya cubiertos con real
  - pendientes de asignacion real
  - flota disponible en el alcance Empresa/UTE
- ✅ Snapshot persistente `reconciliation_snapshot` dentro de `fleet_snapshot`
- ✅ `publish` valida drift de reconciliacion (`reconciliation_stale`) antes de comprometer reservas
- ✅ UI de reconciliacion centrada en reparto por empresa + detalle por matricula

**start-tutti.bat actualizado:**
- Ejecución de `backend/scripts/init_db.py` antes de iniciar backend/frontend
- Verificación de dependencias críticas adicionales (`alembic`)
- Verificación de módulos críticos de flota/publicación

### v2.0 (2026-02-11)

**Cambios mayores:**
- ✅ Añadida validación anti-solapamiento en optimizer_v6.py
- ✅ PDF mejorado con manejo de datos nulos
- ✅ Mapa usa geometría real OSRM (no líneas rectas)
- ✅ Nuevo componente RouteStopsLayer con marcadores de paradas

**start-tutti.bat actualizado:**
- Health check del backend antes de iniciar frontend
- Verificación de dependencias críticas (reportlab, pillow, httpx, pulp)
- Verificación de archivos críticos del backend

---

## 🎯 Próximos Pasos Sugeridos

1. **Testing automatizado:** Agregar tests unitarios para el anti-overlap
2. **Documentación API:** Expandir /docs con más ejemplos
3. **Docker:** Mejorar docker-compose para desarrollo
4. **CI/CD:** GitHub Actions para tests automáticos

---

## 📌 Nota Operativa: Conductores en Flota

### Estado actual

1. `Flota` ya incluye `Plan semanal` por vehículo con descarga CSV.
2. Ya existe capa de conductores por empresa.
3. Cada autobús puede guardar:
   - conductor habitual
   - conductor distinto por día (`L`, `M`, `Mc`, `X`, `V`)
4. El plan semanal del vehículo ya puede mostrar también el conductor asignado.
5. La mensajería automática todavía no está activada.

## 📌 Pendiente Funcional: Conductores y Envío Automático de Trabajo

> **Nota de producto para próximas iteraciones:** esta parte no está implementada todavía, pero debe tenerse en cuenta al seguir evolucionando `Flota`, `Plan semanal` y la publicación operativa.

### Objetivo

Cuando una unidad tenga su planificación semanal visible en `Flota`, el sistema deberá poder relacionar esa unidad con el conductor habitual o con los conductores asignados por día, para preparar en el futuro un flujo automático de envío del trabajo diario.

### Requisitos funcionales esperados

1. **Ficha de vehículo con conductor asociado**
   - Cada autobús deberá poder guardar:
     - conductor principal habitual
     - o conductores distintos según el día (`L`, `M`, `Mc`, `X`, `V`)

2. **Modelo operativo realista**
   - Debe contemplarse que un mismo autobús pueda:
     - tener un conductor fijo
     - o rotar entre distintos conductores según el día
   - Este segundo caso se considera normal y debe soportarse de forma nativa.

3. **Plan semanal enriquecido**
   - En el apartado `Flota -> detalle del vehículo -> Plan semanal` deberá poder verse:
     - qué servicio tiene ese autobús cada día
     - qué conductor lo tiene asignado ese día

4. **Preparación para mensajería automática**
   - El sistema deberá quedar preparado para integrar en el futuro:
     - WhatsApp
     - Telegram
     - u otro canal de mensajería
   - Objetivo futuro:
     - enviar automáticamente cada día, a una hora configurable, el trabajo al conductor que toque

5. **Workflow futuro esperado**
   - Publicación / reconciliación de flota
   - Resolución de qué vehículo hace qué trabajo
   - Resolución de qué conductor lleva ese vehículo ese día
   - Generación del resumen diario del servicio
   - Envío automático del mensaje al conductor correspondiente

### Implicaciones de diseño a tener en cuenta

1. **Nueva entidad o bloque de datos de conductores**
   - Será necesario modelar conductores como dato propio del sistema.

2. **Relación conductor-vehículo por día**
   - No basta con un único campo `driver_name`.
   - Hará falta soportar asignación por día o por calendario operativo.

3. **Datos mínimos del conductor**
   - Nombre
   - Teléfono
   - Canal preferido de contacto
   - Estado (activo/inactivo)

4. **Integración con planificación**
   - El `Plan semanal` del vehículo deberá poder consumir tanto:
     - la planificación publicada del bus
     - como la asignación del conductor para ese día

5. **No mezclar todavía con el núcleo de optimización**
   - En esta fase debe considerarse una capa operativa posterior.
   - Primero se decide flota/vehículo.
   - Después se resuelve conductor y comunicación.

### Sugerencia de implementación futura

Cuando se aborde esta funcionalidad, partir de esta secuencia:

1. Crear CRUD de conductores
2. Añadir asignación conductor habitual / conductor por día en `Flota`
3. Mostrar conductor en `Plan semanal`
4. Generar resumen diario del trabajo por conductor
5. Integrar con proveedor de mensajería
6. Añadir scheduler para envío automático a hora configurable

---

> **Recuerda:** Cada vez que hagas cambios que afecten el inicio del proyecto, actualiza `start-tutti.bat` y documenta en este archivo.

*Última actualización: 2026-03-22*
