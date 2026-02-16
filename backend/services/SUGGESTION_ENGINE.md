# Motor de Sugerencias Inteligentes (SuggestionEngine)

## Descripción

El Motor de Sugerencias es un algoritmo que evalúa TODAS las posiciones posibles para una ruta en todos los buses disponibles y devuelve las mejores opciones ordenadas por puntuación (0-100).

## Características

- ✅ Evalúa TODAS las posiciones posibles en todos los buses
- ✅ Usa OSRM real para calcular tiempos de viaje entre rutas
- ✅ Sistema de puntuación ponderado 0-100 con factores explicables
- ✅ Devuelve top N sugerencias ordenadas
- ✅ Cache de resultados OSRM para optimizar rendimiento
- ✅ Soporte para buses vacíos y con rutas existentes

## Algoritmo de Puntuación

El score (0-100) se calcula ponderando los siguientes factores:

| Factor | Peso | Descripción |
|--------|------|-------------|
| Buffer con ruta anterior | 35% | Tiempo disponible entre ruta anterior y nueva |
| Buffer con ruta siguiente | 35% | Tiempo disponible entre nueva ruta y siguiente |
| Proximidad geográfica | 20% | Distancia entre ubicaciones de rutas |
| Capacidad del bus | 10% | Si el bus tiene capacidad suficiente |

### Rangos de Puntuación por Factor

#### Buffer (prev_buffer / next_buffer)
- `< 0 min`: 0.0 (Incompatible)
- `0-5 min`: 0.3 (Justo)
- `5-10 min`: 0.6 (Aceptable)
- `10-20 min`: 0.85 (Bueno)
- `> 20 min`: 1.0 (Excelente)

#### Proximidad Geográfica
- `0-2 km`: 1.0 (Excelente)
- `2-5 km`: 0.8 (Bueno)
- `5-10 km`: 0.5 (Aceptable)
- `10-20 km`: 0.3 (Lejano)
- `> 20 km`: 0.1 (Muy lejano)

#### Capacidad
- `Capacidad suficiente (>20% margen)`: 1.0
- `Capacidad justa (0-20% margen)`: 0.7
- `Capacidad insuficiente`: 0.0

## Uso

### API Endpoint

```http
POST /api/suggestions
```

#### Request Body

```json
{
  "route": {
    "id": "R001",
    "name": "Ruta Ejemplo",
    "stops": [
      {"name": "Parada 1", "lat": -33.4489, "lon": -70.6693, "order": 1, "time_from_start": 0},
      {"name": "Parada 2", "lat": -33.4567, "lon": -70.6500, "order": 2, "time_from_start": 15}
    ],
    "school_id": "S1",
    "school_name": "Escuela Ejemplo",
    "arrival_time": "08:30:00",
    "capacity_needed": 25,
    "contract_id": "C1",
    "type": "entry"
  },
  "buses": [
    {"id": "BUS01", "capacity": 50},
    {"id": "BUS02", "capacity": 45}
  ],
  "bus_schedules": {
    "BUS01": [
      {
        "route_id": "R002",
        "start_time": "07:00:00",
        "end_time": "07:45:00",
        "stops": [...]
      }
    ],
    "BUS02": []
  },
  "max_suggestions": 5,
  "min_buffer_minutes": 5.0
}
```

#### Response

