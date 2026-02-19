---
name: tutti-testing
description: Testing y calidad para Tutti Fleet Optimizer. Usar cuando se necesite escribir, ejecutar o debuggear tests unitarios, integracion o end-to-end. Incluye pytest, playwright, cobertura de codigo, fixtures y mejores practicas de testing.
---

# Tutti Testing Skill

## Estructura de Tests

```
backend/tests/
├── conftest.py               # Fixtures y configuracion pytest
├── test_optimizer.py         # Tests de optimizadores
├── test_optimizer_advanced.py # Tests avanzados de optimizacion
├── test_parser.py            # Tests del parser Excel
├── test_router_service.py    # Tests de OSRM integration
├── test_validation.py        # Tests de validacion
├── test_websocket.py         # Tests de WebSockets
├── test_workspace_crud.py    # Tests de DB/workspace
└── fixtures/                 # Datos de prueba
    └── sample_routes.py

frontend/
├── e2e/                      # Playwright E2E tests
│   └── control-studio-smoke.spec.js
└── package.json              # Scripts de test
```

## Testing Backend (Pytest)

### Ejecutar Tests

```bash
# Todos los tests
.\.venv\Scripts\python -m pytest backend/tests -v

# Tests especificos
.\.venv\Scripts\python -m pytest backend/tests/test_optimizer.py -v

# Con cobertura
.\.venv\Scripts\python -m pytest backend/tests --cov=backend --cov-report=html

# Solo tests lentos
.\.venv\Scripts\python -m pytest backend/tests -m slow

# Solo tests rapidos
.\.venv\Scripts\python -m pytest backend/tests -m "not slow"
```

### Estructura de Test

```python
# backend/tests/test_mi_modulo.py
import pytest
from models import Route, Stop
from mi_modulo import mi_funcion

class TestMiFuncion:
    """Tests para mi_funcion."""
    
    def test_caso_basico(self):
        """Test caso basico de uso."""
        # Arrange
        entrada = crear_ruta_simple()
        
        # Act
        resultado = mi_funcion(entrada)
        
        # Assert
        assert resultado is not None
        assert len(resultado) > 0
    
    def test_caso_edge_empty(self):
        """Test con entrada vacia."""
        resultado = mi_funcion([])
        assert resultado == []
    
    def test_caso_error(self):
        """Test que lanza excepcion."""
        with pytest.raises(ValueError, match="mensaje esperado"):
            mi_funcion(None)
```

### Fixtures

```python
# conftest.py
import pytest
from models import Route, Stop

@pytest.fixture
def sample_stop():
    """Stop de ejemplo."""
    return Stop(
        name="Parada Test",
        lat=42.5,
        lon=-8.3,
        order=1,
        time_from_start=10,
        passengers=5
    )

@pytest.fixture
def sample_route(sample_stop):
    """Ruta de ejemplo."""
    return Route(
        id="R001_E1",
        name="Ruta Test",
        stops=[sample_stop],
        school_id="S001",
        school_name="Colegio Test",
        arrival_time=time(9, 0),
        capacity_needed=20,
        contract_id="C001",
        type="entry",
        days=["L", "M", "X", "J", "V"]
    )

@pytest.fixture
def sample_routes():
    """Lista de rutas de ejemplo."""
    return [
        # Crear varias rutas para testing
    ]
```

### Marks Personalizados

```python
# pytest.ini o pyproject.toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "osrm: tests that require OSRM connection",
]

# Uso
@pytest.mark.slow
def test_optimization_grande():
    pass

@pytest.mark.osrm
@pytest.mark.integration
def test_routing_real():
    pass
```

### Mocking

```python
from unittest.mock import Mock, patch

def test_con_mock():
    """Test usando mocks."""
    # Mock de funcion
    with patch('router_service.requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            'code': 'Ok',
            'routes': [{'duration': 600}]
        }
        mock_get.return_value.status_code = 200
        
        result = get_real_travel_time(...)
        assert result == 10  # 600 segundos = 10 minutos

# Mock de dependencia
@pytest.fixture
def mock_db():
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = Mock(id="123")
    return db
```

## Testing Frontend (Playwright)

### Setup

```bash
cd frontend
npm install
npx playwright install
```

### Ejecutar Tests

```bash
# Todos los E2E tests
npm run test:e2e

# Tests smoke
npm run test:e2e:smoke

# Con UI
npm run test:e2e:ui

# Headed (ver navegador)
npx playwright test --headed

# Debug
npx playwright test --debug
```

### Estructura E2E Test

