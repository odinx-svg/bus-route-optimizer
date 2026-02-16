# API de Edición de Rutas - Guía de Uso

Esta guía documenta los endpoints para editar rutas y horarios desde el frontend.

## Base URL

```
http://localhost:8000/api
```

## Endpoints

### 1. PATCH /routes/{route_id}

Actualiza datos de una ruta específica.

**URL:** `PATCH /api/routes/{route_id}`

**Request Body:**
```json
{
  "start_time": "08:30",
  "end_time": "09:15",
  "stops": [
    {
      "name": "Parada 1",
      "lat": 42.23,
      "lon": -8.72,
      "order": 1,
      "time_from_start": 0,
      "passengers": 5,
      "is_school": false
    },
    {
      "name": "Colegio ABC",
      "lat": 42.24,
      "lon": -8.73,
      "order": 2,
      "time_from_start": 15,
      "passengers": 0,
      "is_school": true
    }
  ],
  "is_locked": true,
  "bus_id": "B001",
  "time_shift_minutes": 5
}
```

**Campos opcionales:** Todos los campos son opcionales (partial update).

**Response (200 OK):**
```json
{
  "success": true,
  "route_id": "R001",
  "message": "Route R001 updated successfully",
  "changes": {
    "start_time": "08:30",
    "end_time": "09:15",
    "stops_count": 2,
    "is_locked": true,
    "bus_id": "B001",
    "time_shift_minutes": 5,
    "duration_minutes": 45
  },
  "warnings": []
}
```

**Errores comunes:**
- `400`: Coordenadas inválidas, formato de hora incorrecto, time_shift excede límite
- `404`: Ruta no encontrada

---

### 2. POST /routes/{route_id}/toggle-lock

Bloquea o desbloquea una ruta.

**URL:** `POST /api/routes/{route_id}/toggle-lock`

**Request Body (opcional):**
```json
{
  "is_locked": true,
  "reason": "Manual adjustment by operator"
}
```

- Si `is_locked` es `null` o no se envía: alterna el estado actual
- Si `is_locked` es `true`/`false`: establece ese estado específico

**Response (200 OK):**
```json
{
  "success": true,
  "route_id": "R001",
  "is_locked": true,
  "message": "Route R001 locked successfully",
  "previous_state": false,
  "reason": "Manual adjustment by operator"
}
```

---

### 3. POST /schedules/update

Guarda cambios del schedule completo para un día específico.

**URL:** `POST /api/schedules/update`

**Request Body:**
```json
{
  "day": "L",
  "buses": [
    {
      "bus_id": "B001",
      "capacity": 55,
      "plate": "ABC1234",
      "items": [
        {
          "route_id": "R001",
          "start_time": "08:00",
          "end_time": "08:45",
          "type": "entry",
          "time_shift_minutes": 0,
          "deadhead_minutes": 5,
          "school_name": "Colegio ABC",
          "contract_id": "C001",
          "is_locked": false,
          "stops": []
        },
        {
          "route_id": "R002",
          "start_time": "09:00",
          "end_time": "09:30",
          "type": "exit",
          "time_shift_minutes": 5,
          "deadhead_minutes": 10,
          "school_name": "Colegio ABC",
          "contract_id": "C001",
          "is_locked": true,
          "stops": []
        }
      ]
    }
  ],
  "unassigned_routes": [
    {
      "route_id": "R003",
      "reason": "No compatible bus available",
      "suggested_buses": ["B002", "B003"]
    }
  ],
  "metadata": {
    "optimizer_version": "v6",
    "created_by": "user@example.com"
  }
}
```

**Validaciones:**
- Verifica que no haya solapamientos de tiempo en el mismo bus
- Valida que las coordenadas de stops estén en rangos válidos
- Verifica que time_shift no exceda ±30 minutos
- Detecta rutas asignadas a múltiples buses

**Response (200 OK) - Success:**
```json
{
  "success": true,
  "day": "L",
  "saved_at": "2026-02-11T18:30:00.000000",
  "total_buses": 1,
  "total_routes": 2,
  "errors": [],
  "warnings": [],
  "conflicts": []
}
```

**Response (200 OK) - Validation Errors:**
```json
{
  "success": false,
  "day": "L",
  "saved_at": "2026-02-11T18:30:00.000000",
  "total_buses": 1,
  "total_routes": 2,
  "errors": [],
  "warnings": [],
  "conflicts": [
    {
      "route_id": "R001",
      "conflict_type": "time_overlap",
      "bus_id": "B001",
      "conflicting_with": "R002",
      "message": "Route R001 overlaps with R002 on bus B001",
      "details": {
        "route1": {
          "route_id": "R001",
          "start": "08:00",
          "end": "08:45"
        },
        "route2": {
          "route_id": "R002",
          "start": "08:30",
          "end": "09:15"
        }
      }
    }
  ]
}
```

---

