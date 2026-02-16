"""
Tests para módulo de validación Monte Carlo.
"""

import pytest
from datetime import time
from typing import List, Dict, Tuple

from models import Route, BusSchedule, ScheduleItem, Stop
from validation.monte_carlo import (
    MonteCarloValidator,
    SimulationResult,
    check_schedule_feasibility,
    extract_travel_times_from_schedule,
    estimate_base_travel_times,
    create_validation_report
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_schedule() -> List[BusSchedule]:
    """Schedule simple para testing."""
    return [
        BusSchedule(
            bus_id="B001",
            items=[
                ScheduleItem(
                    route_id="R1",
                    start_time=time(8, 0),
                    end_time=time(8, 30),
                    type="entry",
                    deadhead_minutes=0
                ),
                ScheduleItem(
                    route_id="R2",
                    start_time=time(9, 0),
                    end_time=time(9, 30),
                    type="exit",
                    deadhead_minutes=15
                )
            ]
        )
    ]


@pytest.fixture
def tight_schedule() -> List[BusSchedule]:
    """Schedule ajustado con poco margen."""
    return [
        BusSchedule(
            bus_id="B001",
            items=[
                ScheduleItem(
                    route_id="R1",
                    start_time=time(8, 0),
                    end_time=time(8, 30),
                    type="entry",
                    deadhead_minutes=0
                ),
                ScheduleItem(
                    route_id="R2",
                    start_time=time(8, 35),  # Solo 5 min de margen
                    end_time=time(9, 5),
                    type="exit",
                    deadhead_minutes=5
                )
            ]
        )
    ]


@pytest.fixture
def robust_schedule() -> List[BusSchedule]:
    """Schedule robusto con mucho margen."""
    return [
        BusSchedule(
            bus_id="B001",
            items=[
                ScheduleItem(
                    route_id="R1",
                    start_time=time(8, 0),
                    end_time=time(8, 30),
                    type="entry",
                    deadhead_minutes=0
                ),
                ScheduleItem(
                    route_id="R2",
                    start_time=time(9, 30),  # 60 min de margen
                    end_time=time(10, 0),
                    type="exit",
                    deadhead_minutes=15
                )
            ]
        )
    ]


@pytest.fixture
def base_travel_times() -> Dict[Tuple[str, str], float]:
    """Tiempos base de viaje."""
    return {
        ("R1", "R2"): 15.0,
        ("R2", "R3"): 20.0
    }


@pytest.fixture
def sample_routes() -> List[Route]:
    """Rutas de ejemplo."""
    return [
        Route(
            id="R1",
            name="Route 1",
            stops=[
                Stop(name="S1", lat=42.24, lon=-8.72, order=1, time_from_start=0, passengers=5),
                Stop(name="S2", lat=42.25, lon=-8.73, order=2, time_from_start=15, passengers=5, is_school=True)
            ],
            school_id="SCH1",
            school_name="School 1",
            arrival_time=time(8, 30),
            capacity_needed=10,
            contract_id="C1",
            type="entry"
        ),
        Route(
            id="R2",
            name="Route 2",
            stops=[
                Stop(name="S3", lat=42.26, lon=-8.74, order=1, time_from_start=0, passengers=8),
                Stop(name="S4", lat=42.27, lon=-8.75, order=2, time_from_start=20, passengers=8, is_school=True)
            ],
            school_id="SCH2",
            school_name="School 2",
            departure_time=time(14, 30),
            capacity_needed=16,
            contract_id="C2",
            type="exit"
        )
    ]


# =============================================================================
# Tests MonteCarloValidator
# =============================================================================

class TestMonteCarloValidator:
    """Tests para MonteCarloValidator."""
    
    def test_validator_initialization(self):
        """Test inicialización del validador."""
        validator = MonteCarloValidator(n_simulations=100, time_uncertainty=0.15)
        
        assert validator.n_simulations == 100
        assert validator.time_uncertainty == 0.15
        assert validator.distribution == "lognormal"
    
    def test_validator_with_seed(self):
        """Test que seed hace resultados reproducibles."""
        validator1 = MonteCarloValidator(n_simulations=50, seed=42)
        validator2 = MonteCarloValidator(n_simulations=50, seed=42)
        
        base_times = {("R1", "R2"): 15.0}
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(route_id="R1", start_time=time(8, 0), end_time=time(8, 30), type="entry"),
                    ScheduleItem(route_id="R2", start_time=time(9, 0), end_time=time(9, 30), type="exit", deadhead_minutes=15)
                ]
            )
        ]
        
        result1 = validator1.validate_schedule(schedule, base_times)
        result2 = validator2.validate_schedule(schedule, base_times)
        
        assert result1.feasibility_rate == result2.feasibility_rate
        assert result1.avg_violations == result2.avg_violations
    
    def test_validator_creates_simulation_result(self, sample_schedule, base_travel_times):
        """Test que el validador retorna SimulationResult."""
        validator = MonteCarloValidator(n_simulations=50)
        
        result = validator.validate_schedule(sample_schedule, base_travel_times)
        
        assert isinstance(result, SimulationResult)
        assert 0 <= result.feasibility_rate <= 1
        assert result.avg_violations >= 0
        assert result.worst_case_violations >= 0
    
    def test_robust_schedule_high_feasibility(self, robust_schedule, base_travel_times):
        """Test que schedule robusto tiene alta factibilidad."""
        validator = MonteCarloValidator(n_simulations=100, time_uncertainty=0.2, seed=42)
        
        result = validator.validate_schedule(robust_schedule, base_travel_times)
        
        # Schedule con 60 min de margen debería ser muy robusto
        assert result.feasibility_rate >= 0.95
        assert result.avg_violations < 0.1
    
    def test_tight_schedule_low_feasibility(self, tight_schedule, base_travel_times):
        """Test que schedule ajustado tiene baja factibilidad."""
        validator = MonteCarloValidator(n_simulations=100, time_uncertainty=0.3, seed=42)
        
        result = validator.validate_schedule(tight_schedule, base_travel_times)
        
        # Schedule con 5 min de margen debería tener problemas con 30% uncertainty
        assert result.feasibility_rate < 0.9
    
    def test_simulation_result_to_dict(self, sample_schedule, base_travel_times):
        """Test conversión a dict."""
        validator = MonteCarloValidator(n_simulations=50)
        result = validator.validate_schedule(sample_schedule, base_travel_times)
        
        data = result.to_dict()
        
        assert "feasibility_rate" in data
        assert "feasibility_rate_pct" in data
        assert "confidence_interval_95" in data
        assert "violation_distribution" in data
    
    def test_get_robustness_grade(self):
        """Test grados de robustez."""
        validator = MonteCarloValidator()
        
        # Crear results simulados
        result_a = SimulationResult(
            schedule=[], feasibility_rate=0.97, avg_violations=0.1,
            worst_case_violations=1, confidence_interval=(0, 0.2),
            violation_distribution={}
        )
        result_b = SimulationResult(
            schedule=[], feasibility_rate=0.90, avg_violations=0.5,
            worst_case_violations=2, confidence_interval=(0, 0.5),
            violation_distribution={}
        )
        result_f = SimulationResult(
            schedule=[], feasibility_rate=0.40, avg_violations=5.0,
            worst_case_violations=10, confidence_interval=(4, 6),
            violation_distribution={}
        )
        
        assert validator.get_robustness_grade(result_a) == 'A'
        assert validator.get_robustness_grade(result_b) == 'B'
        assert validator.get_robustness_grade(result_f) == 'F'
    
    def test_get_recommendation(self):
        """Test recomendaciones basadas en grado."""
        validator = MonteCarloValidator()
        
        result_a = SimulationResult(
            schedule=[], feasibility_rate=0.97, avg_violations=0.1,
            worst_case_violations=1, confidence_interval=(0, 0.2),
            violation_distribution={}
        )
        
        rec = validator.get_recommendation(result_a)
        assert "ACEPTAR" in rec
    
    def test_validate_multiple_scenarios(self, sample_schedule, base_travel_times):
        """Test validación contra múltiples escenarios."""
        validator = MonteCarloValidator(n_simulations=50)
        
        scenarios = [
            {"uncertainty": 0.1, "distribution": "lognormal"},
            {"uncertainty": 0.3, "distribution": "lognormal"}
        ]
        
        results = validator.validate_schedule_with_scenarios(
            sample_schedule, base_travel_times, scenarios
        )
        
        assert len(results) == 2
        # Mayor uncertainty debería dar menor factibilidad
        assert results[0].feasibility_rate >= results[1].feasibility_rate


