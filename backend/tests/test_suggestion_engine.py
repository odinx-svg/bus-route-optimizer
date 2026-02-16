"""
Tests para el motor de sugerencias (SuggestionEngine).

Este modulo prueba:
- Generacion de sugerencias para rutas
- Calculo de scores con diferentes factores
- Integracion con OSRMService
- Ordenamiento y filtrado de sugerencias
"""

import pytest
import asyncio
from datetime import time
from typing import List, Dict, Any

# Importar modelos y el motor de sugerencias
try:
    from backend.models import Route, Bus, Stop
    from backend.services.suggestion_engine import (
        SuggestionEngine, Suggestion, SuggestionResponse,
        get_route_coordinates, estimate_route_times, calculate_distance_km,
        time_to_minutes, minutes_to_time, time_diff_minutes,
        get_suggestion_engine, reset_suggestion_engine
    )
    from backend.services.osrm_service import OSRMService, TravelTimeResult, Coordinates
    from backend.models.validation import Coordinates as ValidationCoordinates
except ImportError:
    from models import Route, Bus, Stop
    from services.suggestion_engine import (
        SuggestionEngine, Suggestion, SuggestionResponse,
        get_route_coordinates, estimate_route_times, calculate_distance_km,
        time_to_minutes, minutes_to_time, time_diff_minutes,
        get_suggestion_engine, reset_suggestion_engine
    )
    from services.osrm_service import OSRMService, TravelTimeResult, Coordinates
    from models.validation import Coordinates as ValidationCoordinates


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_route() -> Route:
    """Crea una ruta de ejemplo para testing."""
    return Route(
        id="R001",
        name="Ruta Test",
        stops=[
            Stop(name="Parada 1", lat=-33.4489, lon=-70.6693, order=1, time_from_start=0, passengers=10),
            Stop(name="Parada 2", lat=-33.4567, lon=-70.6500, order=2, time_from_start=15, passengers=15),
        ],
        school_id="S1",
        school_name="Escuela Test",
        arrival_time=time(8, 30),
        capacity_needed=25,
        contract_id="C1",
        type="entry",
        days=["L", "M", "Mc", "X", "V"]
    )


@pytest.fixture
def sample_buses() -> List[Bus]:
    """Crea una lista de buses de ejemplo."""
    return [
        Bus(id="BUS01", capacity=50, plate="ABC123"),
        Bus(id="BUS02", capacity=45, plate="DEF456"),
        Bus(id="BUS03", capacity=30, plate="GHI789"),
    ]


@pytest.fixture
def empty_bus_schedules() -> Dict[str, List[Dict[str, Any]]]:
    """Schedules vacios (buses sin rutas asignadas)."""
    return {
        "BUS01": [],
        "BUS02": [],
        "BUS03": [],
    }


@pytest.fixture
def populated_bus_schedules() -> Dict[str, List[Dict[str, Any]]]:
    """Schedules con rutas asignadas."""
    return {
        "BUS01": [
            {
                "route_id": "R002",
                "start_time": "07:00",
                "end_time": "07:45",
                "stops": [
                    {"name": "P1", "lat": -33.4600, "lon": -70.6800, "order": 1},
                    {"name": "P2", "lat": -33.4700, "lon": -70.6900, "order": 2},
                ]
            },
            {
                "route_id": "R003",
                "start_time": "09:00",
                "end_time": "09:30",
                "stops": [
                    {"name": "P3", "lat": -33.4800, "lon": -70.7000, "order": 1},
                    {"name": "P4", "lat": -33.4900, "lon": -70.7100, "order": 2},
                ]
            }
        ],
        "BUS02": [],
        "BUS03": [
            {
                "route_id": "R004",
                "start_time": "06:30",
                "end_time": "07:15",
                "stops": [
                    {"name": "P5", "lat": -33.4400, "lon": -70.6600, "order": 1},
                ]
            }
        ],
    }


