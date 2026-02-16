# API de Validacion de Rutas con OSRM

Endpoints para validacion de compatibilidad de rutas usando OSRM (Open Source Routing Machine).

## Endpoints

### 1. POST /api/v1/validate-route-compatibility

Valida si dos rutas consecutivas son compatibles calculando el tiempo real de viaje.

**Request:**
```json
{
  "route_a_end": {"lat": -33.4489, "lon": -70.6693},
  "route_b_start": {"lat": -33.4567, "lon": -70.6500},
  "time_available_minutes": 30.0
}
```

**Response:**
```json
{
  "compatible": true,
  "travel_time_minutes": 12.5,
  "buffer_minutes": 17.5,
  "time_available_minutes": 30.0,
  "margin_adequate": true,
  "recommendation": "good",
  "recommendation_text": "Buen margen (17.5 min)",
  "distance_km": 6.25,
  "used_cache": false,
  "used_fallback": false
}
```

### 2. POST /api/v1/batch-validate-routes

Valida una secuencia completa de rutas para un bus.

**Request:**
```json
{
  "routes_sequence": [
    {
      "route_id": "R001",
      "start_coordinates": {"lat": -33.4489, "lon": -70.6693},
      "end_coordinates": {"lat": -33.4567, "lon": -70.6500},
      "start_time": "07:30:00",
      "end_time": "08:15:00",
      "route_type": "entry",
      "school_name": "Colegio A"
    },
    {
      "route_id": "R002",
      "start_coordinates": {"lat": -33.4567, "lon": -70.6500},
      "end_coordinates": {"lat": -33.4700, "lon": -70.6400},
      "start_time": "08:45:00",
      "end_time": "09:30:00",
      "route_type": "entry",
      "school_name": "Colegio B"
    }
  ],
  "bus_id": "BUS001"
}
```

**Response:**
```json
{
  "all_compatible": true,
  "validations": [...],
  "total_routes": 2,
  "total_transitions": 1,
  "total_travel_time_minutes": 15.0,
  "min_buffer_minutes": 15.0,
  "avg_buffer_minutes": 15.0,
  "critical_transitions": [],
  "overall_recommendation": "good",
  "execution_time_ms": 45.2,
  "cache_hits": 0
}
```

### 3. GET /api/v1/osrm-health

Verifica el estado de salud del servicio OSRM.

**Response:**
```json
{
  "status": "healthy",
  "response_time_ms": 123.4,
  "cache_size": 150,
  "base_url": "http://187.77.33.218:5000",
  "error_message": null
}
```

### 4. GET /api/v1/osrm-stats

Obtiene estadisticas de uso de OSRM.

**Response:**
```json
{
  "stats": {
    "requests": 100,
    "cache_hits": 45,
    "fallbacks": 2,
    "errors": 0
  },
  "cache_size": 150,
  "config": {...}
}
```

### 5. POST /api/v1/osrm-clear-cache

Limpia el cache de OSRM.

**Response:**
```json
{
  "message": "Cache cleared",
  "previous_size": 150
}
```

## Caracteristicas

- **Cache inteligente**: Las respuestas de OSRM se cachean para evitar llamadas repetidas
- **Fallback robusto**: Si OSRM no responde, usa calculo por distancia euclidiana a 30km/h
- **Rate limiting**: Control de tasa configurable para evitar sobrecargar el servidor OSRM
- **Manejo de errores**: Reintentos automaticos con backoff exponencial

## Configuracion

Las variables de entorno disponibles:

| Variable | Default | Descripcion |
|----------|---------|-------------|
| OSRM_BASE_URL | http://187.77.33.218:5000 | URL base del servidor OSRM |
| OSRM_CACHE_ENABLED | true | Habilitar cache |
| OSRM_CACHE_TTL | 86400 | TTL del cache en segundos |
| OSRM_TIMEOUT | 5.0 | Timeout de requests en segundos |
| OSRM_MAX_RETRIES | 3 | Numero maximo de reintentos |
| OSRM_FALLBACK_ENABLED | true | Habilitar fallback |
| OSRM_FALLBACK_SPEED | 30.0 | Velocidad de fallback en km/h |
| OSRM_MIN_MARGIN | 5.0 | Margen minimo en minutos |

## Niveles de Recomendacion

- **excellent**: Buffer > 20 minutos
- **good**: Buffer entre 10 y 20 minutos
- **acceptable**: Buffer entre 5 y 10 minutos
- **tight**: Buffer entre 0 y 5 minutos
- **incompatible**: Buffer negativo (tiempo de viaje excede disponible)
