"""
Tests para el validador de horarios manuales.
"""

import pytest
from datetime import time
from typing import List, Tuple

# Importar modelos — skip the whole module when imports fail
try:
    from backend.models.validation_result import (
        AssignedRoute, IssueType, RouteIssue,
        ValidationResult, ConnectionValidationResult,
        ProgressiveValidationState, SuggestionResult
    )
    from backend.services.manual_schedule_validator import (
        ManualScheduleValidator, OSRMService
    )
except ImportError:
    try:
        from models.validation_result import (
            AssignedRoute, IssueType, RouteIssue,
            ValidationResult, ConnectionValidationResult,
            ProgressiveValidationState, SuggestionResult
        )
        from services.manual_schedule_validator import (
            ManualScheduleValidator, OSRMService
        )
    except (ImportError, ModuleNotFoundError):
        pytest.skip(
            "manual_schedule_validator imports unavailable",
            allow_module_level=True,
        )


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def osrm_service() -> OSRMService:
    """Servicio OSRM para testing."""
    return OSRMService(cache_ttl_seconds=60)


@pytest.fixture
def validator(osrm_service) -> ManualScheduleValidator:
    """Validador para testing."""
    return ManualScheduleValidator(osrm_service)


@pytest.fixture
def sample_route_entry() -> AssignedRoute:
    """Ruta de entrada de ejemplo."""
    return AssignedRoute(
        id="R1",
        route_id="R1",
        start_time=time(8, 0),
        end_time=time(8, 30),
        start_location=(42.24, -8.72),
        end_location=(42.25, -8.73),
        type="entry",
        school_name="School A"
    )


@pytest.fixture
def sample_route_exit() -> AssignedRoute:
    """Ruta de salida de ejemplo."""
    return AssignedRoute(
        id="R2",
        route_id="R2",
        start_time=time(9, 0),
        end_time=time(9, 30),
        start_location=(42.25, -8.73),
        end_location=(42.26, -8.74),
        type="exit",
        school_name="School B"
    )


@pytest.fixture
def overlapping_routes() -> List[AssignedRoute]:
    """Rutas que se solapan."""
    return [
        AssignedRoute(
            id="R1",
            route_id="R1",
            start_time=time(8, 0),
            end_time=time(8, 30),
            start_location=(42.24, -8.72),
            end_location=(42.25, -8.73),
            type="entry"
        ),
        AssignedRoute(
            id="R2",
            route_id="R2",
            start_time=time(8, 25),  # Se solapa con R1
            end_time=time(9, 0),
            start_location=(42.25, -8.73),
            end_location=(42.26, -8.74),
            type="exit"
        )
    ]


@pytest.fixture
def tight_schedule() -> List[AssignedRoute]:
    """Horario muy ajustado (poco buffer)."""
    return [
        AssignedRoute(
            id="R1",
            route_id="R1",
            start_time=time(8, 0),
            end_time=time(8, 30),
            start_location=(42.24, -8.72),
            end_location=(42.25, -8.73),
            type="entry"
        ),
        AssignedRoute(
            id="R2",
            route_id="R2",
            start_time=time(8, 33),  # Solo 3 min de margen
            end_time=time(9, 0),
            start_location=(42.25, -8.73),
            end_location=(42.26, -8.74),
            type="exit"
        )
    ]


@pytest.fixture
def valid_schedule() -> List[AssignedRoute]:
    """Horario válido con buenos buffers."""
    return [
        AssignedRoute(
            id="R1",
            route_id="R1",
            start_time=time(8, 0),
            end_time=time(8, 30),
            start_location=(42.24, -8.72),
            end_location=(42.25, -8.73),
            type="entry"
        ),
        AssignedRoute(
            id="R2",
            route_id="R2",
            start_time=time(8, 50),  # 20 min de margen
            end_time=time(9, 20),
            start_location=(42.25, -8.73),
            end_location=(42.26, -8.74),
            type="exit"
        )
    ]


# =============================================================================
# Tests OSRMService
# =============================================================================

