---
name: tutti-debug-troubleshoot
description: Debugging y troubleshooting para Tutti Fleet Optimizer. Usar cuando haya errores, comportamientos inesperados, performance issues, o problemas de integracion entre componentes. Incluye guias de diagnostico, logs, common issues y soluciones.
---

# Tutti Debug & Troubleshoot Skill

## Niveles de Logging

### Backend

```python
import logging

logger = logging.getLogger(__name__)

# Niveles recomendados:
logger.debug("Detalle interno, para desarrollo")
logger.info("Eventos importantes (startup, requests)")
logger.warning("Advertencias recuperables")
logger.error("Errores que requieren atencion")
```

### Habilitar Debug

```bash
# Windows (PowerShell)
$env:LOG_LEVEL = "DEBUG"
$env:PYTHONUNBUFFERED = "1"

# O en codigo
logging.basicConfig(level=logging.DEBUG)
```

## Diagnosticos Comunes

### Backend No Responde

```batch
:: 1. Verificar puerto
netstat -ano | findstr :8000

:: 2. Matar proceso si existe
for /f "tokens=5" %a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %a

:: 3. Verificar imports
.\.venv\Scripts\python -c "import main"

:: 4. Iniciar manualmente
cd backend
.\.venv\Scripts\python -m uvicorn main:app --reload
```

### Frontend No Carga

```batch
:: 1. Verificar build existe
dir frontend\dist\index.html

:: 2. Rebuild si es necesario
cd frontend
npm install
npm run build

:: 3. Verificar Vite dev
npm run dev
```

### OSRM Timeout

```python
# Sintomas: Optimizacion lenta, fallbacks a Haversine

# Diagnostico:
from router_service import get_router_metrics
print(get_router_metrics())

# Output esperado:
{
    "cache_hits": 150,
    "http_requests": 50,
    "api_errors": 0,
    "circuit_open_count": 0
}

# Si circuit_open_count > 0:
# - OSRM esta caido o lento
# - Verificar conectividad: ping 187.77.33.218
# - Verificar timeout: OSRM_TIMEOUT env var
```

### Errores de Base de Datos

```python
# Sintoma: "Database locked" (SQLite)

# Causas:
# 1. Multiple procesos usando misma DB
# 2. Conexion no cerrada
# 3. Transaction no commiteada

# Solucion:
# 1. Cerrar otras instancias
# 2. Usar SessionLocal como context manager:

from db.database import SessionLocal

def query_data():
    db = SessionLocal()
    try:
        return db.query(Model).all()
    finally:
        db.close()  # Siempre cerrar!
```

## Common Issues

### Issue: Optimizador Retorna Buses Vacios

**Causas posibles:**
1. No hay rutas parseadas
2. Todas las rutas tienen coordenadas invalidas
3. OSRM no responde y fallback falla

**Diagnostico:**
```python
# Verificar rutas de entrada
print(f"Routes count: {len(routes)}")
print(f"Routes with stops: {sum(1 for r in routes if r.stops)}")
print(f"Valid coords: {sum(1 for r in routes if all(s.lat != 0 for s in r.stops))}")

# Verificar optimizer diagnostics
from optimizer_v6 import get_last_optimization_diagnostics
print(get_last_optimization_diagnostics())
```

### Issue: Rutas Solapadas en Mismo Bus

**Causas:**
1. Validacion OSRM deshabilitada
2. Bug en `_check_overlap_items()`

**Fix:**
```python
# Verificar que schedule builder incluya validacion
def build_full_schedule(buses, blocks):
    for bus in buses:
        # ...
        if not _check_overlap_items(bus.items):
            logger.error(f"Overlap detected in {bus.bus_id}")
            # Manejar conflicto
```

### Issue: PDF Export Falla

**Diagnostico:**
```python
# 1. Verificar dependencias
.\.venv\Scripts\python -c "import reportlab; print('OK')"

# 2. Verificar datos
print(f"Schedule: {len(schedule)} buses")
print(f"Items: {sum(len(b.items) for b in schedule)}")

# 3. Verificar nulos
for bus in schedule:
    for item in bus.items:
        if item.start_time is None:
            print(f"Null start_time in {item.route_id}")
```

### Issue: WebSocket No Conecta

**Verificar:**
```javascript
// En consola del navegador
const ws = new WebSocket('ws://localhost:8000/ws/optimization/test');
ws.onopen = () => console.log('Connected');
ws.onerror = (e) => console.error('Error', e);
```

**Causas:**
1. Backend no tiene websocket habilitado
2. CORS issues
3. Firewall bloqueando

### Issue: Desktop Auto-Update No Funciona

**Logs:**
```
%LOCALAPPDATA%\Tutti\logs\desktop-updater.log
```

**Verificar:**
```python
# 1. Version actual
import desktop_version
print(desktop_version.APP_VERSION)

# 2. Release en GitHub
# Verificar que existe release con tag mayor

# 3. Asset disponible
# Verificar que TuttiDesktopApp.zip existe en release

# 4. Permisos de escritura
# Verificar que APPDATA\Local\Tutti es writable
```

## Performance Profiling

### Backend

```python
import cProfile
import pstats

# Perfilear optimizacion
profiler = cProfile.Profile()
profiler.enable()

result = optimize_v6(routes)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(20)  # Top 20 funciones
```

### Frontend

```javascript
// React DevTools Profiler
// 1. Instalar extension React DevTools
// 2. Abrir Profiler tab
// 3. Record while performing action
// 4. Analizar renders

// Console timing
console.time('operation');
performOperation();
console.timeEnd('operation');
```

## Health Checks

### Endpoint Health

```bash
curl http://localhost:8000/health
```

Respuesta esperada:
```json
{
  "status": "ok",
  "services": {
    "database": "ok",
    "celery": "disabled"
  },
  "ws_manager": {
    "active_jobs": 0,
    "active_connections": 1
  }
}
```

### OSRM Health

```bash
curl "http://187.77.33.218:5000/route/v1/driving/-8.5,42.8;-8.4,42.9?overview=false"
```

## Debug Mode

### Activar Modo Debug

```bash
# Windows batch
set LOG_LEVEL=DEBUG
set APP_RUNTIME_MODE=debug
set WEBSOCKET_ENABLED=true
set PYTHONUNBUFFERED=1
```

### Desktop Debug Window

```python
# En desktop_launcher.py, comentar windowed mode
# para ver consola:

# exe = EXE(
#     ...
#     console=True,  # Cambiar a True
#     ...
# )
```

## Recuperacion de Errores

### Resetear Estado

```batch
:: Limpiar todo
rmdir /S /Q .venv
rmdir /S /Q frontend\node_modules
rmdir /S /Q frontend\dist
del %LOCALAPPDATA%\Tutti\data\*.db
```

### Rebuild Completo

```batch
:: 1. Limpiar
:: 2. Recrear venv
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt

:: 3. Rebuild frontend
cd frontend
npm install
npm run build

:: 4. Rebuild desktop
scripts\desktop\build-desktop-app-exe.bat
```

## Referencias

- `references/error-codes.md`: Catalogo de errores
- `references/performance-tuning.md`: Optimizacion de performance