class MockOSRMService:
    """Mock de OSRMService para testing sin dependencias externas."""
    
    def __init__(self):
        self._cache: Dict[str, TravelTimeResult] = {}
        self._stats = {'requests': 0, 'cache_hits': 0, 'fallbacks': 0, 'errors': 0}
    
    async def get_travel_time(self, start: ValidationCoordinates, end: ValidationCoordinates) -> TravelTimeResult:
        """Retorna un tiempo de viaje fijo para testing."""
        key = f"{start.lat},{start.lon}|{end.lat},{end.lon}"
        
        if key in self._cache:
            self._stats['cache_hits'] += 1
            return self._cache[key]
        
        # Simular tiempo de viaje basado en distancia (aproximadamente 30 km/h)
        distance_km = self._euclidean_distance_km(start, end)
        minutes = (distance_km / 30) * 60  # 30 km/h promedio
        
        result = TravelTimeResult(
            minutes=minutes,
            distance_km=distance_km,
            from_cache=False
        )
        
        self._cache[key] = result
        self._stats['requests'] += 1
        return result
    
    def _euclidean_distance_km(self, start: ValidationCoordinates, end: ValidationCoordinates) -> float:
        """Distancia Haversine simplificada."""
        import math
        R = 6371
        lat1 = math.radians(start.lat)
        lat2 = math.radians(end.lat)
        dlat = math.radians(end.lat - start.lat)
        dlon = math.radians(end.lon - start.lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    
    def get_stats(self) -> Dict[str, int]:
        return self._stats.copy()
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            'status': 'healthy',
            'response_time_ms': 10.0,
            'cache_size': len(self._cache),
            'base_url': 'mock://osrm',
            'error': None
        }


@pytest.fixture
def mock_osrm_service():
    """Crea un mock de OSRMService."""
    return MockOSRMService()


@pytest.fixture
def suggestion_engine(mock_osrm_service) -> SuggestionEngine:
    """Crea un SuggestionEngine con OSRM mockeado."""
    reset_suggestion_engine()
    return SuggestionEngine(osrm_service=mock_osrm_service)


# =============================================================================
# Tests de Utilidades
# =============================================================================

class TestUtilities:
    """Tests para funciones utilitarias."""
    
    def test_time_to_minutes(self):
        """Test conversion de time a minutos."""
        assert time_to_minutes(time(8, 30)) == 510
        assert time_to_minutes(time(0, 0)) == 0
        assert time_to_minutes(time(23, 59)) == 1439
    
    def test_minutes_to_time(self):
        """Test conversion de minutos a time."""
        assert minutes_to_time(510) == time(8, 30)
        assert minutes_to_time(0) == time(0, 0)
        assert minutes_to_time(1439) == time(23, 59)
    
    def test_time_diff_minutes(self):
        """Test diferencia entre dos tiempos."""
        assert time_diff_minutes(time(7, 0), time(8, 0)) == 60
        assert time_diff_minutes(time(8, 0), time(7, 0)) == -60
        assert time_diff_minutes(time(8, 30), time(9, 15)) == 45
    
    def test_get_route_coordinates(self, sample_route):
        """Test extraccion de coordenadas de ruta."""
        start, end = get_route_coordinates(sample_route)
        assert start.lat == -33.4489
        assert start.lon == -70.6693
        assert end.lat == -33.4567
        assert end.lon == -70.6500
    
    def test_calculate_distance_km(self):
        """Test calculo de distancia Haversine."""
        coord1 = ValidationCoordinates(lat=0, lon=0)
        coord2 = ValidationCoordinates(lat=0, lon=1)
        distance = calculate_distance_km(coord1, coord2)
        # Aproximadamente 111 km por grado de longitud en el ecuador
        assert 110 < distance < 112
    
    def test_estimate_route_times_entry(self, sample_route):
        """Test estimacion de tiempos para ruta de entrada."""
        start, end = estimate_route_times(sample_route)
        # Ruta de 15 minutos, llegada a las 8:30
        assert start == time(8, 15)
        assert end == time(8, 30)
    
    def test_estimate_route_times_exit(self):
        """Test estimacion de tiempos para ruta de salida."""
        route = Route(
            id="R002",
            name="Ruta Salida",
            stops=[
                Stop(name="P1", lat=-33.4489, lon=-70.6693, order=1, time_from_start=0),
                Stop(name="P2", lat=-33.4567, lon=-70.6500, order=2, time_from_start=20),
            ],
            school_id="S1",
            school_name="Escuela Test",
            departure_time=time(15, 0),
            capacity_needed=20,
            contract_id="C1",
            type="exit"
        )
        start, end = estimate_route_times(route)
        assert start == time(15, 0)
        assert end == time(15, 20)