# =============================================================================
# Tests check_schedule_feasibility
# =============================================================================

class TestCheckScheduleFeasibility:
    """Tests para función check_schedule_feasibility."""
    
    def test_feasible_schedule(self, sample_schedule):
        """Test schedule factible."""
        travel_times = {("R1", "R2"): 20.0}  # 30 min entre rutas, 20 min travel
        
        is_feasible, violations = check_schedule_feasibility(sample_schedule, travel_times)
        
        assert is_feasible is True
        assert violations == 0
    
    def test_infeasible_schedule(self, sample_schedule):
        """Test schedule no factible."""
        travel_times = {("R1", "R2"): 40.0}  # Solo 30 min entre rutas, 40 min travel
        
        is_feasible, violations = check_schedule_feasibility(sample_schedule, travel_times)
        
        assert is_feasible is False
        assert violations == 1
    
    def test_missing_travel_time_uses_default(self):
        """Test que usa default cuando no hay tiempo definido."""
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(route_id="R1", start_time=time(8, 0), end_time=time(8, 30), type="entry"),
                    ScheduleItem(route_id="R2", start_time=time(8, 35), end_time=time(9, 0), type="exit")
                ]
            )
        ]
        travel_times = {}  # Sin tiempos definidos
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        # Default es 15 min, solo hay 5 min de margen
        assert is_feasible is False
    
    def test_multiple_buses(self):
        """Test schedule con múltiples buses."""
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(route_id="R1", start_time=time(8, 0), end_time=time(8, 30), type="entry"),
                    ScheduleItem(route_id="R2", start_time=time(9, 0), end_time=time(9, 30), type="exit", deadhead_minutes=15)
                ]
            ),
            BusSchedule(
                bus_id="B002",
                items=[
                    ScheduleItem(route_id="R3", start_time=time(10, 0), end_time=time(10, 30), type="entry"),
                    ScheduleItem(route_id="R4", start_time=time(11, 0), end_time=time(11, 30), type="exit", deadhead_minutes=15)
                ]
            )
        ]
        travel_times = {
            ("R1", "R2"): 15.0,
            ("R3", "R4"): 20.0
        }
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        assert is_feasible is True
        assert violations == 0


