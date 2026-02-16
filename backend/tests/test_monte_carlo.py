"""
Tests unitarios para validación de cálculo de buffers en Monte Carlo.

Este módulo verifica específicamente que el cálculo de:
    buffer = tiempo_disponible - tiempo_necesario
sea correcto y que las unidades sean consistentes (minutos).
"""

import pytest
from datetime import time
from typing import List, Dict, Tuple

from models import BusSchedule, ScheduleItem
from validation.monte_carlo import (
    check_schedule_feasibility,
    time_to_minutes,
    extract_travel_times_from_schedule
)


# =============================================================================
# Tests de time_to_minutes
# =============================================================================

class TestTimeToMinutes:
    """Tests para la función de conversión de tiempo."""
    
    def test_time_to_minutes_basic(self):
        """Test conversión básica de time a minutos."""
        assert time_to_minutes(time(7, 0)) == 420   # 7*60 = 420
        assert time_to_minutes(time(8, 30)) == 510  # 8*60 + 30 = 510
        assert time_to_minutes(time(12, 0)) == 720  # 12*60 = 720
        assert time_to_minutes(time(23, 59)) == 1439  # 23*60 + 59 = 1439
    
    def test_time_to_minutes_midnight(self):
        """Test conversión de medianoche."""
        assert time_to_minutes(time(0, 0)) == 0
    
    def test_time_to_minutes_ignores_seconds(self):
        """Test que ignora los segundos en la conversión."""
        # La función actual no considera segundos
        assert time_to_minutes(time(8, 30, 0)) == 510
        assert time_to_minutes(time(8, 30, 45)) == 510  # Segundos ignorados


# =============================================================================
# Tests de Buffer Calculation
# =============================================================================

