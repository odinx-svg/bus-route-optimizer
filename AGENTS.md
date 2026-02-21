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
| `tutti-backend-dev` | Desarrollo backend FastAPI/Python | Crear endpoints, optimizadores, modelos |
| `tutti-frontend-dev` | Desarrollo frontend React | Componentes UI, stores, hooks |
| `tutti-frontend-design` | Diseño UI/UX y estilos | Paleta de colores, animaciones, responsive |
| `image-ui-analyzer` | Análisis de imágenes UI | Extraer diseño de screenshots para replicar |
| `tutti-build-deploy` | Build y deployment | Generar EXE, releases, landing |
| `tutti-debug-troubleshoot` | Debugging y troubleshooting | Diagnosticar errores, logs |
| `tutti-testing` | Testing y calidad | Escribir tests, cobertura |

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
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Excel      │────▶│   Parser     │────▶│   Routes    │
│  (.xlsx)    │     │  (parser.py) │     │  (models)   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                         ┌──────────────────────┘
                         ▼
              ┌────────────────────┐
              │  Optimizer V6      │
              │  (optimizer_v6.py) │
              │  • ILP-based       │
              │  • Anti-overlap    │
              │  • OSRM routing    │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │   Schedule         │
              │   (BusSchedule)    │
              └─────────┬──────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   ┌─────────┐    ┌──────────┐   ┌──────────┐
   │   PDF   │    │   Map    │   │  Timeline│
   │ Export  │    │   View   │   │  Editor  │
   └─────────┘    └──────────┘   └──────────┘
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

---

## ✅ Checklist de Cambios Importantes

### Antes de hacer cambios significativos:

```markdown
## Backend
- [ ] ¿Modifiqué models.py? → Verificar schemas
- [ ] ¿Agregué endpoints? → Agregar tests
- [ ] ¿Cambié el optimizador? → Verificar anti-overlap sigue funcionando
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
│   ├── 📄 pdf_service.py       # Generación de PDFs
│   ├── 📄 router_service.py    # OSRM integration
│   ├── 📄 requirements.txt     # Dependencias Python
│   │
│   ├── 📁 api/                 # Routers adicionales
│   │   └── 📄 routes_editor.py # Editor de rutas
│   │
│   ├── 📁 db/                  # Database
│   │   ├── 📄 models.py        # SQLAlchemy models
│   │   ├── 📄 schemas.py       # Pydantic schemas
│   │   └── 📄 crud.py          # Operaciones CRUD
│   │
│   ├── 📁 services/            # Servicios auxiliares
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

> **Recuerda:** Cada vez que hagas cambios que afecten el inicio del proyecto, actualiza `start-tutti.bat` y documenta en este archivo.

*Última actualización: 2026-02-11*
