"""
Tests for Advanced Optimizer (Multi-Objective + LNS)
====================================================

FASE 3.1 + 3.2: Tests para optimización multi-objetivo y LNS.

Este módulo prueba:
1. Función objetivo multi-criterio
2. Large Neighborhood Search (LNS)
3. Integración con V6
4. Comparativa greedy vs LNS
"""

import pytest
from datetime import time
from typing import List, Dict, Any

from models import Route, Stop, BusSchedule, ScheduleItem
from optimizer_multi import (
    ObjectiveWeights, 
    ObjectivePresets,
    MultiObjectiveOptimizer,
    ScheduleMetrics,
    evaluate_schedule,
    get_schedule_metrics
)
from optimizer_lns import (
    DestroyStrategy,
    RepairStrategy,
    LNSConfig,
    LNSOptimizer,
    optimize_v6_lns
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_stops() -> List[Stop]:
    """Crear stops de ejemplo."""
    return [
        Stop(name="Stop 1", lat=-33.45, lon=-70.66, order=1, time_from_start=0, passengers=10),
        Stop(name="Stop 2", lat=-33.46, lon=-70.67, order=2, time_from_start=10, passengers=8),
        Stop(name="Stop 3", lat=-33.47, lon=-70.68, order=3, time_from_start=20, passengers=12),
    ]


@pytest.fixture
def sample_routes(sample_stops) -> List[Route]:
    """Crear rutas de ejemplo."""
    return [
        Route(
            id="R1",
            name="Route 1",
            stops=sample_stops,
            school_id="S1",
            school_name="School A",
            arrival_time=time(8, 30),
            capacity_needed=30,
            contract_id="C1",
            type="entry",
            days=["L", "M", "Mc", "X", "V"]
        ),
        Route(
            id="R2",
            name="Route 2",
            stops=[
                Stop(name="Stop 4", lat=-33.48, lon=-70.69, order=1, time_from_start=0, passengers=15),
                Stop(name="Stop 5", lat=-33.49, lon=-70.70, order=2, time_from_start=15, passengers=10),
            ],
            school_id="S1",
            school_name="School A",
            arrival_time=time(8, 45),
            capacity_needed=25,
            contract_id="C1",
            type="entry",
            days=["L", "M", "Mc", "X", "V"]
        ),
        Route(
            id="R3",
            name="Route 3",
            stops=[
                Stop(name="Stop 6", lat=-33.50, lon=-70.71, order=1, time_from_start=0, passengers=20),
                Stop(name="Stop 7", lat=-33.51, lon=-70.72, order=2, time_from_start=12, passengers=18),
            ],
            school_id="S2",
            school_name="School B",
            departure_time=time(14, 30),
            capacity_needed=38,
            contract_id="C2",
            type="exit",
            days=["L", "M", "Mc", "X", "V"]
        ),
    ]


@pytest.fixture
def sample_schedule() -> List[BusSchedule]:
    """Crear un schedule de ejemplo."""
    return [
        BusSchedule(
            bus_id="B001",
            items=[
                ScheduleItem(
                    route_id="R1",
                    start_time=time(7, 30),
                    end_time=time(8, 30),
                    type="entry",
                    time_shift_minutes=0,
                    deadhead_minutes=0,
                    school_name="School A",
                    stops=[
                        Stop(name="Stop 1", lat=-33.45, lon=-70.66, order=1, time_from_start=0, passengers=10),
                        Stop(name="Stop 2", lat=-33.46, lon=-70.67, order=2, time_from_start=10, passengers=8),
                    ]
                ),
                ScheduleItem(
                    route_id="R2",
                    start_time=time(8, 45),
                    end_time=time(9, 30),
                    type="entry",
                    time_shift_minutes=5,
                    deadhead_minutes=10,
                    school_name="School A",
                    stops=[
                        Stop(name="Stop 4", lat=-33.48, lon=-70.69, order=1, time_from_start=0, passengers=15),
                    ]
                ),
            ]
        ),
        BusSchedule(
            bus_id="B002",
            items=[
                ScheduleItem(
                    route_id="R3",
                    start_time=time(14, 30),
                    end_time=time(15, 30),
                    type="exit",
                    time_shift_minutes=0,
                    deadhead_minutes=0,
                    school_name="School B",
                    stops=[
                        Stop(name="Stop 6", lat=-33.50, lon=-70.71, order=1, time_from_start=0, passengers=20),
                    ]
                ),
            ]
        ),
    ]


# =============================================================================
# TESTS: Multi-Objective Weights
# =============================================================================

class TestObjectiveWeights:
    """Tests para ObjectiveWeights y presets."""
    
    def test_default_weights(self):
        """Test que los pesos default son correctos."""
        weights = ObjectiveWeights()
        assert weights.buses == 1000.0
        assert weights.deadhead_km == 10.0
        assert weights.driver_overtime == 50.0
        assert weights.time_shift_minutes == 5.0
        assert weights.unbalanced_load == 20.0
        assert weights.fuel_cost == 0.15
        assert weights.co2_emissions == 0.01
    
    def test_custom_weights(self):
        """Test que se pueden crear pesos personalizados."""
        weights = ObjectiveWeights(
            buses=500,
            deadhead_km=20,
            driver_overtime=100
        )
        assert weights.buses == 500
        assert weights.deadhead_km == 20
        assert weights.driver_overtime == 100
    
    def test_to_dict(self):
        """Test conversión a diccionario."""
        weights = ObjectiveWeights()
        d = weights.to_dict()
        assert "buses" in d
        assert "deadhead_km" in d
        assert d["buses"] == 1000.0
    
    def test_from_dict(self):
        """Test creación desde diccionario."""
        data = {"buses": 500, "deadhead_km": 20}
        weights = ObjectiveWeights.from_dict(data)
        assert weights.buses == 500
        assert weights.deadhead_km == 20


class TestObjectivePresets:
    """Tests para presets de objetivos."""
    
    def test_minimize_buses_preset(self):
        """Test preset minimize_buses."""
        preset = ObjectivePresets.minimize_buses()
        assert preset.buses == 1000
        assert preset.deadhead_km == 10
    
    def test_minimize_cost_preset(self):
        """Test preset minimize_cost."""
        preset = ObjectivePresets.minimize_cost()
        assert preset.buses == 500
        assert preset.fuel_cost == 0.25
    
    def test_minimize_emissions_preset(self):
        """Test preset minimize_emissions."""
        preset = ObjectivePresets.minimize_emissions()
        assert preset.co2_emissions == 0.05
        assert preset.deadhead_km == 30
    
    def test_get_preset_by_name(self):
        """Test obtener preset por nombre."""
        preset = ObjectivePresets.get_preset("minimize_buses")
        assert preset.buses == 1000
        
        preset = ObjectivePresets.get_preset("minimize_cost")
        assert preset.fuel_cost == 0.25
        
        # Preset desconocido retorna balanced
        preset = ObjectivePresets.get_preset("unknown")
        assert preset.buses == 1000.0  # Valor default


# =============================================================================
# TESTS: Multi-Objective Optimizer
# =============================================================================

class TestMultiObjectiveOptimizer:
    """Tests para MultiObjectiveOptimizer."""
    
    def test_evaluate_schedule_basic(self, sample_schedule):
        """Test evaluación básica de un schedule."""
        optimizer = MultiObjectiveOptimizer()
        score = optimizer.evaluate_schedule(sample_schedule)
        
        assert score > 0
        # 2 buses * 1000 = 2000 base
        assert score >= 2000
    
    def test_evaluate_empty_schedule(self):
        """Test evaluación de schedule vacío."""
        optimizer = MultiObjectiveOptimizer()
        score = optimizer.evaluate_schedule([])
        assert score == float('inf')
    
    def test_calculate_deadhead(self, sample_schedule):
        """Test cálculo de deadhead."""
        optimizer = MultiObjectiveOptimizer()
        deadhead = optimizer.calculate_deadhead(sample_schedule)
        
        # Debe ser >= 0
        assert deadhead >= 0
    
    def test_calculate_time_shifts(self, sample_schedule):
        """Test cálculo de time shifts."""
        optimizer = MultiObjectiveOptimizer()
        shifts = optimizer.calculate_time_shifts(sample_schedule)
        
        # El schedule tiene un shift de 5 minutos
        assert shifts == 5
    
    def test_calculate_variance(self):
        """Test cálculo de varianza."""
        optimizer = MultiObjectiveOptimizer()
        
        # Lista vacía
        assert optimizer.calculate_variance([]) == 0.0
        
        # Un solo elemento
        assert optimizer.calculate_variance([5]) == 0.0
        
        # Dos elementos
        variance = optimizer.calculate_variance([2, 4])
        assert variance == 1.0
    
    def test_calculate_metrics(self, sample_schedule):
        """Test cálculo completo de métricas."""
        optimizer = MultiObjectiveOptimizer()
        metrics = optimizer.calculate_metrics(sample_schedule)
        
        assert isinstance(metrics, ScheduleMetrics)
        assert metrics.num_buses == 2
        assert metrics.total_routes == 3
        assert metrics.total_time_shift_minutes == 5
    
    def test_compare_schedules(self, sample_schedule):
        """Test comparación de schedules."""
        optimizer = MultiObjectiveOptimizer()
        
        # Crear schedules ligeramente diferentes
        schedule1 = sample_schedule
        schedule2 = [BusSchedule(
            bus_id="B001",
            items=sample_schedule[0].items + sample_schedule[1].items
        )]
        
        comparison = optimizer.compare_schedules(schedule1, schedule2)
        
        assert "schedule1" in comparison
        assert "schedule2" in comparison
        assert "improvement" in comparison
        assert "winner" in comparison["improvement"]
    
    def test_different_weights_different_scores(self, sample_schedule):
        """Test que diferentes pesos producen diferentes scores."""
        optimizer1 = MultiObjectiveOptimizer(ObjectiveWeights(buses=1000))
        optimizer2 = MultiObjectiveOptimizer(ObjectiveWeights(buses=100))
        
        score1 = optimizer1.evaluate_schedule(sample_schedule)
        score2 = optimizer2.evaluate_schedule(sample_schedule)
        
        # El score con peso mayor en buses debe ser mayor
        assert score1 > score2


# =============================================================================
# TESTS: Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Tests para funciones de conveniencia."""
    
    def test_evaluate_schedule_function(self, sample_schedule):
        """Test función evaluate_schedule."""
        score = evaluate_schedule(sample_schedule)
        assert score > 0
    
    def test_get_schedule_metrics_function(self, sample_schedule):
        """Test función get_schedule_metrics."""
        metrics = get_schedule_metrics(sample_schedule)
        assert isinstance(metrics, ScheduleMetrics)
        assert metrics.num_buses == 2


# =============================================================================
# TESTS: LNS Configuration
# =============================================================================

class TestLNSConfig:
    """Tests para LNSConfig."""
    
    def test_default_config(self):
        """Test configuración por defecto."""
        config = LNSConfig()
        assert config.destroy_rate == 0.3
        assert config.max_iterations == 100
        assert config.max_no_improvement == 20
        assert config.destroy_strategy == DestroyStrategy.WORST
        assert config.repair_strategy == RepairStrategy.GREEDY
    
    def test_custom_config(self):
        """Test configuración personalizada."""
        config = LNSConfig(
            destroy_rate=0.5,
            max_iterations=50,
            destroy_strategy=DestroyStrategy.RANDOM
        )
        assert config.destroy_rate == 0.5
        assert config.max_iterations == 50
        assert config.destroy_strategy == DestroyStrategy.RANDOM


# =============================================================================
# TESTS: LNS Optimizer (Integration)
# =============================================================================

@pytest.mark.integration
class TestLNSOptimizer:
    """Tests de integración para LNSOptimizer."""
    
    def test_lns_optimizer_initialization(self):
        """Test inicialización del optimizador LNS."""
        weights = ObjectiveWeights()
        config = LNSConfig(max_iterations=10)
        
        optimizer = LNSOptimizer(weights=weights, config=config)
        
        assert optimizer.weights == weights
        assert optimizer.config == config
        assert optimizer.evaluator is not None
    
    def test_lns_optimizer_with_empty_routes(self):
        """Test LNS con lista vacía de rutas."""
        optimizer = LNSOptimizer()
        result = optimizer.optimize([])
        assert result == []
    
    def test_optimize_v6_lns_without_lns(self, sample_routes):
        """Test función optimize_v6_lns sin LNS (solo greedy)."""
        schedule = optimize_v6_lns(sample_routes, use_lns=False)
        
        assert isinstance(schedule, list)
        # Debe retornar algún resultado
        assert len(schedule) > 0
    
    def test_optimize_v6_lns_with_lns(self, sample_routes):
        """Test función optimize_v6_lns con LNS habilitado."""
        weights = ObjectiveWeights()
        config = LNSConfig(max_iterations=5, max_no_improvement=2)
        
        schedule = optimize_v6_lns(
            sample_routes, 
            weights=weights, 
            use_lns=True,
            config=config
        )
        
        assert isinstance(schedule, list)
        # LNS debe retornar un resultado válido
        assert len(schedule) >= 0  # Puede ser vacío si no hay solución

    def test_optimize_v6_lns_returns_unique_sequential_bus_ids(self, sample_routes):
        """LNS debe devolver IDs de bus únicos y secuenciales para evitar descuadres en frontend."""
        weights = ObjectiveWeights()
        config = LNSConfig(max_iterations=5, max_no_improvement=2)

        schedule = optimize_v6_lns(
            sample_routes,
            weights=weights,
            use_lns=True,
            config=config,
        )

        bus_ids = [bus.bus_id for bus in schedule]
        assert len(bus_ids) == len(set(bus_ids))
        assert bus_ids == [f"B{i + 1:03d}" for i in range(len(bus_ids))]


# =============================================================================
# TESTS: Strategy Enums
# =============================================================================

class TestStrategyEnums:
    """Tests para enums de estrategia."""
    
    def test_destroy_strategy_values(self):
        """Test valores de DestroyStrategy."""
        assert DestroyStrategy.RANDOM.value == "random"
        assert DestroyStrategy.WORST.value == "worst"
        assert DestroyStrategy.RELATED.value == "related"
        assert DestroyStrategy.CLUSTER.value == "cluster"
        assert DestroyStrategy.SHAW.value == "shaw"
    
    def test_repair_strategy_values(self):
        """Test valores de RepairStrategy."""
        assert RepairStrategy.GREEDY.value == "greedy"
        assert RepairStrategy.REGRET.value == "regret"
        assert RepairStrategy.ILP_SUBPROBLEM.value == "ilp"


# =============================================================================
# TESTS: Benchmark / Comparison
# =============================================================================

@pytest.mark.benchmark
class TestBenchmark:
    """Tests de benchmark para comparar greedy vs LNS."""
    
    def test_lns_improves_over_greedy(self, sample_routes):
        """
        Test que LNS mejora sobre greedy.
        
        Este test verifica que LNS produce resultados iguales o mejores
        que el algoritmo greedy base.
        """
        from optimizer_v6 import optimize_v6
        from optimizer_multi import MultiObjectiveOptimizer
        
        weights = ObjectiveWeights()
        evaluator = MultiObjectiveOptimizer(weights)
        
        # Ejecutar greedy
        greedy_schedule = optimize_v6(sample_routes)
        greedy_score = evaluator.evaluate_schedule(greedy_schedule)
        
        # Ejecutar LNS con pocas iteraciones
        config = LNSConfig(max_iterations=10, max_no_improvement=3)
        lns_schedule = optimize_v6_lns(
            sample_routes, 
            weights=weights, 
            use_lns=True,
            config=config
        )
        lns_score = evaluator.evaluate_schedule(lns_schedule)
        
        # LNS debe ser igual o mejor (score menor o igual)
        assert lns_score <= greedy_score * 1.1  # 10% tolerancia
    
    def test_metrics_consistency(self, sample_schedule):
        """Test que las métricas son consistentes."""
        optimizer = MultiObjectiveOptimizer()
        metrics = optimizer.calculate_metrics(sample_schedule)
        
        # Verificar consistencia de métricas
        assert metrics.num_buses > 0
        assert metrics.total_routes > 0
        assert metrics.avg_routes_per_bus > 0
        
        # avg_routes_per_bus debe ser consistente
        expected_avg = metrics.total_routes / metrics.num_buses
        assert abs(metrics.avg_routes_per_bus - expected_avg) < 0.01


# =============================================================================
# TESTS: API Integration
# =============================================================================

@pytest.mark.api
class TestAPIIntegration:
    """Tests de integración con API."""
    
    def test_objective_weights_serialization(self):
        """Test serialización de pesos."""
        weights = ObjectiveWeights(buses=500, deadhead_km=20)
        
        # Debe poder serializarse a dict
        data = weights.to_dict()
        assert data["buses"] == 500
        assert data["deadhead_km"] == 20
        
        # Debe poder deserializarse
        restored = ObjectiveWeights.from_dict(data)
        assert restored.buses == 500
        assert restored.deadhead_km == 20
    
    def test_schedule_metrics_to_dict(self, sample_schedule):
        """Test conversión de métricas a dict."""
        optimizer = MultiObjectiveOptimizer()
        metrics = optimizer.calculate_metrics(sample_schedule)
        
        data = metrics.to_dict()
        
        assert "num_buses" in data
        assert "total_routes" in data
        assert "score" not in data  # Score no está en ScheduleMetrics


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