# =============================================================================
# Tests extract_travel_times_from_schedule
# =============================================================================

class TestExtractTravelTimes:
    """Tests para extracción de tiempos."""
    
    def test_extract_from_schedule(self, sample_schedule):
        """Test extracción de tiempos."""
        times = extract_travel_times_from_schedule(sample_schedule)
        
        assert ("R1", "R2") in times
        assert times[("R1", "R2")] > 0
    
    def test_extract_empty_schedule(self):
        """Test extracción de schedule vacío."""
        times = extract_travel_times_from_schedule([])
        assert times == {}
    
    def test_extract_uses_default(self):
        """Test que usa default cuando deadhead es 0."""
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(route_id="R1", start_time=time(8, 0), end_time=time(8, 30), type="entry", deadhead_minutes=0),
                    ScheduleItem(route_id="R2", start_time=time(9, 0), end_time=time(9, 30), type="exit", deadhead_minutes=0)
                ]
            )
        ]
        times = extract_travel_times_from_schedule(schedule, default_time=20.0)
        
        assert times[("R1", "R2")] == 20.0


# =============================================================================
# Tests estimate_base_travel_times
# =============================================================================

class TestEstimateBaseTravelTimes:
    """Tests para estimación de tiempos base."""
    
    def test_estimate_from_routes(self, sample_routes):
        """Test estimación desde rutas."""
        times = estimate_base_travel_times(sample_routes)
        
        # Debería haber tiempos entre rutas
        assert len(times) > 0
        assert ("R1", "R2") in times or ("R2", "R1") in times
    
    def test_estimate_empty_routes(self):
        """Test estimación con rutas vacías."""
        times = estimate_base_travel_times([])
        assert times == {}
    
    def test_estimate_with_osrm_provider(self, sample_routes):
        """Test estimación con provider OSRM."""
        def mock_osrm(lat1, lon1, lat2, lon2):
            return 25.0  # Siempre 25 minutos
        
        times = estimate_base_travel_times(sample_routes, osrm_provider=mock_osrm)
        
        # Los tiempos deberían ser 25 + buffer
        for key, value in times.items():
            assert value >= 25.0