# =============================================================================
# Tests del SuggestionEngine
# =============================================================================

class TestSuggestionEngine:
    """Tests para SuggestionEngine."""
    
    @pytest.mark.asyncio
    async def test_empty_bus_suggestion(self, suggestion_engine, sample_route, sample_buses, empty_bus_schedules):
        """Test sugerencias para buses vacios."""
        response = await suggestion_engine.generate_suggestions(
            route=sample_route,
            buses=sample_buses,
            bus_schedules=empty_bus_schedules,
            max_suggestions=5
        )
        
        assert response.route_id == "R001"
        assert len(response.suggestions) == 3  # Uno por cada bus vacio
        assert response.total_evaluated == 3
        
        # Todas las sugerencias deben tener score 100 (buses vacios)
        for suggestion in response.suggestions:
            assert suggestion.score == 100.0
            assert suggestion.position == 0
            assert "empty_bus" in suggestion.factors
    
    @pytest.mark.asyncio
    async def test_populated_bus_suggestions(self, suggestion_engine, sample_route, sample_buses, populated_bus_schedules):
        """Test sugerencias para buses con rutas existentes."""
        response = await suggestion_engine.generate_suggestions(
            route=sample_route,
            buses=sample_buses,
            bus_schedules=populated_bus_schedules,
            max_suggestions=10
        )
        
        assert response.route_id == "R001"
        # BUS01: 3 posiciones (inicio, entre R002-R003, final)
        # BUS02: 1 posicion (bus vacio)
        # BUS03: 2 posiciones (inicio, final)
        assert response.total_evaluated == 6
        
        # Las sugerencias deben estar ordenadas por score descendente
        scores = [s.score for s in response.suggestions]
        assert scores == sorted(scores, reverse=True)
    
    @pytest.mark.asyncio
    async def test_suggestion_factors(self, suggestion_engine, sample_route, sample_buses, populated_bus_schedules):
        """Test que las sugerencias incluyen todos los factores esperados."""
        response = await suggestion_engine.generate_suggestions(
            route=sample_route,
            buses=sample_buses,
            bus_schedules=populated_bus_schedules,
            max_suggestions=1
        )
        
        suggestion = response.suggestions[0]
        factors = suggestion.factors
        
        # Verificar que existen los factores principales
        assert "prev_buffer" in factors or "empty_bus" in factors
        assert "next_buffer" in factors or "empty_bus" in factors
        assert "geographic_proximity" in factors or "empty_bus" in factors
        assert "capacity" in factors
    
    @pytest.mark.asyncio
    async def test_max_suggestions_limit(self, suggestion_engine, sample_route, sample_buses, populated_bus_schedules):
        """Test que respeta el limite de sugerencias."""
        for limit in [1, 3, 5]:
            response = await suggestion_engine.generate_suggestions(
                route=sample_route,
                buses=sample_buses,
                bus_schedules=populated_bus_schedules,
                max_suggestions=limit
            )
            assert len(response.suggestions) <= limit
    
    @pytest.mark.asyncio
    async def test_empty_bus_score_perfect(self, suggestion_engine, sample_route, sample_buses, empty_bus_schedules):
        """Test que buses vacios tienen score perfecto."""
        response = await suggestion_engine.generate_suggestions(
            route=sample_route,
            buses=sample_buses,
            bus_schedules=empty_bus_schedules,
            max_suggestions=5
        )
        
        for suggestion in response.suggestions:
            assert suggestion.score == 100.0
            assert suggestion.buffer_time == 999  # Buffer infinito
            assert suggestion.travel_time_from_prev == 0
    
    def test_score_buffer_calculation(self, suggestion_engine):
        """Test del calculo de score para buffers."""
        # Buffer negativo: incompatible
        assert suggestion_engine._score_buffer(-5) == 0.0
        # Buffer justo
        assert suggestion_engine._score_buffer(3) == 0.3
        # Buffer aceptable
        assert suggestion_engine._score_buffer(7) == 0.6
        # Buffer bueno
        assert suggestion_engine._score_buffer(15) == 0.85
        # Buffer excelente
        assert suggestion_engine._score_buffer(25) == 1.0
    
    def test_geographic_proximity_score(self, suggestion_engine):
        """Test del score de proximidad geografica."""
        # Muy cercano
        assert suggestion_engine._score_geographic_proximity(1.5) == 1.0
        # Cercano
        assert suggestion_engine._score_geographic_proximity(3) == 0.8
        # Moderado
        assert suggestion_engine._score_geographic_proximity(7) == 0.5
        # Lejano
        assert suggestion_engine._score_geographic_proximity(15) == 0.3
        # Muy lejano
        assert suggestion_engine._score_geographic_proximity(25) == 0.1
    
    def test_capacity_score(self, suggestion_engine):
        """Test del score de capacidad."""
        # Capacidad insuficiente
        assert suggestion_engine._score_capacity(30, 35) == 0.0
        # Capacidad justa (< 20% margen)
        assert suggestion_engine._score_capacity(30, 28) == 0.7
        # Capacidad suficiente (> 20% margen)
        assert suggestion_engine._score_capacity(50, 25) == 1.0


