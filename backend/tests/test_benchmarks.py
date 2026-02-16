"""
Tests para sistema de benchmarks.
"""

import pytest
import json
import time
from datetime import time as dt_time
from pathlib import Path
from typing import List

from models import Route, BusSchedule, ScheduleItem, Stop
from benchmarks import BenchmarkSuite, BenchmarkResult
from benchmarks.metrics import (
    EfficiencyMetrics,
    RobustnessMetrics,
    calculate_efficiency_metrics,
    calculate_robustness_metrics,
    calculate_multi_objective_score,
    compare_schedules
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
                    start_time=dt_time(8, 0),
                    end_time=dt_time(8, 30),
                    type="entry",
                    deadhead_minutes=0
                ),
                ScheduleItem(
                    route_id="R2",
                    start_time=dt_time(9, 0),
                    end_time=dt_time(9, 30),
                    type="exit",
                    deadhead_minutes=15
                )
            ]
        ),
        BusSchedule(
            bus_id="B002",
            items=[
                ScheduleItem(
                    route_id="R3",
                    start_time=dt_time(10, 0),
                    end_time=dt_time(10, 30),
                    type="entry",
                    deadhead_minutes=0
                )
            ]
        )
    ]


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
            arrival_time=dt_time(8, 30),
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
            departure_time=dt_time(14, 30),
            capacity_needed=16,
            contract_id="C2",
            type="exit"
        ),
        Route(
            id="R3",
            name="Route 3",
            stops=[
                Stop(name="S5", lat=42.28, lon=-8.76, order=1, time_from_start=0, passengers=6),
                Stop(name="S6", lat=42.29, lon=-8.77, order=2, time_from_start=18, passengers=6, is_school=True)
            ],
            school_id="SCH1",
            school_name="School 1",
            arrival_time=dt_time(10, 30),
            capacity_needed=12,
            contract_id="C1",
            type="entry"
        )
    ]


@pytest.fixture
def mock_algorithm():
    """Algoritmo mock para testing."""
    def algorithm(routes: List[Route]) -> List[BusSchedule]:
        time.sleep(0.01)  # Simular trabajo
        return [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id=r.id,
                        start_time=dt_time(8, 0),
                        end_time=dt_time(8, 30),
                        type=r.type,
                        deadhead_minutes=10
                    )
                    for r in routes[:2]
                ]
            )
        ]
    return algorithm


@pytest.fixture
def benchmark_suite(tmp_path):
    """Suite de benchmarks con directorio temporal."""
    return BenchmarkSuite(output_dir=str(tmp_path / "benchmarks"))


# =============================================================================
# Tests BenchmarkSuite
# =============================================================================

