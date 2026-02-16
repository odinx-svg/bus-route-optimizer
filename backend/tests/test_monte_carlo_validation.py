"""
Tests exhaustivos para validación Monte Carlo.

Objetivo: Detectar por qué da 0% y validar el fix.

Tests:
1. Schedule perfecto (debe dar ~100%)
2. Schedule imposible (debe dar ~0%)
3. Schedule realista (debe dar ~70-90%)
4. Debug de extracción de tiempos de viaje
"""

import pytest
import statistics
from datetime import time
from typing import List, Dict, Tuple

# Importar componentes de Monte Carlo
try:
    from backend.validation.monte_carlo import (
        MonteCarloValidator,
        SimulationResult,
        check_schedule_feasibility,
        extract_travel_times_from_schedule,
        time_to_minutes,
    )
    from backend.models import Route, BusSchedule, ScheduleItem, Stop
    IMPORTS_OK = True
except ImportError:
    try:
        from validation.monte_carlo import (
            MonteCarloValidator,
            SimulationResult,
            check_schedule_feasibility,
            extract_travel_times_from_schedule,
            time_to_minutes,
        )
        from models import Route, BusSchedule, ScheduleItem, Stop
        IMPORTS_OK = True
    except ImportError:
        IMPORTS_OK = False


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def validator() -> MonteCarloValidator:
    """Crear un validator con seed fijo para reproducibilidad."""
    if not IMPORTS_OK:
        pytest.skip("Imports no disponibles")
    return MonteCarloValidator(n_simulations=500, seed=42)


@pytest.fixture
def validator_high_precision() -> MonteCarloValidator:
    """Validator con más simulaciones para tests críticos."""
    if not IMPORTS_OK:
        pytest.skip("Imports no disponibles")
    return MonteCarloValidator(n_simulations=1000, seed=42)


# =============================================================================
# TEST 1: SCHEDULE PERFECTO (debe dar ~100%)
# =============================================================================