# =============================================================================
# Tests de Integracion
# =============================================================================

class TestSuggestionEngineIntegration:
    """Tests de integracion con dependencias reales (o mockeadas)."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_suggestion_flow(self):
        """Test del flujo completo de generacion de sugerencias."""
        reset_suggestion_engine()
        
        # Crear OSRM mock
        osrm = MockOSRMService()
        engine = SuggestionEngine(osrm_service=osrm)
        
        # Crear ruta de prueba
        route = Route(
            id="R_TEST",
            name="Ruta Integracion",
            stops=[
                Stop(name="Inicio", lat=-33.4489, lon=-70.6693, order=1, time_from_start=0),
                Stop(name="Fin", lat=-33.4567, lon=-70.6500, order=2, time_from_start=20),
            ],
            school_id="S1",
            school_name="Escuela Test",
            arrival_time=time(9, 0),
            capacity_needed=30,
            contract_id="C1",
            type="entry"
        )
        
        # Crear buses
        buses = [Bus(id=f"BUS_{i:02d}", capacity=50) for i in range(5)]
        
        # Schedules con algunos buses ocupados
        schedules = {
            "BUS_00": [
                {
                    "route_id": "R_EXISTING",
                    "start_time": "07:00",
                    "end_time": "08:00",
                    "stops": [
                        {"name": "P1", "lat": -33.4400, "lon": -70.6600, "order": 1},
                    ]
                }
            ],
            "BUS_01": [],
            "BUS_02": [],
            "BUS_03": [
                {
                    "route_id": "R_EARLY",
                    "start_time": "06:00",
                    "end_time": "06:45",
                    "stops": [
                        {"name": "P2", "lat": -33.4700, "lon": -70.6800, "order": 1},
                    ]
                }
            ],
            "BUS_04": [],
        }
        
        response = await engine.generate_suggestions(
            route=route,
            buses=buses,
            bus_schedules=schedules,
            max_suggestions=5
        )
        
        # Verificar estructura de respuesta
        assert isinstance(response, SuggestionResponse)
        assert response.route_id == "R_TEST"
        assert len(response.suggestions) > 0
        assert response.total_evaluated > 0
        
        # Verificar que hay sugerencias de buses vacios con score 100
        empty_bus_suggestions = [s for s in response.suggestions if s.score == 100.0]
        # Al menos los 3 buses vacios (BUS_01, BUS_02, BUS_04) deben tener score 100
        # Pero si un bus con ruta tiene buen buffer, tambien puede tener score 100
        assert len(empty_bus_suggestions) >= 3
        
        # Verificar OSRM stats
        assert response.osrm_stats is not None
        assert response.osrm_stats['requests'] > 0


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