class TestBenchmarkSuite:
    """Tests para BenchmarkSuite."""
    
    def test_suite_initialization(self, tmp_path):
        """Test inicialización de suite."""
        suite = BenchmarkSuite(output_dir=str(tmp_path / "bench"))
        
        assert suite.output_dir == tmp_path / "bench"
        assert suite.results == []
        assert (tmp_path / "bench").exists()
    
    def test_run_benchmark(self, benchmark_suite, mock_algorithm, sample_routes):
        """Test ejecución de benchmark."""
        result = benchmark_suite.run_benchmark(
            algorithm=mock_algorithm,
            algorithm_name="mock_algo",
            dataset=sample_routes,
            dataset_name="test_dataset",
            n_runs=3,
            validate_robustness=False
        )
        
        assert isinstance(result, BenchmarkResult)
        assert result.algorithm == "mock_algo"
        assert result.dataset == "test_dataset"
        assert result.n_routes == len(sample_routes)
        assert result.n_buses > 0
        assert result.execution_time_ms > 0
        assert "n_runs" in result.metadata
    
    def test_run_benchmark_with_evaluator(self, benchmark_suite, mock_algorithm, sample_routes):
        """Test benchmark con evaluador custom."""
        def custom_evaluator(schedule, routes):
            return len(schedule) * 100
        
        result = benchmark_suite.run_benchmark(
            algorithm=mock_algorithm,
            algorithm_name="mock_algo",
            dataset=sample_routes,
            dataset_name="test_dataset",
            evaluator=custom_evaluator,
            n_runs=2,
            validate_robustness=False
        )
        
        assert result.objective_score > 0
    
    def test_run_benchmark_multiple_runs(self, benchmark_suite, mock_algorithm, sample_routes):
        """Test benchmark con múltiples runs."""
        result = benchmark_suite.run_benchmark(
            algorithm=mock_algorithm,
            algorithm_name="mock_algo",
            dataset=sample_routes,
            dataset_name="test_dataset",
            n_runs=5,
            validate_robustness=False
        )
        
        assert result.metadata["n_runs"] == 5
        assert "time_std" in result.metadata
        assert "time_min" in result.metadata
        assert "time_max" in result.metadata
    
    def test_run_benchmark_adds_to_results(self, benchmark_suite, mock_algorithm, sample_routes):
        """Test que benchmark agrega resultado a lista."""
        initial_count = len(benchmark_suite.results)
        
        benchmark_suite.run_benchmark(
            algorithm=mock_algorithm,
            algorithm_name="mock_algo",
            dataset=sample_routes,
            dataset_name="test_dataset",
            n_runs=2,
            validate_robustness=False
        )
        
        assert len(benchmark_suite.results) == initial_count + 1
    
    def test_run_benchmark_error_handling(self, benchmark_suite, sample_routes):
        """Test manejo de errores en benchmark."""
        def failing_algorithm(routes):
            raise ValueError("Algorithm failed")
        
        with pytest.raises(RuntimeError):
            benchmark_suite.run_benchmark(
                algorithm=failing_algorithm,
                algorithm_name="failing_algo",
                dataset=sample_routes,
                dataset_name="test_dataset",
                n_runs=2,
                validate_robustness=False
            )


# =============================================================================
# Tests compare_algorithms
# =============================================================================

class TestCompareAlgorithms:
    """Tests para comparación de algoritmos."""
    
    def test_compare_two_algorithms(self):
        """Test comparación básica."""
        results = [
            BenchmarkResult(
                algorithm="algo_a",
                dataset="test",
                n_routes=10,
                execution_time_ms=100,
                n_buses=5,
                total_km=100,
                deadhead_km=20,
                avg_routes_per_bus=2,
                objective_score=500
            ),
            BenchmarkResult(
                algorithm="algo_b",
                dataset="test",
                n_routes=10,
                execution_time_ms=150,
                n_buses=4,
                total_km=90,
                deadhead_km=15,
                avg_routes_per_bus=2.5,
                objective_score=400
            )
        ]
        
        suite = BenchmarkSuite()
        comparison = suite.compare_algorithms(results)
        
        assert comparison["baseline"] == "algo_a"
        assert len(comparison["comparisons"]) == 1
        assert comparison["comparisons"][0]["algorithm"] == "algo_b"
    
    def test_compare_shows_improvements(self):
        """Test que muestra mejoras porcentuales."""
        results = [
            BenchmarkResult(
                algorithm="baseline",
                dataset="test",
                n_routes=10,
                execution_time_ms=100,
                n_buses=10,
                total_km=100,
                deadhead_km=20,
                avg_routes_per_bus=1,
                objective_score=1000
            ),
            BenchmarkResult(
                algorithm="improved",
                dataset="test",
                n_routes=10,
                execution_time_ms=100,
                n_buses=8,
                total_km=80,
                deadhead_km=15,
                avg_routes_per_bus=1.25,
                objective_score=800
            )
        ]
        
        suite = BenchmarkSuite()
        comparison = suite.compare_algorithms(results)
        
        vs_baseline = comparison["comparisons"][0]["vs_baseline"]
        assert "buses" in vs_baseline
        assert "buses_saved" in vs_baseline
        assert vs_baseline["buses_saved"] == 2
    
    def test_compare_empty_results(self):
        """Test comparación con resultados vacíos."""
        suite = BenchmarkSuite()
        comparison = suite.compare_algorithms([])
        
        assert comparison == {}


# =============================================================================
# Tests save/load results
# =============================================================================