# =============================================================================
# Tests create_validation_report
# =============================================================================

class TestCreateValidationReport:
    """Tests para creación de reportes."""
    
    def test_create_report_structure(self, sample_routes):
        """Test estructura del reporte."""
        # Crear schedule simple
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(route_id="R1", start_time=time(8, 0), end_time=time(8, 30), type="entry"),
                    ScheduleItem(route_id="R2", start_time=time(9, 0), end_time=time(9, 30), type="exit", deadhead_minutes=20)
                ]
            )
        ]
        
        report = create_validation_report(
            schedule=schedule,
            routes=sample_routes,
            n_simulations=50,
            uncertainty_levels=[0.1, 0.2]
        )
        
        assert "summary" in report
        assert "standard_result" in report
        assert "scenario_analysis" in report
        assert "timestamp" in report
        
        assert report["summary"]["n_buses"] == 1
        assert len(report["scenario_analysis"]) == 2
    
    def test_report_has_grade(self, sample_routes):
        """Test que reporte incluye grado."""
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(route_id="R1", start_time=time(8, 0), end_time=time(8, 30), type="entry"),
                    ScheduleItem(route_id="R2", start_time=time(10, 0), end_time=time(10, 30), type="exit", deadhead_minutes=20)
                ]
            )
        ]
        
        report = create_validation_report(
            schedule=schedule,
            routes=sample_routes,
            n_simulations=50
        )
        
        assert "overall_grade" in report["summary"]
        assert "overall_recommendation" in report["summary"]
        assert report["summary"]["overall_grade"] in ['A', 'B', 'C', 'D', 'F']


# =============================================================================
# Tests distribuciones
# =============================================================================

class TestDistributions:
    """Tests para diferentes distribuciones."""
    
    def test_lognormal_distribution(self, sample_schedule, base_travel_times):
        """Test distribución lognormal."""
        validator = MonteCarloValidator(
            n_simulations=100,
            distribution="lognormal",
            seed=42
        )
        
        result = validator.validate_schedule(sample_schedule, base_travel_times)
        assert 0 <= result.feasibility_rate <= 1
    
    def test_normal_distribution(self, sample_schedule, base_travel_times):
        """Test distribución normal."""
        validator = MonteCarloValidator(
            n_simulations=100,
            distribution="normal",
            seed=42
        )
        
        result = validator.validate_schedule(sample_schedule, base_travel_times)
        assert 0 <= result.feasibility_rate <= 1
    
    def test_uniform_distribution(self, sample_schedule, base_travel_times):
        """Test distribución uniforme."""
        validator = MonteCarloValidator(
            n_simulations=100,
            distribution="uniform",
            seed=42
        )
        
        result = validator.validate_schedule(sample_schedule, base_travel_times)
        assert 0 <= result.feasibility_rate <= 1
    
    def test_invalid_distribution(self, sample_schedule, base_travel_times):
        """Test distribución inválida."""
        validator = MonteCarloValidator(
            n_simulations=10,
            distribution="invalid"
        )
        
        with pytest.raises(ValueError):
            validator.validate_schedule(sample_schedule, base_travel_times)