### 4. POST /schedules/validate

Valida un schedule sin guardarlo (útil para validación en tiempo real).

**URL:** `POST /api/schedules/validate`

**Request Body:** Igual que `/schedules/update`

**Response:**
```json
{
  "is_valid": true,
  "conflicts": [],
  "errors": [],
  "warnings": []
}
```

---

### 5. GET /schedules/{day}

Obtiene un schedule guardado previamente.

**URL:** `GET /api/schedules/{day}`

**Response:**
```json
{
  "success": true,
  "day": "L",
  "day_name": "Lunes",
  "schedule": {
    "day": "L",
    "buses": [...],
    "unassigned_routes": [...],
    "updated_at": "2026-02-11T18:30:00"
  }
}
```

---

### 6. GET /routes/validation-config

Obtiene la configuración de validación actual.

**URL:** `GET /api/routes/validation-config`

**Response:**
```json
{
  "max_time_shift_minutes": 30,
  "min_buffer_minutes": 0,
  "coordinate_limits": {
    "min": -180.0,
    "max": 180.0
  },
  "valid_days": {
    "L": "Lunes",
    "M": "Martes",
    "Mc": "Miércoles",
    "X": "Jueves",
    "V": "Viernes"
  },
  "version": "1.0.0"
}
```

---

## Validaciones

### Solapamientos de Tiempo

El sistema verifica que las rutas en el mismo bus no se solapen. Dos rutas se consideran solapadas si:

```
end_time_route1 + buffer > start_time_route2
```

Donde `buffer` es 0 minutos por defecto.

### Coordenadas Válidas

- Latitud: entre -90 y 90
- Longitud: entre -180 y 180

### Límites de Time Shift

- Máximo: ±30 minutos
- Si se excede, se retorna error 400

---

## Códigos de Error

### Conflict Types
- `time_overlap`: Dos rutas se solapan en el tiempo
- `time_shift_exceeded`: El time_shift excede ±30 minutos
- `invalid_coordinates`: Coordenadas fuera de rango
- `duplicate_assignment`: Ruta asignada a múltiples buses
- `invalid_time_format`: Formato de hora inválido (debe ser HH:MM)

### Error Codes
- `invalid_day`: Código de día inválido (debe ser L, M, Mc, X, V)
- `invalid_coordinates`: Coordenadas inválidas en stops
- `high_route_count`: Bus con más de 7 rutas (advertencia)

---

## Ejemplo de Flujo de Uso

### 1. Actualizar una ruta individual

```javascript
// Frontend - React/Vue/Angular
const updateRoute = async (routeId, updates) => {
  const response = await fetch(`/api/routes/${routeId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates)
  });
  return response.json();
};

// Uso
await updateRoute('R001', {
  start_time: '08:30',
  end_time: '09:15',
  is_locked: true
});
```

### 2. Bloquear/desbloquear una ruta

```javascript
const toggleLock = async (routeId, isLocked) => {
  const response = await fetch(`/api/routes/${routeId}/toggle-lock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_locked: isLocked })
  });
  return response.json();
};

// Bloquear
await toggleLock('R001', true);

// Desbloquear
await toggleLock('R001', false);

// Alternar estado actual
await toggleLock('R001');
```

### 3. Guardar schedule completo

```javascript
const saveSchedule = async (day, buses, unassignedRoutes) => {
  const response = await fetch('/api/schedules/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      day,
      buses,
      unassigned_routes: unassignedRoutes
    })
  });
  
  const result = await response.json();
  
  if (!result.success) {
    // Mostrar conflictos al usuario
    console.error('Conflicts:', result.conflicts);
    console.error('Errors:', result.errors);
  }
  
  return result;
};
```

### 4. Validación en tiempo real

```javascript
// Validar antes de guardar
const validateSchedule = async (scheduleData) => {
  const response = await fetch('/api/schedules/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(scheduleData)
  });
  return response.json();
};

// Uso en el frontend (ej: cada 2 segundos mientras edita)
const result = await validateSchedule({
  day: 'L',
  buses: currentBuses,
  unassigned_routes: []
});

if (!result.is_valid) {
  // Mostrar advertencias visuales
  showValidationErrors(result.conflicts);
}
```

---

## CORS

El backend está configurado para permitir solicitudes desde:
- `http://localhost:5173` (Vite dev server)
- `http://localhost:3000` (React dev server)
- `http://127.0.0.1:5173`
- `http://127.0.0.1:3000`

---

## Logs

El backend registra logs detallados para debugging:

```
[Route Update] Updating route R001
[Route Update] Route R001 updated successfully. Changes: ['start_time', 'end_time', 'is_locked']
[Route Lock] Toggling lock for route R001
[Route Lock] Route R001 locked
[Schedule Update] Processing schedule for day L
[Schedule Update] Schedule for Lunes saved successfully: 5 buses, 23 routes
```