class TestSaveLoadResults:
    """Tests para guardar y cargar resultados."""
    
    def test_save_results(self, benchmark_suite):
        """Test guardar resultados."""
        benchmark_suite.results = [
            BenchmarkResult(
                algorithm="test_algo",
                dataset="test",
                n_routes=10,
                execution_time_ms=100,
                n_buses=5,
                total_km=100,
                deadhead_km=20,
                avg_routes_per_bus=2,
                objective_score=500
            )
        ]
        
        path = benchmark_suite.save_results("test_results.json")
        
        assert Path(path).exists()
        with open(path, "r") as f:
            data = json.load(f)
        
        assert "results" in data
        assert len(data["results"]) == 1
    
    def test_generate_report(self, benchmark_suite):
        """Test generación de reporte."""
        benchmark_suite.results = [
            BenchmarkResult(
                algorithm="algo_a",
                dataset="small",
                n_routes=10,
                execution_time_ms=100,
                n_buses=5,
                total_km=100,
                deadhead_km=20,
                avg_routes_per_bus=2,
                objective_score=500
            ),
            BenchmarkResult(
                algorithm="algo_b",
                dataset="small",
                n_routes=10,
                execution_time_ms=120,
                n_buses=4,
                total_km=90,
                deadhead_km=15,
                avg_routes_per_bus=2.5,
                objective_score=450
            )
        ]
        
        path = benchmark_suite.generate_report("test_report.json")
        
        assert Path(path).exists()
        with open(path, "r") as f:
            data = json.load(f)
        
        assert "summary" in data
        assert "results_by_dataset" in data
        assert "comparisons" in data
    
    def test_load_results(self, tmp_path):
        """Test cargar resultados."""
        # Crear archivo de prueba
        data = {
            "timestamp": "2024-01-01T00:00:00",
            "results": [
                {
                    "algorithm": "loaded_algo",
                    "dataset": "test",
                    "n_routes": 10,
                    "execution_time_ms": 100,
                    "n_buses": 5,
                    "total_km": 100,
                    "deadhead_km": 20,
                    "avg_routes_per_bus": 2,
                    "objective_score": 500,
                    "timestamp": "2024-01-01T00:00:00",
                    "metadata": {}
                }
            ]
        }
        
        output_dir = tmp_path / "benchmarks"
        output_dir.mkdir()
        with open(output_dir / "load_test.json", "w") as f:
            json.dump(data, f)
        
        suite = BenchmarkSuite(output_dir=str(output_dir))
        suite.load_results("load_test.json")
        
        assert len(suite.results) == 1
        assert suite.results[0].algorithm == "loaded_algo"


# =============================================================================
# Tests EfficiencyMetrics
# =============================================================================

class TestEfficiencyMetrics:
    """Tests para métricas de eficiencia."""
    
    def test_calculate_efficiency(self, sample_schedule, sample_routes):
        """Test cálculo de eficiencia."""
        metrics = calculate_efficiency_metrics(sample_schedule, sample_routes)
        
        assert isinstance(metrics, EfficiencyMetrics)
        assert metrics.avg_routes_per_bus > 0
        assert metrics.coverage_ratio > 0
    
    def test_efficiency_empty_schedule(self, sample_routes):
        """Test eficiencia con schedule vacío."""
        metrics = calculate_efficiency_metrics([], sample_routes)
        
        assert metrics.bus_utilization_rate == 0
        assert metrics.avg_routes_per_bus == 0
    
    def test_efficiency_to_dict(self, sample_schedule, sample_routes):
        """Test conversión a dict."""
        metrics = calculate_efficiency_metrics(sample_schedule, sample_routes)
        data = metrics.to_dict()
        
        assert "bus_utilization_rate" in data
        assert "bus_utilization_pct" in data
        assert "coverage_ratio" in data
        assert "coverage_pct" in data


# =============================================================================
# Tests RobustnessMetrics
# =============================================================================