class TestBufferCalculation:
    """
    Tests específicos para validar el cálculo de buffer.
    
    Buffer = tiempo_disponible - tiempo_necesario
           = (start_next - end_current) - travel_time
    
    Si buffer >= 0 → factible
    Si buffer < 0  → infeasible (llega tarde)
    """
    
    def test_buffer_exact_zero(self):
        """
        Test caso límite: buffer exactamente 0 (justo, debería ser factible).
        
        Ruta 1: 07:00 - 07:30 (30 min)
        Travel time: 15 min
        Ruta 2: 07:45 - 08:00
        
        Tiempo disponible: 07:45 - 07:30 = 15 min
        Buffer: 15 - 15 = 0 min (justo, factible)
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(7, 0),
                        end_time=time(7, 30),
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(7, 45),
                        end_time=time(8, 0),
                        type="exit",
                        deadhead_minutes=15
                    )
                ]
            )
        ]
        travel_times = {("R1", "R2"): 15.0}  # Exactamente 15 min
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        # Con 15 min disponibles y 15 min necesarios, debería ser factible (justo)
        assert is_feasible is True
        assert violations == 0
    
    def test_buffer_positive_small(self):
        """
        Test buffer positivo pequeño (factible con margen).
        
        Ruta 1: 07:00 - 07:30
        Travel time: 10 min
        Ruta 2: 07:45 - 08:00
        
        Tiempo disponible: 15 min
        Buffer: 15 - 10 = 5 min (positivo, factible)
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(7, 0),
                        end_time=time(7, 30),
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(7, 45),
                        end_time=time(8, 0),
                        type="exit"
                    )
                ]
            )
        ]
        travel_times = {("R1", "R2"): 10.0}  # Solo 10 min necesarios
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        assert is_feasible is True
        assert violations == 0
    
    def test_buffer_negative(self):
        """
        Test buffer negativo (infeasible, llega tarde).
        
        Ruta 1: 07:00 - 07:30
        Travel time: 20 min
        Ruta 2: 07:45 - 08:00
        
        Tiempo disponible: 15 min
        Buffer: 15 - 20 = -5 min (negativo, infeasible)
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(7, 0),
                        end_time=time(7, 30),
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(7, 45),
                        end_time=time(8, 0),
                        type="exit"
                    )
                ]
            )
        ]
        travel_times = {("R1", "R2"): 20.0}  # Necesita 20 min, solo hay 15
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        assert is_feasible is False
        assert violations == 1
    
    def test_buffer_calculation_manual_verification(self):
        """
        Test que verifica manualmente el cálculo interno del buffer.
        
        Este test expone el cálculo paso a paso para verificación manual.
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(8, 0),
                        end_time=time(8, 30),
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(9, 0),
                        end_time=time(9, 30),
                        type="exit"
                    )
                ]
            )
        ]
        
        # Cálculo manual
        end_current = time_to_minutes(time(8, 30))  # 510 minutos
        start_next = time_to_minutes(time(9, 0))     # 540 minutos
        tiempo_disponible = start_next - end_current  # 540 - 510 = 30 min
        
        travel_time = 25.0  # 25 min necesarios
        buffer = tiempo_disponible - travel_time  # 30 - 25 = 5 min (positivo)
        
        # Verificación
        assert end_current == 510, f"Esperado 510, got {end_current}"
        assert start_next == 540, f"Esperado 540, got {start_next}"
        assert tiempo_disponible == 30, f"Esperado 30, got {tiempo_disponible}"
        assert buffer == 5, f"Esperado 5, got {buffer}"
        
        # Verificación con la función
        travel_times = {("R1", "R2"): 25.0}
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        assert is_feasible is True
        assert violations == 0
    
    def test_multiple_buffers_calculation(self):
        """
        Test con múltiples rutas consecutivas, verificando cada buffer.
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(7, 0),
                        end_time=time(7, 30),
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(7, 50),  # 20 min después de R1
                        end_time=time(8, 20),
                        type="exit"
                    ),
                    ScheduleItem(
                        route_id="R3",
                        start_time=time(8, 30),  # 10 min después de R2
                        end_time=time(9, 0),
                        type="entry"
                    )
                ]
            )
        ]
        
        # R1→R2: 20 min disponibles, 15 min necesarios → buffer = 5 (OK)
        # R2→R3: 10 min disponibles, 15 min necesarios → buffer = -5 (FAIL)
        travel_times = {
            ("R1", "R2"): 15.0,
            ("R2", "R3"): 15.0
        }
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        # Debería haber 1 violación (R2→R3)
        assert is_feasible is False
        assert violations == 1
    
    def test_buffer_with_float_travel_time(self):
        """
        Test buffer con tiempos de viaje en float (decimales).
        Verifica que se manejen correctamente valores como 12.5 minutos.
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(8, 0),
                        end_time=time(8, 30),
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(8, 42),  # 12 min después
                        end_time=time(9, 0),
                        type="exit"
                    )
                ]
            )
        ]
        
        # 12 min disponibles vs 12.5 min necesarios → buffer = -0.5
        travel_times = {("R1", "R2"): 12.5}
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        assert is_feasible is False
        assert violations == 1


# =============================================================================
# Tests de Formatos de Tiempo
# =============================================================================