```json
{
  "route_id": "R001",
  "suggestions": [
    {
      "route_id": "R001",
      "bus_id": "BUS02",
      "position": 0,
      "score": 100.0,
      "factors": {
        "empty_bus": {
          "score": 1.0,
          "weight": 1.0,
          "description": "Bus vacío, sin restricciones"
        },
        "capacity": {
          "score": 1.0,
          "weight": 0.0,
          "available": 45,
          "needed": 25
        }
      },
      "estimated_start_time": "08:15:00",
      "estimated_end_time": "08:30:00",
      "travel_time_from_prev": 0,
      "travel_time_to_next": 0,
      "buffer_time": 999,
      "prev_route_id": null,
      "next_route_id": null,
      "geographic_distance_m": 0,
      "generated_at": "2024-01-01T12:00:00",
      "osrm_cache_hit": false
    },
    {
      "route_id": "R001",
      "bus_id": "BUS01",
      "position": 1,
      "score": 85.5,
      "factors": {
        "prev_buffer": {
          "score": 0.85,
          "weight": 0.35,
          "buffer_minutes": 15.2,
          "travel_time_min": 12.5,
          "time_gap_min": 30,
          "description": "Bueno (15.2 min)"
        },
        "next_buffer": {
          "score": 1.0,
          "weight": 0.35,
          "description": "Última ruta del bus, sin restricción siguiente"
        },
        "geographic_proximity": {
          "score": 0.8,
          "weight": 0.2,
          "distance_km": 3.5,
          "distance_m": 3500,
          "description": "Cercano (3.5 km)"
        },
        "capacity": {
          "score": 1.0,
          "weight": 0.1,
          "bus_capacity": 50,
          "route_capacity_needed": 25,
          "utilization_pct": 50.0,
          "description": "Capacidad suficiente"
        }
      },
      "estimated_start_time": "08:15:00",
      "estimated_end_time": "08:30:00",
      "travel_time_from_prev": 12.5,
      "travel_time_to_next": 0,
      "buffer_time": 15.2,
      "prev_route_id": "R002",
      "next_route_id": null,
      "geographic_distance_m": 3500,
      "generated_at": "2024-01-01T12:00:00",
      "osrm_cache_hit": true
    }
  ],
  "total_evaluated": 3,
  "generated_at": "2024-01-01T12:00:00",
  "osrm_stats": {
    "requests": 2,
    "cache_hits": 1,
    "fallbacks": 0,
    "errors": 0
  }
}
```

### Health Check

```http
GET /api/suggestions/health
```

#### Response

```json
{
  "status": "healthy",
  "osrm": {
    "status": "healthy",
    "response_time_ms": 45.2,
    "cache_size": 150,
    "cache_hits": 320,
    "requests": 450
  },
  "suggestion_engine": {
    "available": true,
    "weights": {
      "prev_buffer": 0.35,
      "next_buffer": 0.35,
      "geographic": 0.20,
      "capacity": 0.10
    }
  }
}
```

## Uso Programático

```python
from services.suggestion_engine import SuggestionEngine, get_suggestion_engine
from models import Route, Bus

# Crear motor de sugerencias
engine = get_suggestion_engine()

# Generar sugerencias
response = await engine.generate_suggestions(
    route=route,
    buses=buses,
    bus_schedules=schedules,
    max_suggestions=5,
    min_buffer_minutes=5.0
)

# Acceder a resultados
for suggestion in response.suggestions:
    print(f"Bus: {suggestion.bus_id}, Score: {suggestion.score}")
    print(f"  Buffer: {suggestion.buffer_time} min")
    print(f"  Factores: {suggestion.factors}")
```

## Cache OSRM

El motor utiliza el cache integrado de OSRMService para optimizar consultas repetidas:

- **TTL**: Configurable (default 24 horas)
- **Max size**: Configurable (default 10000 entradas)
- **Persistencia**: El cache se guarda en disco al cerrar la aplicación

## Consideraciones

1. **Buses vacíos**: Siempre reciben score 100 (perfecto) ya que no tienen restricciones
2. **Buffers negativos**: Se penalizan fuertemente (-50% del score total)
3. **Coordenadas**: Si una ruta no tiene stops, se usan coordenadas (0,0) como fallback
4. **Tiempos de viaje**: Se obtienen de OSRM real, con fallback a estimación por distancia

## Tests

```bash
cd backend
python -m pytest tests/test_suggestion_engine.py -v
```

## Archivos Relacionados

- `backend/services/suggestion_engine.py` - Implementación principal
- `backend/services/osrm_service.py` - Servicio OSRM
- `backend/main.py` - Endpoints API
- `backend/tests/test_suggestion_engine.py` - Tests unitarios