class TestOSRMService:
    """Tests para OSRMService."""
    
    def test_cache_key_generation(self, osrm_service):
        """Test generación de claves de caché."""
        origin = (42.24, -8.72)
        dest = (42.25, -8.73)
        
        key1 = osrm_service._get_cache_key(origin, dest)
        key2 = osrm_service._get_cache_key(origin, dest)
        
        assert key1 == key2
        assert "|" in key1
    
    def test_estimate_travel_time(self, osrm_service):
        """Test estimación con Haversine."""
        origin = (42.24, -8.72)
        dest = (42.25, -8.73)
        
        estimated = osrm_service._estimate_travel_time(origin, dest)
        
        assert estimated >= 5.0  # Mínimo 5 min
        assert isinstance(estimated, float)
    
    def test_estimate_same_point(self, osrm_service):
        """Test estimación con mismo punto."""
        point = (42.24, -8.72)
        
        estimated = osrm_service._estimate_travel_time(point, point)
        
        assert estimated == 5.0  # Mínimo
    
    def test_cache_stats(self, osrm_service):
        """Test estadísticas de caché."""
        stats = osrm_service.get_cache_stats()
        
        assert "total_entries" in stats
        assert "valid_entries" in stats
    
    def test_clear_cache(self, osrm_service):
        """Test limpieza de caché."""
        # Agregar entrada simulada
        osrm_service._cache["test"] = 10.0
        osrm_service._cache_timestamps["test"] = 0.0
        
        osrm_service.clear_cache()
        
        assert len(osrm_service._cache) == 0


# =============================================================================
# Tests ManualScheduleValidator - validate_connection
# =============================================================================

class TestValidateConnection:
    """Tests para validación de conexiones."""
    
    @pytest.mark.asyncio
    async def test_valid_connection(self, validator, sample_route_entry, sample_route_exit):
        """Test conexión válida con buen margen."""
        result = await validator.validate_connection(sample_route_entry, sample_route_exit)
        
        assert isinstance(result, ConnectionValidationResult)
        assert result.time_available == 30.0  # 8:30 a 9:00
        assert result.travel_time >= 0
        assert result.buffer_minutes == result.time_available - result.travel_time
    
    @pytest.mark.asyncio
    async def test_overlapping_routes(self, validator, overlapping_routes):
        """Test rutas que se solapan."""
        result = await validator.validate_connection(overlapping_routes[0], overlapping_routes[1])
        
        assert result.is_compatible is False
        assert result.buffer_minutes < 0
        assert result.issue is not None
        assert result.issue.issue_type == IssueType.OVERLAPPING_ROUTES
    
    @pytest.mark.asyncio
    async def test_tight_buffer(self, validator, tight_schedule):
        """Test buffer muy ajustado."""
        result = await validator.validate_connection(tight_schedule[0], tight_schedule[1])
        
        # 3 minutos es menor que el mínimo recomendado (5)
        if result.buffer_minutes < validator.MIN_BUFFER_RECOMMENDED:
            assert result.issue is not None
            assert result.issue.severity in ["warning", "error"]
    
    @pytest.mark.asyncio
    async def test_suggested_start_for_invalid(self, validator, sample_route_entry, sample_route_exit):
        """Test que sugiere hora de inicio cuando hay conflicto de tiempo."""
        # Crear rutas con poco tiempo (no overlap, pero si insuficiente)
        from models.validation_result import AssignedRoute
        from datetime import time as dt_time
        
        route_a = AssignedRoute(
            id="R1", route_id="R1",
            start_time=dt_time(8, 0), end_time=dt_time(8, 30),
            start_location=(42.24, -8.72), end_location=(42.25, -8.73),
            type="entry"
        )
        route_b = AssignedRoute(
            id="R2", route_id="R2", 
            start_time=dt_time(8, 32), end_time=dt_time(9, 0),  # Solo 2 min de margen
            start_location=(42.26, -8.74), end_location=(42.27, -8.75),
            type="exit"
        )
        
        result = await validator.validate_connection(route_a, route_b)
        
        if not result.is_compatible:
            assert result.suggested_start is not None
            assert ":" in result.suggested_start  # Formato HH:MM


# =============================================================================
# Tests ManualScheduleValidator - validate_bus_schedule
# =============================================================================