```javascript
// e2e/flujo-completo.spec.js
const { test, expect } = require('@playwright/test');

test.describe('Flujo Completo', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:8000');
  });

  test('cargar excel y optimizar', async ({ page }) => {
    // 1. Cargar archivo
    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      page.click('[data-testid="upload-button"]')
    ]);
    await fileChooser.setFiles('fixtures/sample-routes.xlsx');

    // 2. Verificar carga
    await expect(page.locator('[data-testid="routes-count"]')).toHaveText('10 rutas');

    // 3. Optimizar
    await page.click('[data-testid="optimize-button"]');

    // 4. Verificar resultado
    await expect(page.locator('[data-testid="schedule-loaded"]')).toBeVisible();
  });

  test('drag and drop en timeline', async ({ page }) => {
    // Setup...
    
    // Drag and drop
    const source = page.locator('[data-testid="route-block-1"]');
    const target = page.locator('[data-testid="bus-row-2"]');
    
    await source.dragTo(target);
    
    // Verificar
    await expect(page.locator('[data-testid="success-toast"]')).toBeVisible();
  });
});
```

### Selectores Data-TestId

```jsx
// Componente con test ids
const RouteBlock = ({ route }) => (
  <div data-testid={`route-block-${route.id}`}>
    <span data-testid="route-name">{route.name}</span>
    <button data-testid="edit-route">Editar</button>
  </div>
);
```

## Cobertura de Codigo

### Backend

```bash
# Generar reporte HTML
.\.venv\Scripts\python -m pytest backend/tests --cov=backend --cov-report=html

# Ver en browser
start htmlcov\index.html

# Cobertura minima
.\.venv\Scripts\python -m pytest backend/tests --cov=backend --cov-fail-under=80
```

### Frontend

```bash
# Vite + Vitest (si esta configurado)
npm run test -- --coverage
```

## Testing Integracion

### Test End-to-End Completo

```python
# tests/test_e2e.py
@pytest.mark.integration
@pytest.mark.slow
def test_flujo_completo(tmp_path):
    """Test desde Excel hasta PDF."""
    # 1. Crear Excel de prueba
    excel_path = crear_excel_prueba(tmp_path)
    
    # 2. Parsear
    routes = parse_routes(excel_path)
    assert len(routes) > 0
    
    # 3. Optimizar
    schedule = optimize_v6(routes)
    assert len(schedule) < len(routes)
    
    # 4. Validar
    validator = ManualScheduleValidator(OSRMService())
    result = validator.validate(schedule)
    assert result.is_valid
    
    # 5. Exportar PDF
    pdf = generate_pdf(schedule)
    assert len(pdf) > 0
```

## Testing Performance

### Benchmarks

```python
# tests/test_performance.py
import time

@pytest.mark.benchmark
@pytest.mark.slow
def test_optimizer_performance(sample_100_routes):
    """Benchmark de optimizador."""
    start = time.perf_counter()
    
    schedule = optimize_v6(sample_100_routes)
    
    elapsed = time.perf_counter() - start
    
    # Debe completar en menos de 60 segundos
    assert elapsed < 60.0
    
    # Ratio de compresion
    ratio = len(schedule) / len(sample_100_routes)
    assert ratio < 0.5  # Al menos 50% de compresion
```

## Calidad de Codigo

### Pre-commit Hooks

```bash
# Instalar pre-commit
.\.venv\Scripts\pip install pre-commit
pre-commit install

# Ejecutar manualmente
pre-commit run --all-files
```

### Linting

```bash
# Python (ruff)
.\.venv\Scripts\ruff check backend
.\.venv\Scripts\ruff format backend

# JavaScript (eslint)
cd frontend
npm run lint
npm run lint:fix
```

### Type Checking

```bash
# Python (mypy)
.\.venv\Scripts\mypy backend

# TypeScript
cd frontend
npx tsc --noEmit
```

## Mejores Practicas

### DO's

1. **Tests independientes**: Cada test debe poder correr solo
2. **Nombres descriptivos**: `test_suma_dos_numeros` mejor que `test_1`
3. **Arrange-Act-Assert**: Estructura clara
4. **Un assert por test**: Idealmente, test una cosa
5. **Mantener tests rapidos**: < 1s si es posible

### DON'Ts

1. **No tests que dependen de estado**: Limpiar despues de cada test
2. **No hardcodear paths**: Usar tmp_path o fixtures
3. **No tests que requieren OSRM para pasar**: Marcar como optional
4. **No ignorar fallos flaky**: Investigar y fixear

## Referencias

- `references/test-fixtures.md`: Fixtures y datos de prueba
- `references/e2e-patterns.md`: Patrones de E2E testing