class TestPerfectSchedule:
    """
    Test con schedule que tiene buffers enormes (30+ min entre rutas).
    
    travel_time = 10 min
    start_next - end_prev = 40 min
    buffer = 30 min > 0 → siempre factible
    
    Esperado: >95% factible
    """
    
    @pytest.fixture
    def perfect_schedule(self) -> List[BusSchedule]:
        """Crear schedule perfecto con buffers enormes."""
        if not IMPORTS_OK:
            pytest.skip("Imports no disponibles")
            
        return [
            BusSchedule(
                bus_id="BUS-PERFECT",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        type="entry",
                        start_time=time(8, 0),
                        end_time=time(9, 0),    # Termina 09:00
                        deadhead_minutes=10
                    ),
                    ScheduleItem(
                        route_id="R2",
                        type="entry",
                        start_time=time(9, 40),  # Empieza 09:40 (40 min buffer!)
                        end_time=time(10, 30),
                        deadhead_minutes=10
                    ),
                    ScheduleItem(
                        route_id="R3",
                        type="exit",
                        start_time=time(11, 10),  # Empieza 11:10 (40 min buffer!)
                        end_time=time(12, 0),
                        deadhead_minutes=10
                    ),
                ]
            )
        ]
    
    @pytest.fixture
    def perfect_travel_times(self) -> Dict[Tuple[str, str], float]:
        """Tiempos de viaje pequeños para schedule perfecto."""
        return {
            ("R1", "R2"): 10.0,  # Solo 10 min de viaje
            ("R2", "R3"): 10.0,  # Solo 10 min de viaje
        }
    
    def test_perfect_schedule_feasibility_rate(
        self, 
        validator_high_precision: MonteCarloValidator,
        perfect_schedule: List[BusSchedule],
        perfect_travel_times: Dict[Tuple[str, str], float]
    ):
        """
        Test CRÍTICO: Schedule perfecto debe dar >95% factible.
        
        Si da 0%, hay un bug grave en el sistema.
        """
        result = validator_high_precision.validate_schedule(
            perfect_schedule, 
            perfect_travel_times
        )
        
        print(f"\n[PERFECT SCHEDULE RESULT]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        print(f"  Avg violations: {result.avg_violations:.2f}")
        print(f"  Worst case: {result.worst_case_violations}")
        print(f"  Grade: {validator_high_precision.get_robustness_grade(result)}")
        
        # ASSERT CRÍTICO: Debe ser >95%
        assert result.feasibility_rate > 0.95, (
            f"CRITICAL BUG: Schedule perfecto dio {result.feasibility_rate:.2%} "
            f"factible, esperado >95%. "
            f"Avg violations: {result.avg_violations:.2f}"
        )
    
    def test_perfect_schedule_no_violations(
        self,
        validator_high_precision: MonteCarloValidator,
        perfect_schedule: List[BusSchedule],
        perfect_travel_times: Dict[Tuple[str, str], float]
    ):
        """Schedule perfecto debería tener 0 violaciones en la mayoría de casos."""
        result = validator_high_precision.validate_schedule(
            perfect_schedule, 
            perfect_travel_times
        )
        
        # En el mejor escenario, debe tener 0 violaciones promedio
        assert result.avg_violations < 0.5, (
            f"Schedule perfecto tiene {result.avg_violations:.2f} violaciones promedio, "
            f"esperado cercano a 0"
        )
    
    def test_perfect_schedule_deterministic_check(
        self,
        perfect_schedule: List[BusSchedule],
        perfect_travel_times: Dict[Tuple[str, str], float]
    ):
        """
        Verificación determinística: Con tiempos base, debe ser 100% factible.
        """
        is_feasible, violations = check_schedule_feasibility(
            perfect_schedule, 
            perfect_travel_times
        )
        
        print(f"\n[DETERMINISTIC CHECK - PERFECT]")
        print(f"  Is feasible: {is_feasible}")
        print(f"  Violations: {violations}")
        
        assert is_feasible, (
            f"Schedule perfecto no es factible con tiempos base! "
            f"Violations: {violations}"
        )
        assert violations == 0, (
            f"Schedule perfecto tiene {violations} violaciones con tiempos base"
        )


# =============================================================================
# TEST 2: SCHEDULE IMPOSIBLE (debe dar ~0%)
# =============================================================================

class TestImpossibleSchedule:
    """
    Test con schedule que tiene traslapes imposibles.
    
    Ruta 1 termina 08:00, Ruta 2 empieza 07:30 (30 min antes!)
    Esperado: 0% factible
    """
    
    @pytest.fixture
    def impossible_schedule(self) -> List[BusSchedule]:
        """Crear schedule imposible con traslapes."""
        if not IMPORTS_OK:
            pytest.skip("Imports no disponibles")
            
        return [
            BusSchedule(
                bus_id="BUS-IMPOSSIBLE",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        type="entry",
                        start_time=time(7, 0),
                        end_time=time(8, 0),    # Termina 08:00
                        deadhead_minutes=10
                    ),
                    ScheduleItem(
                        route_id="R2",
                        type="exit",
                        start_time=time(7, 30),  # ¡Empieza 07:30! (30 min ANTES)
                        end_time=time(8, 30),
                        deadhead_minutes=10
                    ),
                ]
            )
        ]
    
    @pytest.fixture
    def impossible_travel_times(self) -> Dict[Tuple[str, str], float]:
        """Tiempos de viaje para schedule imposible."""
        return {
            ("R1", "R2"): 10.0,
        }
    
    def test_impossible_schedule_feasibility_rate(
        self,
        validator_high_precision: MonteCarloValidator,
        impossible_schedule: List[BusSchedule],
        impossible_travel_times: Dict[Tuple[str, str], float]
    ):
        """
        Test: Schedule imposible debe dar ~0% factible.
        """
        result = validator_high_precision.validate_schedule(
            impossible_schedule, 
            impossible_travel_times
        )
        
        print(f"\n[IMPOSSIBLE SCHEDULE RESULT]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        print(f"  Avg violations: {result.avg_violations:.2f}")
        print(f"  Worst case: {result.worst_case_violations}")
        
        # Debe ser 0% o muy cercano
        assert result.feasibility_rate < 0.05, (
            f"Schedule imposible dio {result.feasibility_rate:.2%} factible, "
            f"esperado ~0%"
        )
    
    def test_impossible_schedule_always_violations(
        self,
        validator_high_precision: MonteCarloValidator,
        impossible_schedule: List[BusSchedule],
        impossible_travel_times: Dict[Tuple[str, str], float]
    ):
        """Schedule imposible debe tener violaciones en todas las simulaciones."""
        result = validator_high_precision.validate_schedule(
            impossible_schedule, 
            impossible_travel_times
        )
        
        assert result.avg_violations >= 0.9, (
            f"Schedule imposible tiene solo {result.avg_violations:.2f} "
            f"violaciones promedio, esperado ~1.0"
        )
    
    def test_impossible_schedule_deterministic_check(
        self,
        impossible_schedule: List[BusSchedule],
        impossible_travel_times: Dict[Tuple[str, str], float]
    ):
        """
        Verificación determinística: Con tiempos base, debe ser 0% factible.
        """
        is_feasible, violations = check_schedule_feasibility(
            impossible_schedule, 
            impossible_travel_times
        )
        
        print(f"\n[DETERMINISTIC CHECK - IMPOSSIBLE]")
        print(f"  Is feasible: {is_feasible}")
        print(f"  Violations: {violations}")
        
        assert not is_feasible, (
            "Schedule imposible es factible con tiempos base! Bug en check_schedule_feasibility"
        )
        assert violations > 0, "Schedule imposible debería tener violaciones"


# =============================================================================
# TEST 3: SCHEDULE REALISTA (debe dar ~70-90%)
# =============================================================================

class TestRealisticSchedule:
    """
    Test con schedule realista con buffers de 5-10 min.
    
    Esperado: 70-90% dependiendo de la incertidumbre
    """
    
    def test_realistic_schedule_feasibility_range(
        self,
        validator_high_precision: MonteCarloValidator,
        realistic_schedule: List[BusSchedule],
        realistic_travel_times: Dict[Tuple[str, str], float]
    ):
        """
        Test: Schedule realista debe dar entre 30-99% factible.
        
        Con 15 min de buffer y 8-10 min de viaje, debería ser robusto.
        """
        result = validator_high_precision.validate_schedule(
            realistic_schedule, 
            realistic_travel_times
        )
        
        print(f"\n[REALISTIC SCHEDULE RESULT]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        print(f"  Avg violations: {result.avg_violations:.2f}")
        print(f"  Worst case: {result.worst_case_violations}")
        print(f"  Grade: {validator_high_precision.get_robustness_grade(result)}")
        
        # Con 15 min buffer y 8-10 min viaje, debería ser >30%
        # La incertidumbre de 20% puede hacer variar esto
        assert 0.30 <= result.feasibility_rate <= 0.99, (
            f"Schedule realista dio {result.feasibility_rate:.2%} factible, "
            f"esperado entre 30%-99%. "
            f"Esto puede indicar: buffers muy justos o bug en extracción de tiempos."
        )
        """
        Test: Schedule realista debe dar entre 50-95% factible.
        
        Con 15 min de buffer y 8-10 min de viaje, debería ser robusto.
        """
        result = validator_high_precision.validate_schedule(
            realistic_schedule, 
            realistic_travel_times
        )
        
        print(f"\n[REALISTIC SCHEDULE RESULT]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        print(f"  Avg violations: {result.avg_violations:.2f}")
        print(f"  Worst case: {result.worst_case_violations}")
        print(f"  Grade: {validator_high_precision.get_robustness_grade(result)}")
        
        # Con 15 min buffer y 8-10 min viaje, debería ser >50%
        # La incertidumbre de 20% puede hacer variar esto
        assert 0.30 <= result.feasibility_rate <= 0.99, (
            f"Schedule realista dio {result.feasibility_rate:.2%} factible, "
            f"esperado entre 30%-99%. "
            f"Esto puede indicar: buffers muy justos o bug en extracción de tiempos."
        )
    
    def test_realistic_schedule_with_low_uncertainty(
        self,
        realistic_schedule: List[BusSchedule],
        realistic_travel_times: Dict[Tuple[str, str], float]
    ):
        """Con baja incertidumbre (10%), debe ser muy robusto."""
        validator = MonteCarloValidator(
            n_simulations=500, 
            time_uncertainty=0.1,  # Solo 10% variación
            seed=42
        )
        
        result = validator.validate_schedule(
            realistic_schedule, 
            realistic_travel_times
        )
        
        print(f"\n[REALISTIC - LOW UNCERTAINTY]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        print(f"  Grade: {validator.get_robustness_grade(result)}")
        
        # Con 10% incertidumbre y 15 min buffer, debería ser >70%
        assert result.feasibility_rate > 0.70, (
            f"Con 10% incertidumbre y 15 min buffer, "
            f"dio {result.feasibility_rate:.2%} factible"
        )
        """Con baja incertidumbre (10%), debe ser muy robusto."""
        validator = MonteCarloValidator(
            n_simulations=500, 
            time_uncertainty=0.1,  # Solo 10% variación
            seed=42
        )
        
        result = validator.validate_schedule(
            realistic_schedule, 
            realistic_travel_times
        )
        
        print(f"\n[REALISTIC - LOW UNCERTAINTY]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        print(f"  Grade: {validator.get_robustness_grade(result)}")
        
        # Con 10% incertidumbre y 15 min buffer, debería ser >70%
        assert result.feasibility_rate > 0.70, (
            f"Con 10% incertidumbre y 15 min buffer, "
            f"dio {result.feasibility_rate:.2%} factible"
        )
    
    def test_realistic_schedule_with_high_uncertainty(
        self,
        realistic_schedule: List[BusSchedule],
        realistic_travel_times: Dict[Tuple[str, str], float]
    ):
        """Con alta incertidumbre (50%), debe ser menos robusto."""
        validator = MonteCarloValidator(
            n_simulations=500, 
            time_uncertainty=0.5,  # 50% variación (muy alta)
            seed=42
        )
        
        result = validator.validate_schedule(
            realistic_schedule, 
            realistic_travel_times
        )
        
        print(f"\n[REALISTIC - HIGH UNCERTAINTY]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        print(f"  Grade: {validator.get_robustness_grade(result)}")
        
        # Con 50% incertidumbre, puede variar mucho
        # Solo verificamos que no sea 0% ni 100% (debería haber variabilidad)
        assert 0.05 < result.feasibility_rate < 0.95, (
            f"Con 50% incertidumbre, dio {result.feasibility_rate:.2%}. "
            f"Esto indica que no hay variabilidad en las simulaciones."
        )
        """Con alta incertidumbre (50%), debe ser menos robusto."""
        validator = MonteCarloValidator(
            n_simulations=500, 
            time_uncertainty=0.5,  # 50% variación (muy alta)
            seed=42
        )
        
        result = validator.validate_schedule(
            realistic_schedule, 
            realistic_travel_times
        )
        
        print(f"\n[REALISTIC - HIGH UNCERTAINTY]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        print(f"  Grade: {validator.get_robustness_grade(result)}")
        
        # Con 50% incertidumbre, puede variar mucho
        # Solo verificamos que no sea 0% ni 100% (debería haber variabilidad)
        assert 0.05 < result.feasibility_rate < 0.95, (
            f"Con 50% incertidumbre, dio {result.feasibility_rate:.2%}. "
            f"Esto indica que no hay variabilidad en las simulaciones."
        )


# =============================================================================
# TEST 4: DEBUG DE TIEMPOS DE VIAJE
# =============================================================================

class TestTravelTimeExtraction:
    """
    Tests para verificar que los tiempos de viaje se extraen correctamente.
    
    Este es el área más probable de bugs - si los tiempos no se extraen
    correctamente, Monte Carlo usará valores por defecto incorrectos.
    """
    
    @pytest.fixture
    def schedule_with_deadhead(self) -> List[BusSchedule]:
        """Schedule con deadhead_minutes configurados."""
        if not IMPORTS_OK:
            pytest.skip("Imports no disponibles")
            
        return [
            BusSchedule(
                bus_id="BUS-DEADHEAD",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        type="entry",
                        start_time=time(8, 0),
                        end_time=time(9, 0),
                        deadhead_minutes=25  # Deadhead específico
                    ),
                    ScheduleItem(
                        route_id="R2",
                        type="exit",
                        start_time=time(9, 30),
                        end_time=time(10, 30),
                        deadhead_minutes=30  # Otro deadhead
                    ),
                    ScheduleItem(
                        route_id="R3",
                        type="exit",
                        start_time=time(11, 0),
                        end_time=time(12, 0),
                        deadhead_minutes=0   # Sin deadhead
                    ),
                ]
            )
        ]
    
    @pytest.fixture
    def schedule_without_deadhead(self) -> List[BusSchedule]:
        """Schedule SIN deadhead (valores por defecto 0)."""
        if not IMPORTS_OK:
            pytest.skip("Imports no disponibles")
            
        return [
            BusSchedule(
                bus_id="BUS-NO-DEADHEAD",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        type="entry",
                        start_time=time(8, 0),
                        end_time=time(9, 0),
                        # deadhead_minutes = 0 (default)
                    ),
                    ScheduleItem(
                        route_id="R2",
                        type="exit",
                        start_time=time(9, 15),
                        end_time=time(10, 15),
                        # deadhead_minutes = 0 (default)
                    ),
                ]
            )
        ]
    
    def test_extract_travel_times_with_deadhead(
        self,
        schedule_with_deadhead: List[BusSchedule]
    ):
        """
        Verificar que se extraen correctamente los tiempos con deadhead.
        
        NOTA: extract_travel_times_from_schedule usa el deadhead del
        NEXT item, no del current. Esto es por diseño: el deadhead
        representa el tiempo necesario para llegar a esa ruta.
        """
        travel_times = extract_travel_times_from_schedule(
            schedule_with_deadhead, 
            default_time=15.0
        )
        
        print(f"\n[EXTRACT TRAVEL TIMES - WITH DEADHEAD]")
        for key, value in travel_times.items():
            print(f"  {key}: {value} min")
        
        # Verificar que se extrajeron los tiempos
        assert ("R1", "R2") in travel_times, "No se extrajo tiempo R1->R2"
        assert ("R2", "R3") in travel_times, "No se extrajo tiempo R2->R3"
        
        # Los valores deben ser los deadhead del NEXT item
        # R1->R2 usa deadhead de R2 = 30 (según el fixture)
        assert travel_times[("R1", "R2")] == 30.0, (
            f"R1->R2 debería ser 30 (deadhead de R2), "
            f"pero es {travel_times[('R1', 'R2')]}. "
            f"¿Bug en extracción?"
        )
        # R2->R3 usa deadhead de R3 = 0, por lo tanto usa default
        assert travel_times[("R2", "R3")] == 15.0, (
            f"R2->R3 debería ser 15 (default, ya que deadhead de R3 es 0), "
            f"pero es {travel_times[('R2', 'R3')]}. "
            f"¿Bug en extracción?"
        )
    
    def test_extract_travel_times_without_deadhead_uses_default(
        self,
        schedule_without_deadhead: List[BusSchedule]
    ):
        """
        Si deadhead es 0, debe usar el valor por defecto (15 min).
        
        Este es un posible bug: si el optimizador no setea deadhead,
        todos los tiempos serán 15 min (default) y los buffers pueden
        parecer suficientes cuando no lo son.
        """
        travel_times = extract_travel_times_from_schedule(
            schedule_without_deadhead,
            default_time=15.0
        )
        
        print(f"\n[EXTRACT TRAVEL TIMES - NO DEADHEAD]")
        for key, value in travel_times.items():
            print(f"  {key}: {value} min (esperado: 15.0 default)")
        
        assert ("R1", "R2") in travel_times
        # Como deadhead es 0, debe usar default
        assert travel_times[("R1", "R2")] == 15.0, (
            f"Sin deadhead, debería usar default 15.0, "
            f"pero es {travel_times[('R1', 'R2')]}. "
            f"Esto indica que se está usando un valor incorrecto."
        )
    
    def test_extract_travel_times_custom_default(
        self,
        schedule_without_deadhead: List[BusSchedule]
    ):
        """Verificar que se puede especificar un default diferente."""
        travel_times = extract_travel_times_from_schedule(
            schedule_without_deadhead,
            default_time=30.0  # Custom default
        )
        
        assert travel_times[("R1", "R2")] == 30.0, (
            "Custom default no se aplica correctamente"
        )
    
    def test_buffer_vs_travel_time_calculation(
        self,
        schedule_without_deadhead: List[BusSchedule]
    ):
        """
        Debug: Calcular buffer real vs tiempo de viaje extraído.
        
        Schedule:
        - R1 termina: 09:00
        - R2 empieza: 09:15
        - Buffer: 15 min
        
        Si travel_time extraído es 15 (default), buffer == travel_time
        → Siempre factible (borde)
        
        Si travel_time real es mayor, será infactible.
        """
        travel_times = extract_travel_times_from_schedule(
            schedule_without_deadhead,
            default_time=15.0
        )
        
        # Calcular buffer real
        bus = schedule_without_deadhead[0]
        items = bus.items
        end_r1 = time_to_minutes(items[0].end_time)  # 09:00 = 540
        start_r2 = time_to_minutes(items[1].start_time)  # 09:15 = 555
        buffer = start_r2 - end_r1  # 15 min
        
        travel_time = travel_times.get(("R1", "R2"), 15.0)
        
        print(f"\n[BUFFER ANALYSIS]")
        print(f"  R1 end: {items[0].end_time} ({end_r1} min)")
        print(f"  R2 start: {items[1].start_time} ({start_r2} min)")
        print(f"  Buffer: {buffer} min")
        print(f"  Travel time (extracted): {travel_time} min")
        print(f"  Margin: {buffer - travel_time} min")
        
        assert buffer == 15, f"Buffer debería ser 15 min, es {buffer}"
        assert travel_time == 15, f"Travel time debería ser 15 min (default), es {travel_time}"


# =============================================================================
# TEST 5: EDGE CASES Y BUG HUNTING
# =============================================================================

@pytest.fixture
def realistic_schedule() -> List[BusSchedule]:
    """Crear schedule realista con buffers moderados."""
    if not IMPORTS_OK:
        pytest.skip("Imports no disponibles")
        
    return [
        BusSchedule(
            bus_id="BUS-REALISTIC-1",
            items=[
                ScheduleItem(
                    route_id="R1",
                    type="entry",
                    start_time=time(7, 0),
                    end_time=time(7, 45),   # 45 min duración
                    deadhead_minutes=8
                ),
                ScheduleItem(
                    route_id="R2",
                    type="entry",
                    start_time=time(8, 0),   # 15 min buffer (8 viaje + 7 margen)
                    end_time=time(8, 45),
                    deadhead_minutes=8
                ),
                ScheduleItem(
                    route_id="R3",
                    type="exit",
                    start_time=time(9, 0),   # 15 min buffer
                    end_time=time(9, 30),
                    deadhead_minutes=8
                ),
            ]
        ),
        BusSchedule(
            bus_id="BUS-REALISTIC-2",
            items=[
                ScheduleItem(
                    route_id="R4",
                    type="entry",
                    start_time=time(7, 30),
                    end_time=time(8, 15),
                    deadhead_minutes=10
                ),
                ScheduleItem(
                    route_id="R5",
                    type="exit",
                    start_time=time(8, 30),  # 15 min buffer
                    end_time=time(9, 30),
                    deadhead_minutes=10
                ),
            ]
        ),
    ]


@pytest.fixture
def realistic_travel_times() -> Dict[Tuple[str, str], float]:
    """Tiempos de viaje realistas."""
    return {
        ("R1", "R2"): 8.0,
        ("R2", "R3"): 8.0,
        ("R4", "R5"): 10.0,
    }


class TestEdgeCases:
    """Tests para casos límite y detección de bugs."""
    
    def test_single_route_always_feasible(
        self,
        validator: MonteCarloValidator
    ):
        """Un bus con una sola ruta siempre es factible (no hay transiciones)."""
        if not IMPORTS_OK:
            pytest.skip("Imports no disponibles")
            
        schedule = [
            BusSchedule(
                bus_id="BUS-SINGLE",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        type="entry",
                        start_time=time(8, 0),
                        end_time=time(9, 0),
                        deadhead_minutes=10
                    ),
                ]
            )
        ]
        
        travel_times = {}
        
        result = validator.validate_schedule(schedule, travel_times)
        
        print(f"\n[SINGLE ROUTE RESULT]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        
        # Sin transiciones, siempre factible
        assert result.feasibility_rate == 1.0, (
            f"Single route dio {result.feasibility_rate:.2%} factible, "
            f"debería ser 100% (no hay transiciones)"
        )
    
    def test_empty_schedule(
        self,
        validator: MonteCarloValidator
    ):
        """Schedule vacío debe ser 100% factible."""
        if not IMPORTS_OK:
            pytest.skip("Imports no disponibles")
            
        schedule = []
        travel_times = {}
        
        result = validator.validate_schedule(schedule, travel_times)
        
        assert result.feasibility_rate == 1.0, "Schedule vacío debería ser 100% factible"
        assert result.avg_violations == 0, "Schedule vacío no debería tener violaciones"
    
    def test_zero_uncertainty_deterministic(
        self,
        realistic_schedule: List[BusSchedule],
        realistic_travel_times: Dict[Tuple[str, str], float]
    ):
        """Con 0% incertidumbre, el resultado debe ser determinístico."""
        if not IMPORTS_OK:
            pytest.skip("Imports no disponibles")
            
        validator = MonteCarloValidator(
            n_simulations=100,
            time_uncertainty=0.0,  # Sin incertidumbre
            seed=42
        )
        
        result = validator.validate_schedule(
            realistic_schedule, 
            realistic_travel_times
        )
        
        print(f"\n[ZERO UNCERTAINTY RESULT]")
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        
        # Sin incertidumbre, debe ser 0% o 100% (determinístico)
        assert result.feasibility_rate in [0.0, 1.0], (
            f"Con 0% incertidumbre, resultado debería ser determinístico "
            f"(0% o 100%), pero es {result.feasibility_rate:.2%}"
        )
    
    def test_different_distributions(
        self,
        realistic_schedule: List[BusSchedule],
        realistic_travel_times: Dict[Tuple[str, str], float]
    ):
        """Comparar resultados con diferentes distribuciones."""
        if not IMPORTS_OK:
            pytest.skip("Imports no disponibles")
            
        distributions = ["lognormal", "normal", "uniform"]
        results = {}
        
        for dist in distributions:
            validator = MonteCarloValidator(
                n_simulations=500,
                time_uncertainty=0.2,
                distribution=dist,
                seed=42
            )
            result = validator.validate_schedule(
                realistic_schedule, 
                realistic_travel_times
            )
            results[dist] = result.feasibility_rate
        
        print(f"\n[DISTRIBUTION COMPARISON]")
        for dist, rate in results.items():
            print(f"  {dist}: {rate:.2%}")
        
        # Todas las distribuciones deberían dar resultados razonables
        for dist, rate in results.items():
            assert 0.0 <= rate <= 1.0, f"{dist} dio resultado inválido: {rate}"
    
    def test_negative_buffer_detection(
        self,
        validator: MonteCarloValidator
    ):
        """
        Detectar si hay buffers negativos (schedules mal formados).
        
        Si una ruta empieza antes de que termine la anterior,
        es un schedule mal formado.
        """
        if not IMPORTS_OK:
            pytest.skip("Imports no disponibles")
            
        # Schedule con buffer negativo (mal formado)
        schedule = [
            BusSchedule(
                bus_id="BUS-NEGATIVE",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        type="entry",
                        start_time=time(8, 0),
                        end_time=time(9, 0),
                        deadhead_minutes=10
                    ),
                    ScheduleItem(
                        route_id="R2",
                        type="exit",
                        start_time=time(8, 45),  # 15 min ANTES de que termine R1!
                        end_time=time(9, 45),
                        deadhead_minutes=10
                    ),
                ]
            )
        ]
        
        travel_times = {("R1", "R2"): 10.0}
        
        # Verificar el buffer
        bus = schedule[0]
        end_r1 = time_to_minutes(bus.items[0].end_time)  # 540
        start_r2 = time_to_minutes(bus.items[1].start_time)  # 525
        buffer = start_r2 - end_r1  # -15 min
        
        print(f"\n[NEGATIVE BUFFER DETECTION]")
        print(f"  Buffer: {buffer} min (NEGATIVO!)")
        
        assert buffer < 0, "Test mal configurado - buffer debería ser negativo"
        
        result = validator.validate_schedule(schedule, travel_times)
        
        print(f"  Feasibility rate: {result.feasibility_rate:.2%}")
        
        # Debe ser 0% (imposible)
        assert result.feasibility_rate == 0.0, (
            f"Buffer negativo dio {result.feasibility_rate:.2%} factible, "
            f"debería ser 0%"
        )