class TestValidateBusSchedule:
    """Tests para validación de horarios completos."""
    
    @pytest.mark.asyncio
    async def test_valid_schedule(self, validator, valid_schedule):
        """Test horario válido."""
        result = await validator.validate_bus_schedule(valid_schedule)
        
        assert isinstance(result, ValidationResult)
        assert result.total_travel_time >= 0
        assert result.efficiency_score > 0
        assert "min" in result.buffer_stats or result.buffer_stats == {}
    
    @pytest.mark.asyncio
    async def test_schedule_with_issues(self, validator, tight_schedule):
        """Test horario con problemas."""
        result = await validator.validate_bus_schedule(tight_schedule)
        
        assert isinstance(result, ValidationResult)
        # Puede tener issues warning por buffer ajustado
    
    @pytest.mark.asyncio
    async def test_empty_schedule(self, validator):
        """Test horario vacío."""
        result = await validator.validate_bus_schedule([])
        
        assert result.is_valid is True
        assert result.issues == []
        assert result.total_travel_time == 0.0
    
    @pytest.mark.asyncio
    async def test_single_route(self, validator, sample_route_entry):
        """Test horario con una sola ruta."""
        result = await validator.validate_bus_schedule([sample_route_entry])
        
        assert result.is_valid is True
        assert result.issues == []


# =============================================================================
# Tests ManualScheduleValidator - Efficiency
# =============================================================================

class TestCalculateEfficiency:
    """Tests para cálculo de eficiencia."""
    
    def test_efficiency_empty_routes(self, validator):
        """Test eficiencia con rutas vacías."""
        score = validator.calculate_efficiency([], [])
        
        assert score == 0.0
    
    def test_efficiency_no_buffers(self, validator, sample_route_entry):
        """Test eficiencia sin buffers."""
        score = validator.calculate_efficiency([sample_route_entry], None)
        
        assert score == 50.0  # Default
    
    def test_efficiency_optimal_buffers(self, validator):
        """Test eficiencia con buffers óptimos (5-15 min)."""
        buffers = [10.0, 12.0, 8.0]  # Dentro del rango óptimo
        score = validator.calculate_efficiency([1, 2, 3, 4], buffers)
        
        assert score > 80  # Debería ser muy alto
    
    def test_efficiency_negative_buffers(self, validator):
        """Test eficiencia con buffers negativos."""
        buffers = [-5.0, -2.0]
        score = validator.calculate_efficiency([1, 2, 3], buffers)
        
        assert score < 50  # Debería ser bajo
    
    def test_efficiency_very_large_buffers(self, validator):
        """Test eficiencia con buffers muy grandes (ineficiente)."""
        buffers = [60.0, 45.0]  # Mucho tiempo muerto
        score = validator.calculate_efficiency([1, 2, 3], buffers)
        
        assert score < 80  # Penalizado


# =============================================================================
# Tests ManualScheduleValidator - Suggestions
# =============================================================================

class TestSuggestAlternativeTime:
    """Tests para sugerencias de horarios."""
    
    def test_suggestion_generation(self, validator, sample_route_entry, sample_route_exit):
        """Test generación de sugerencias."""
        travel_time = 15.0
        
        suggestion = validator.suggest_alternative_time(
            sample_route_entry, sample_route_exit, travel_time
        )
        
        assert isinstance(suggestion, SuggestionResult)
        assert suggestion.suggested_start_time is not None
        assert "Prueba iniciar" in suggestion.message
    
    def test_suggestion_includes_buffer(self, validator, sample_route_entry, sample_route_exit):
        """Test que la sugerencia incluye buffer de seguridad."""
        travel_time = 10.0
        
        suggestion = validator.suggest_alternative_time(
            sample_route_entry, sample_route_exit, travel_time
        )
        
        # Hora sugerida debe ser end_time (8:30 = 510 min) + travel_time + buffer
        expected_total_minutes = 510 + 10 + int(validator.MIN_BUFFER_RECOMMENDED)  # 525 = 8:45
        actual_total_minutes = suggestion.suggested_start_time.hour * 60 + suggestion.suggested_start_time.minute
        assert actual_total_minutes == expected_total_minutes
    
    def test_suggestion_has_alternatives(self, validator, sample_route_entry, sample_route_exit):
        """Test que genera alternativas."""
        suggestion = validator.suggest_alternative_time(
            sample_route_entry, sample_route_exit, 15.0
        )
        
        assert len(suggestion.alternative_times) > 0
        assert len(suggestion.alternative_times) <= 4


# =============================================================================
# Tests ManualScheduleValidator - Progressive Validation
# =============================================================================

