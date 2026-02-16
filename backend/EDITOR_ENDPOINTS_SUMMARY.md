# Resumen: Endpoints de Edición de Rutas

## Archivos Creados/Modificados

### 1. `backend/api/routes_editor.py` (NUEVO)
Módulo principal con los endpoints de edición:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/routes/{route_id}` | PATCH | Actualiza datos de una ruta |
| `/api/routes/{route_id}/toggle-lock` | POST | Bloquea/desbloquea ruta |
| `/api/schedules/update` | POST | Guarda schedule completo |
| `/api/schedules/{day}` | GET | Obtiene schedule guardado |
| `/api/schedules/validate` | POST | Valida sin guardar |
| `/api/routes/validation-config` | GET | Config de validación |

### 2. `backend/db/schemas.py` (ACTUALIZADO)
Nuevos schemas para validación de requests/responses:
- `RouteUpdateRequest` / `RouteUpdateResponse`
- `ToggleLockRequest` / `ToggleLockResponse`
- `ScheduleUpdateRequest` / `ScheduleUpdateResponse`
- `ScheduleItemEditorSchema`, `BusEditorSchema`
- `ValidationResult`, `RouteConflict`, `ValidationError`

### 3. `backend/main.py` (ACTUALIZADO)
- Registro del router `routes_editor`
- CORS configurado para `localhost:5173`

### 4. `backend/api/__init__.py` (ACTUALIZADO)
Documentación del módulo

### 5. `backend/API_EDITOR_USAGE.md` (NUEVO)
Guía completa de uso con ejemplos

---

## Validaciones Implementadas

### 1. Solapamientos de Tiempo
```python
def check_time_overlap(start1, end1, start2, end2, buffer=0):
    # Detecta si dos rangos de tiempo se solapan
    return not (end1 + buffer <= start2 or end2 <= start1 - buffer)
```

### 2. Coordenadas Válidas
```python
def validate_coordinates(lat, lon):
    # Latitud: -90 a 90
    # Longitud: -180 a 180
    return (-90 <= lat <= 90) and (-180 <= lon <= 180)
```

### 3. Time Shift Limits
```python
MAX_TIME_SHIFT_MINUTES = 30  # ±30 minutos máximo
```

### 4. Duplicate Assignments
Detecta si una ruta está asignada a múltiples buses.

---

## Estructura de Datos

### Schedule Update Request
```json
{
  "day": "L",
  "buses": [
    {
      "bus_id": "B001",
      "capacity": 55,
      "items": [
        {
          "route_id": "R001",
          "start_time": "08:00",
          "end_time": "08:45",
          "type": "entry",
          "is_locked": false,
          "stops": [...]
        }
      ]
    }
  ],
  "unassigned_routes": [...]
}
```

---

## Caché en Memoria

Los schedules se guardan temporalmente en:
```python
edited_schedules_cache: Dict[str, Dict[str, Any]] = {}
# Key: "schedule_{day}"
# Value: schedule completo con timestamp
```

---

## Configuración CORS

```python
allow_origins=[
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",  # React dev server
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "*"
]
```

---

## Códigos de Conflicto

| Código | Descripción |
|--------|-------------|
| `time_overlap` | Dos rutas se solapan en el tiempo |
| `time_shift_exceeded` | time_shift > ±30 minutos |
| `invalid_coordinates` | Coordenadas fuera de rango |
| `duplicate_assignment` | Ruta en múltiples buses |
| `invalid_time_format` | Formato debe ser HH:MM |
| `high_route_count` | Bus con >7 rutas (warning) |

---

## Ejemplo de Uso Completo

```javascript
// 1. Actualizar una ruta
await fetch('/api/routes/R001', {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    start_time: '08:30',
    end_time: '09:15',
    is_locked: true
  })
});

// 2. Bloquear la ruta
await fetch('/api/routes/R001/toggle-lock', {
  method: 'POST',
  body: JSON.stringify({ is_locked: true })
});

// 3. Validar schedule antes de guardar
const validation = await fetch('/api/schedules/validate', {
  method: 'POST',
  body: JSON.stringify(scheduleData)
});

// 4. Guardar schedule
const result = await fetch('/api/schedules/update', {
  method: 'POST',
  body: JSON.stringify({
    day: 'L',
    buses: [...],
    unassigned_routes: []
  })
});
```

---

## Logs para Debugging

Todos los endpoints generan logs estructurados:
```
[Route Update] Updating route R001
[Route Update] Route R001 updated successfully. Changes: [...]
[Route Lock] Route R001 locked
[Schedule Update] Processing schedule for day L
[Schedule Update] Schedule for Lunes saved: 5 buses, 23 routes
```

---

## Próximos Pasos Recomendados

1. **Integración con DB:** Actualmente los schedules se guardan en memoria. Para persistencia, conectar con SQLAlchemy models.

2. **Autenticación:** Agregar middleware de auth para proteger endpoints.

3. **WebSocket:** Considerar WebSocket para notificaciones de cambios en tiempo real.

4. **Tests:** Agregar tests unitarios con pytest:
   ```bash
   pytest backend/tests/test_routes_editor.py
   ```