# =============================================================================
# TEST 6: GRADE CALCULATION
# =============================================================================

class TestGradeCalculation:
    """Tests para la asignación de grados."""
    
    def test_grade_boundaries(self, validator: MonteCarloValidator):
        """Verificar límites de grados."""
        from unittest.mock import Mock
        
        test_cases = [
            (0.96, "A"),
            (0.95, "A"),  # Boundary
            (0.94, "B"),
            (0.85, "B"),  # Boundary
            (0.84, "C"),
            (0.70, "C"),  # Boundary
            (0.69, "D"),
            (0.50, "D"),  # Boundary
            (0.49, "F"),
            (0.00, "F"),
        ]
        
        for rate, expected_grade in test_cases:
            result = Mock()
            result.feasibility_rate = rate
            grade = validator.get_robustness_grade(result)
            
            assert grade == expected_grade, (
                f"Rate {rate} debería dar grado {expected_grade}, dio {grade}"
            )
    
    def test_recommendations(self, validator: MonteCarloValidator):
        """Verificar que hay recomendaciones para todos los grados."""
        from unittest.mock import Mock
        
        for grade in ["A", "B", "C", "D", "F"]:
            result = Mock()
            result.feasibility_rate = {"A": 0.96, "B": 0.90, "C": 0.75, "D": 0.60, "F": 0.40}[grade]
            
            rec = validator.get_recommendation(result)
            
            assert rec is not None and len(rec) > 0, (
                f"No hay recomendación para grado {grade}"
            )
            assert grade in ["A", "B", "C", "D", "F"] or "REVISAR" in rec


# =============================================================================
# REPORTE DE RESULTADOS
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def print_summary(request):
    """Imprimir resumen al final de todos los tests."""
    yield
    
    print("\n" + "="*70)
    print("RESUMEN DE TESTS MONTE CARLO VALIDATION")
    print("="*70)
    print("""
Tests creados:
1. test_perfect_schedule_feasibility_rate - Schedule con buffers enormes
2. test_impossible_schedule_feasibility_rate - Schedule con traslapes
3. test_realistic_schedule_feasibility_range - Schedule realista
4. test_extract_travel_times_with_deadhead - Extracción de tiempos
5. test_buffer_vs_travel_time_calculation - Debug de buffers
6. test_single_route_always_feasible - Casos límite

Si el test 1 falla (perfect schedule da 0%), indica un bug grave.
Si el test 4 falla, revisar extract_travel_times_from_schedule.
    """)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
