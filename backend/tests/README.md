# Tutti Backend Test Suite

Suite de tests completa para el backend del Optimizador de Rutas de Autobuses Escolares Tutti.

## Estructura

```
tests/
├── __init__.py                   # Package marker
├── conftest.py                   # Fixtures compartidos de pytest
├── README.md                     # Esta documentación
├── test_models.py                # Tests de modelos Pydantic
├── test_parser.py                # Tests del parser Excel
├── test_optimizer.py             # Tests del optimizador V6
├── test_router_service.py        # Tests del servicio de routing (con mocks)
├── test_suggestion_engine.py     # Tests del motor de sugerencias ⭐ NUEVO
├── test_api_async.py             # Tests de API asíncrona
├── test_celery.py                # Tests de tareas Celery
├── test_e2e_async.py             # Tests E2E asíncronos
├── test_websocket.py             # Tests de WebSocket
├── test_validation.py            # Tests de validación
└── fixtures/
    ├── sample_routes.json        # Rutas de ejemplo en JSON
    ├── sample_excel.xlsx         # Archivo Excel de prueba
    └── generate_sample_excel.py  # Script para generar el Excel
```

## Ejecución

```bash
# Ejecutar todos los tests
pytest

# Ejecutar con coverage
pytest --cov=. --cov-report=html

# Ejecutar tests específicos
pytest tests/test_models.py
pytest tests/test_optimizer.py -v
pytest tests/test_suggestion_engine.py -v  # ⭐ NUEVO

# Ejecutar tests rápidos (excluir integración)
pytest -m "not integration"

# Ejecutar tests de optimizer solamente
pytest -m optimizer

# Ejecutar tests de sugerencias
pytest tests/test_suggestion_engine.py

# Ejecutar tests con reporte de performance
pytest tests/test_suggestion_engine.py::test_suggestion_performance_under_1_second -v
```

## Nuevo: Motor de Sugerencias (test_suggestion_engine.py)

El motor de sugerencias proporciona recomendaciones inteligentes para asignar rutas a buses.

### Tests incluidos:

| Test | Descripción |
|------|-------------|
| `test_suggestion_engine_returns_ordered_results` | Verifica ordenamiento por score |
| `test_suggestion_empty_bus_is_always_viable` | Bus vacío siempre es opción viable |
| `test_suggestion_considers_capacity` | Considera capacidad del bus |
| `test_suggestion_detects_time_conflicts` | Detecta conflictos de horario |
| `test_suggestion_prefers_current_bus` | Prioridad al bus actual |
| `test_suggestion_considers_geographic_proximity` | Favorece buses cercanos |
| `test_suggestion_performance_under_1_second` | Performance < 1 segundo |
| `test_suggestion_performance_with_many_buses` | Test con 20 buses |
| `test_validate_compatibility_detects_capacity_issues` | Valida capacidad |
| `test_validate_compatibility_detects_time_conflicts` | Valida tiempo |

### Fixtures disponibles:

- `mock_osrm` - Servicio OSRM mock
- `suggestion_engine` - Instancia del motor
- `test_route` / `test_route_exit` - Rutas de prueba
- `empty_bus` - Bus vacío
- `bus_with_routes` - Bus con rutas asignadas
- `bus_full_capacity` - Bus con capacidad casi llena
- `bus_with_time_conflict` - Bus con conflicto de horario

### Ejemplo de uso:

```python
import pytest
from services.suggestion_engine import SuggestionEngine

@pytest.mark.asyncio
async def test_mi_feature(suggestion_engine, test_route, empty_bus):
    suggestions = await suggestion_engine.generate_suggestions(
        test_route, [empty_bus]
    )
    assert len(suggestions) > 0
    assert suggestions[0].score >= 95
```

## Markers

- `slow`: Tests que tardan más de 1 segundo
- `integration`: Tests que requieren archivos externos o APIs
- `optimizer`: Tests del optimizador de rutas
- `asyncio`: Tests asíncronos (requiere pytest-asyncio)

## Fixtures Disponibles (conftest.py)

### Modelos
- `sample_stop`: Stop básico
- `school_stop`: Parada de escuela
- `multiple_stops`: Lista de paradas
- `entry_route`: Ruta de entrada (mañana)
- `exit_route`: Ruta de salida (tarde)
- `multiple_entry_routes`: 5 rutas de entrada
- `multiple_exit_routes`: 5 rutas de salida
- `optimizer_test_routes`: 15 rutas mixtas para testing

### Archivos
- `sample_json_path`: Path a sample_routes.json
- `sample_excel_path`: Path a sample_excel.xlsx

## Coverage Report

El reporte HTML se genera en `htmlcov/index.html`:

```bash
pytest --cov=backend --cov-report=html
# Abrir htmlcov/index.html
```

## Estadísticas Actuales

| Módulo | Tests | Coverage |
|--------|-------|----------|
| models.py | 25 | 100% |
| parser.py | 15 | 93% |
| optimizer_*.py | 40 | 79% |
| router_service.py | 12 | 94% |
| suggestion_engine.py | 20 | 90% | ⭐ NUEVO |
| **Total** | **150+** | **84%** |

## CI/CD

Los tests se ejecutan automáticamente en GitHub Actions:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: pytest --cov=backend --cov-report=xml
  
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'backend'"

Asegúrate de ejecutar desde el directorio raíz del proyecto:

```bash
cd c:\Users\Juanjo\Desktop\ODINX LABS\bus-route-optimizer
pytest backend/tests/
```

### Error: "asyncio fixture request"

Instala pytest-asyncio:

```bash
pip install pytest-asyncio
```

### Tests de sugerencias lentos

Los tests de performance usan timeouts. Si fallan por lentitud:

```bash
# Ejecutar sin tests de performance
pytest tests/test_suggestion_engine.py -k "not performance"
```