class TestRobustnessMetrics:
    """Tests para métricas de robustez."""
    
    def test_calculate_robustness(self, sample_schedule):
        """Test cálculo de robustez."""
        metrics = calculate_robustness_metrics(sample_schedule)
        
        assert isinstance(metrics, RobustnessMetrics)
        assert metrics.max_chain_length > 0
    
    def test_robustness_critical_transitions(self):
        """Test detección de transiciones críticas."""
        # Schedule con buffer pequeño
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=dt_time(8, 0),
                        end_time=dt_time(8, 30),
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=dt_time(8, 33),  # Solo 3 min buffer
                        end_time=dt_time(9, 0),
                        type="exit"
                    )
                ]
            )
        ]
        
        metrics = calculate_robustness_metrics(schedule)
        
        assert metrics.min_buffer_time < 5
        assert metrics.critical_transitions > 0
    
    def test_robustness_to_dict(self, sample_schedule):
        """Test conversión a dict."""
        metrics = calculate_robustness_metrics(sample_schedule)
        data = metrics.to_dict()
        
        assert "min_buffer_time" in data
        assert "critical_transitions" in data
        assert "max_chain_length" in data


# =============================================================================
# Tests Multi-Objective Score
# =============================================================================

class TestMultiObjectiveScore:
    """Tests para score multi-objetivo."""
    
    def test_calculate_score(self, sample_schedule, sample_routes):
        """Test cálculo de score."""
        score = calculate_multi_objective_score(sample_schedule, sample_routes)
        
        assert score > 0
    
    def test_score_with_weights(self, sample_schedule, sample_routes):
        """Test score con pesos custom."""
        weights = {
            'w_buses': 2.0,
            'w_deadhead': 0.05,
            'w_robustness': 0.1,
            'w_utilization': 0.1
        }
        
        score = calculate_multi_objective_score(sample_schedule, sample_routes, weights)
        
        assert score > 0
    
    def test_compare_schedules(self, sample_routes):
        """Test comparación de schedules."""
        schedule_a = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(route_id="R1", start_time=dt_time(8, 0), end_time=dt_time(8, 30), type="entry"),
                    ScheduleItem(route_id="R2", start_time=dt_time(9, 0), end_time=dt_time(9, 30), type="exit", deadhead_minutes=15)
                ]
            )
        ]
        
        schedule_b = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(route_id="R1", start_time=dt_time(8, 0), end_time=dt_time(8, 30), type="entry")
                ]
            ),
            BusSchedule(
                bus_id="B002",
                items=[
                    ScheduleItem(route_id="R2", start_time=dt_time(9, 0), end_time=dt_time(9, 30), type="exit", deadhead_minutes=15)
                ]
            )
        ]
        
        comparison = compare_schedules(schedule_a, schedule_b, sample_routes, "Algo A", "Algo B")
        
        assert "comparison" in comparison
        assert "winner" in comparison
        assert "score_difference" in comparison
        assert comparison["comparison"]["Algo A"]["buses"] == 1
        assert comparison["comparison"]["Algo B"]["buses"] == 2


# =============================================================================
# Tests BenchmarkResult
# =============================================================================

class TestBenchmarkResult:
    """Tests para clase BenchmarkResult."""
    
    def test_result_to_dict(self):
        """Test conversión a dict."""
        result = BenchmarkResult(
            algorithm="test",
            dataset="test_dataset",
            n_routes=10,
            execution_time_ms=100,
            n_buses=5,
            total_km=100,
            deadhead_km=20,
            avg_routes_per_bus=2,
            objective_score=500
        )
        
        data = result.to_dict()
        
        assert data["algorithm"] == "test"
        assert data["dataset"] == "test_dataset"
        assert data["n_buses"] == 5
    
    def test_result_repr(self):
        """Test representación string."""
        result = BenchmarkResult(
            algorithm="test_algo",
            dataset="test",
            n_routes=10,
            execution_time_ms=100.5,
            n_buses=5,
            total_km=100,
            deadhead_km=20,
            avg_routes_per_bus=2,
            objective_score=500.25
        )
        
        repr_str = repr(result)
        
        assert "test_algo" in repr_str
        assert "test" in repr_str
        assert "5 buses" in repr_str