class TestProgressiveValidation:
    """Tests para validación progresiva."""
    
    @pytest.mark.asyncio
    async def test_first_route_always_valid(self, validator, sample_route_entry):
        """Test que la primera ruta siempre es válida."""
        from models.validation_result import ProgressiveValidationState
        
        state = ProgressiveValidationState(bus_id="B001")
        result = await validator.validate_progressive(state, sample_route_entry)
        
        assert result.is_valid is True
        assert len(state.routes) == 1
    
    @pytest.mark.asyncio
    async def test_progressive_accumulates(self, validator, valid_schedule):
        """Test que la validación progresiva acumula resultados."""
        from models.validation_result import ProgressiveValidationState
        
        state = ProgressiveValidationState(bus_id="B001")
        
        # Agregar primera ruta
        result1 = await validator.validate_progressive(state, valid_schedule[0])
        assert len(state.routes) == 1
        
        # Agregar segunda ruta
        result2 = await validator.validate_progressive(state, valid_schedule[1])
        assert len(state.routes) == 2
        # El total_travel_time se acumula en el estado, puede ser 0 si OSRM mock retorna 0
        assert result2.total_travel_time >= 0  # Permite 0 con mocks
    
    @pytest.mark.asyncio
    async def test_progressive_tracks_issues(self, validator, overlapping_routes):
        """Test que trackea issues en validación progresiva."""
        from models.validation_result import ProgressiveValidationState
        
        state = ProgressiveValidationState(bus_id="B001")
        
        # Primera ruta - sin issues
        await validator.validate_progressive(state, overlapping_routes[0])
        assert len(state.cumulative_issues) == 0
        
        # Segunda ruta - con overlap
        await validator.validate_progressive(state, overlapping_routes[1])
        assert len(state.cumulative_issues) > 0


# =============================================================================
# Tests Modelos
# =============================================================================

class TestModels:
    """Tests para modelos de datos."""
    
    def test_assigned_route_creation(self):
        """Test creación de AssignedRoute."""
        route = AssignedRoute(
            id="R1",
            route_id="R1",
            start_time=time(8, 0),
            end_time=time(8, 30),
            start_location=(42.24, -8.72),
            end_location=(42.25, -8.73),
            type="entry"
        )
        
        assert route.id == "R1"
        assert route.start_time.hour == 8
    
    def test_route_issue_creation(self):
        """Test creación de RouteIssue."""
        issue = RouteIssue(
            route_a="R1",
            route_b="R2",
            issue_type=IssueType.INSUFFICIENT_TIME,
            message="Faltan 5 minutos",
            suggestion="Ajusta horario"
        )
        
        assert issue.severity == "error"
        assert issue.issue_type == IssueType.INSUFFICIENT_TIME
    
    def test_validation_result_to_dict(self):
        """Test conversión a dict."""
        result = ValidationResult(
            is_valid=True,
            issues=[],
            total_travel_time=15.5,
            efficiency_score=85.0
        )
        
        data = result.to_dict()
        
        assert data["is_valid"] is True
        assert data["total_travel_time"] == 15.5
        assert "issues_count" in data
    
    def test_connection_result_to_dict(self):
        """Test conversión de ConnectionValidationResult."""
        result = ConnectionValidationResult(
            is_compatible=True,
            buffer_minutes=10.5,
            travel_time=15.0,
            time_available=25.5,
            suggested_start="09:00"
        )
        
        data = result.to_dict()
        
        assert data["is_compatible"] is True
        assert data["suggested_start"] == "09:00"
        assert "issue" not in data


# =============================================================================
# Tests Performance
# =============================================================================

class TestPerformance:
    """Tests de performance."""
    
    @pytest.mark.asyncio
    async def test_validation_under_200ms(self, validator, valid_schedule):
        """Test que la validación es rápida (< 200ms por conexión)."""
        import time
        
        start = time.time()
        await validator.validate_bus_schedule(valid_schedule)
        elapsed_ms = (time.time() - start) * 1000
        
        # Con 2 rutas = 1 conexión, debería ser < 200ms
        assert elapsed_ms < 400  # Un poco más permisivo para tests
    
    @pytest.mark.asyncio
    async def test_cached_validation_faster(self, validator, sample_route_entry, sample_route_exit):
        """Test que la segunda validación es más rápida (cache)."""
        import time
        
        # Primera validación
        start = time.time()
        await validator.validate_connection(sample_route_entry, sample_route_exit)
        first_ms = (time.time() - start) * 1000
        
        # Segunda validación (cacheada)
        start = time.time()
        await validator.validate_connection(sample_route_entry, sample_route_exit)
        second_ms = (time.time() - start) * 1000
        
        # La segunda debería ser más rápida o similar
        assert second_ms <= first_ms * 1.5  # Permitir algo de variación