class TestTimeFormats:
    """Tests para verificar formatos de tiempo en los modelos."""
    
    def test_schedule_item_time_types(self):
        """
        Verifica que start_time y end_time sean objetos time.
        """
        item = ScheduleItem(
            route_id="R1",
            start_time=time(7, 30),
            end_time=time(8, 0),
            type="entry"
        )
        
        assert isinstance(item.start_time, time)
        assert isinstance(item.end_time, time)
        assert item.start_time.hour == 7
        assert item.start_time.minute == 30
        assert item.end_time.hour == 8
        assert item.end_time.minute == 0
    
    def test_deadhead_minutes_type(self):
        """
        Verifica que deadhead_minutes sea int.
        """
        item = ScheduleItem(
            route_id="R1",
            start_time=time(7, 0),
            end_time=time(7, 30),
            type="entry",
            deadhead_minutes=15
        )
        
        assert isinstance(item.deadhead_minutes, int)
        assert item.deadhead_minutes == 15
    
    def test_travel_times_dict_format(self):
        """
        Verifica el formato del diccionario de tiempos de viaje.
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(8, 0),
                        end_time=time(8, 30),
                        type="entry",
                        deadhead_minutes=10
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(8, 50),
                        end_time=time(9, 20),
                        type="exit",
                        deadhead_minutes=20
                    )
                ]
            )
        ]
        
        travel_times = extract_travel_times_from_schedule(schedule)
        
        # Verificar formato de las claves
        assert ("R1", "R2") in travel_times
        
        # Verificar que el valor es numérico (int o float)
        assert isinstance(travel_times[("R1", "R2")], (int, float))
        
        # El valor debería venir de deadhead_minutes del segundo item
        assert travel_times[("R1", "R2")] == 20


# =============================================================================
# Tests de Casos Edge
# =============================================================================

class TestEdgeCases:
    """Tests para casos límite y edge cases."""
    
    def test_same_start_and_end_time(self):
        """
        Test cuando una ruta tiene el mismo start y end (duración 0).
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(8, 0),
                        end_time=time(8, 0),  # Mismo tiempo
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(8, 10),
                        end_time=time(8, 30),
                        type="exit"
                    )
                ]
            )
        ]
        travel_times = {("R1", "R2"): 5.0}
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        # 10 min disponibles, 5 necesarios → factible
        assert is_feasible is True
    
    def test_very_small_buffer(self):
        """
        Test con buffer muy pequeño (0.1 min = 6 segundos).
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(8, 0),
                        end_time=time(8, 30),
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(8, 31),  # Solo 1 min después
                        end_time=time(9, 0),
                        type="exit"
                    )
                ]
            )
        ]
        travel_times = {("R1", "R2"): 0.9}  # Necesita 0.9 min = 54 seg
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        # 1 min disponible > 0.9 necesario → factible
        assert is_feasible is True
    
    def test_large_travel_time(self):
        """
        Test con tiempo de viaje muy grande.
        """
        schedule = [
            BusSchedule(
                bus_id="B001",
                items=[
                    ScheduleItem(
                        route_id="R1",
                        start_time=time(8, 0),
                        end_time=time(8, 30),
                        type="entry"
                    ),
                    ScheduleItem(
                        route_id="R2",
                        start_time=time(9, 30),  # 60 min después
                        end_time=time(10, 0),
                        type="exit"
                    )
                ]
            )
        ]
        travel_times = {("R1", "R2"): 120.0}  # Necesita 2 horas
        
        is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
        
        # 60 min disponibles < 120 necesarios → infeasible
        assert is_feasible is False


# =============================================================================
# Reporte de Formatos Encontrados
# =============================================================================

def test_report_time_formats():
    """
    Este test documenta los formatos de tiempo encontrados en el sistema.
    Sirve como documentación viva de los tipos de datos.
    """
    # Formatos en ScheduleItem:
    # - start_time: datetime.time (HH:MM:SS)
    # - end_time: datetime.time (HH:MM:SS)
    # - deadhead_minutes: int (minutos)
    
    item = ScheduleItem(
        route_id="TEST",
        start_time=time(7, 30, 0),  # HH:MM:SS
        end_time=time(8, 15, 30),   # HH:MM:SS (con segundos)
        type="entry",
        deadhead_minutes=15         # int, en minutos
    )
    
    # Verificaciones
    assert hasattr(item.start_time, 'hour')
    assert hasattr(item.start_time, 'minute')
    assert type(item.deadhead_minutes) == int
    
    # Formatos en travel_times:
    # - Dict[Tuple[str, str], float]
    # - Clave: (route_id_from, route_id_to)
    # - Valor: float (minutos, puede tener decimales)
    
    travel_times: Dict[Tuple[str, str], float] = {
        ("R1", "R2"): 15.0,     # float
        ("R2", "R3"): 12.5,     # float con decimales
    }
    
    assert isinstance(list(travel_times.keys())[0], tuple)
    assert isinstance(list(travel_times.values())[0], float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
