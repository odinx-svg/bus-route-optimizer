"""
Optimizer Multi-Objective - Tutti Route Optimizer
=================================================

FASE 3.1: Función Objetivo Multi-criterio

Permite optimizar considerando múltiples objetivos simultáneamente:
- Número de buses
- Kilómetros en vacío (deadhead)
- Horas extra de conductores
- Adelantos de tiempo (time shifts)
- Balance de carga entre buses
- Costo de combustible
- Emisiones CO2

El optimizador usa una función objetivo ponderada que combina
todos estos criterios con pesos configurables.
"""

import logging
import math
from typing import Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import time

from models import Route, BusSchedule, ScheduleItem, Stop
from router_service import get_real_travel_time

logger = logging.getLogger(__name__)

# Constants
EARTH_RADIUS_KM: float = 6371.0
FALLBACK_SPEED_KMH: int = 50
DEADHEAD_BUFFER_MINUTES: int = 3


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two coordinates using haversine formula."""
    if lat1 == 0 or lon1 == 0 or lat2 == 0 or lon2 == 0:
        return 999.0
    R = EARTH_RADIUS_KM
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class ObjectiveWeights:
    """
    Pesos configurables para función objetivo multi-criterio.
    
    Cada peso representa el costo por unidad de la métrica correspondiente.
    Un peso mayor indica que esa métrica es más importante minimizar.
    """
    buses: float = 1000.0           # Penalización por cada bus adicional
    deadhead_km: float = 10.0       # Costo por km en vacío
    driver_overtime: float = 50.0   # Penalización por cada hora extra (>8h)
    time_shift_minutes: float = 5.0 # Costo por minuto de adelanto
    unbalanced_load: float = 20.0   # Varianza en rutas/bus
    fuel_cost: float = 0.15         # Costo por km total
    co2_emissions: float = 0.01     # Emisiones CO2 (kg por km)
    
    def to_dict(self) -> Dict[str, float]:
        """Convertir a diccionario para serialización."""
        return {
            "buses": self.buses,
            "deadhead_km": self.deadhead_km,
            "driver_overtime": self.driver_overtime,
            "time_shift_minutes": self.time_shift_minutes,
            "unbalanced_load": self.unbalanced_load,
            "fuel_cost": self.fuel_cost,
            "co2_emissions": self.co2_emissions,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "ObjectiveWeights":
        """Crear instancia desde diccionario."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ObjectivePresets:
    """Presets predefinidos para diferentes escenarios de optimización."""
    
    @staticmethod
    def minimize_buses() -> ObjectiveWeights:
        """Preset para minimizar principalmente el número de buses."""
        return ObjectiveWeights(
            buses=1000,
            deadhead_km=10,
            driver_overtime=50,
            time_shift_minutes=5,
            unbalanced_load=10,
            fuel_cost=0.1,
            co2_emissions=0.005
        )
    
    @staticmethod
    def minimize_cost() -> ObjectiveWeights:
        """Preset para minimizar costos operacionales."""
        return ObjectiveWeights(
            buses=500,
            deadhead_km=20,
            driver_overtime=100,
            time_shift_minutes=2,
            fuel_cost=0.25,
            unbalanced_load=15,
            co2_emissions=0.005
        )
    
    @staticmethod
    def minimize_emissions() -> ObjectiveWeights:
        """Preset para minimizar emisiones de CO2."""
        return ObjectiveWeights(
            buses=800,
            deadhead_km=30,
            driver_overtime=50,
            time_shift_minutes=5,
            unbalanced_load=10,
            fuel_cost=0.1,
            co2_emissions=0.05
        )
    
    @staticmethod
    def balanced() -> ObjectiveWeights:
        """Preset balanceado (default)."""
        return ObjectiveWeights()
    
    @staticmethod
    def get_preset(name: str) -> ObjectiveWeights:
        """Obtener preset por nombre."""
        presets = {
            "minimize_buses": ObjectivePresets.minimize_buses(),
            "minimize_cost": ObjectivePresets.minimize_cost(),
            "minimize_emissions": ObjectivePresets.minimize_emissions(),
            "balanced": ObjectivePresets.balanced(),
        }
        return presets.get(name, ObjectivePresets.balanced())


@dataclass
class ScheduleMetrics:
    """Métricas calculadas para un schedule."""
    num_buses: int
    total_deadhead_km: float
    total_overtime_hours: float
    total_time_shift_minutes: int
    load_variance: float
    total_fuel_cost: float
    total_co2_emissions: float
    total_routes: int
    avg_routes_per_bus: float
    
    def to_dict(self) -> Dict[str, any]:
        """Convertir a diccionario."""
        return {
            "num_buses": self.num_buses,
            "total_deadhead_km": round(self.total_deadhead_km, 2),
            "total_overtime_hours": round(self.total_overtime_hours, 2),
            "total_time_shift_minutes": self.total_time_shift_minutes,
            "load_variance": round(self.load_variance, 2),
            "total_fuel_cost": round(self.total_fuel_cost, 2),
            "total_co2_emissions": round(self.total_co2_emissions, 2),
            "total_routes": self.total_routes,
            "avg_routes_per_bus": round(self.avg_routes_per_bus, 2),
        }


class MultiObjectiveOptimizer:
    """
    Optimizador con función objetivo multi-criterio configurable.
    
    Permite evaluar schedules según múltiples objetivos ponderados
    y comparar diferentes soluciones de manera consistente.
    """
    
    def __init__(self, weights: Optional[ObjectiveWeights] = None):
        """
        Inicializar el optimizador con pesos específicos.
        
        Args:
            weights: Pesos para cada objetivo. Si es None, usa valores default.
        """
        self.weights = weights or ObjectiveWeights()
        self._distance_cache: Dict[Tuple[str, str], float] = {}
    
    def evaluate_schedule(self, schedule: List[BusSchedule]) -> float:
        """
        Evaluar un schedule según la función objetivo ponderada.
        
        Args:
            schedule: Lista de BusSchedule a evaluar
            
        Returns:
            float: Score del schedule (menor = mejor)
        """
        if not schedule:
            return float('inf')
        
        score = 0.0
        
        # 1. Número de buses
        score += self.weights.buses * len(schedule)
        
        # 2. Deadhead (km en vacío)
        total_deadhead = self.calculate_deadhead(schedule)
        score += self.weights.deadhead_km * total_deadhead
        
        # 3. Overtime de conductores
        total_overtime = self.calculate_overtime(schedule)
        score += self.weights.driver_overtime * total_overtime
        
        # 4. Time shifts (adelantos)
        total_shift = self.calculate_time_shifts(schedule)
        score += self.weights.time_shift_minutes * total_shift
        
        # 5. Balance de carga (varianza)
        routes_per_bus = [len(bus.items) for bus in schedule]
        variance = self.calculate_variance(routes_per_bus)
        score += self.weights.unbalanced_load * variance
        
        # 6. Costo combustible (total km)
        total_km = self.calculate_total_km(schedule)
        score += self.weights.fuel_cost * total_km
        
        # 7. Emisiones CO2
        score += self.weights.co2_emissions * total_km
        
        return score
    
    def calculate_metrics(self, schedule: List[BusSchedule]) -> ScheduleMetrics:
        """
        Calcular todas las métricas para un schedule.
        
        Args:
            schedule: Lista de BusSchedule
            
        Returns:
            ScheduleMetrics con todas las métricas calculadas
        """
        if not schedule:
            return ScheduleMetrics(0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0, 0.0)
        
        num_buses = len(schedule)
        total_routes = sum(len(bus.items) for bus in schedule)
        avg_routes = total_routes / num_buses if num_buses > 0 else 0.0
        
        routes_per_bus = [len(bus.items) for bus in schedule]
        load_variance = self.calculate_variance(routes_per_bus)
        
        total_deadhead = self.calculate_deadhead(schedule)
        total_overtime = self.calculate_overtime(schedule)
        total_shift = self.calculate_time_shifts(schedule)
        total_km = self.calculate_total_km(schedule)
        
        return ScheduleMetrics(
            num_buses=num_buses,
            total_deadhead_km=total_deadhead,
            total_overtime_hours=total_overtime,
            total_time_shift_minutes=total_shift,
            load_variance=load_variance,
            total_fuel_cost=self.weights.fuel_cost * total_km,
            total_co2_emissions=self.weights.co2_emissions * total_km,
            total_routes=total_routes,
            avg_routes_per_bus=avg_routes
        )
    
    def calculate_deadhead(self, schedule: List[BusSchedule]) -> float:
        """
        Calcular kilómetros en vacío entre rutas consecutivas.
        
        Args:
            schedule: Lista de BusSchedule
            
        Returns:
            Total de kilómetros en vacío
        """
        total = 0.0
        
        for bus in schedule:
            items = bus.items
            for i in range(len(items) - 1):
                current = items[i]
                next_item = items[i + 1]
                
                # Obtener coordenadas
                current_end = self._get_end_location(current)
                next_start = self._get_start_location(next_item)
                
                # Calcular distancia
                km = self._distance_between(current_end, next_start)
                total += km
        
        return total
    
    def calculate_overtime(self, schedule: List[BusSchedule]) -> float:
        """
        Calcular horas extra totales (jornadas > 8 horas).
        
        Args:
            schedule: Lista de BusSchedule
            
        Returns:
            Total de horas extra
        """
        total = 0.0
        
        for bus in schedule:
            if not bus.items:
                continue
            
            # Calcular duración de la jornada
            start_times = []
            end_times = []
            
            for item in bus.items:
                start_minutes = item.start_time.hour * 60 + item.start_time.minute
                end_minutes = item.end_time.hour * 60 + item.end_time.minute
                start_times.append(start_minutes)
                end_times.append(end_minutes)
            
            if not start_times or not end_times:
                continue
            
            day_start = min(start_times)
            day_end = max(end_times)
            hours_worked = (day_end - day_start) / 60.0
            
            if hours_worked > 8:
                total += hours_worked - 8
        
        return total
    
    def calculate_time_shifts(self, schedule: List[BusSchedule]) -> int:
        """
        Calcular total de minutos de adelanto (time shifts).
        
        Args:
            schedule: Lista de BusSchedule
            
        Returns:
            Total de minutos de adelanto
        """
        total = 0
        for bus in schedule:
            for item in bus.items:
                if item.time_shift_minutes and item.time_shift_minutes > 0:
                    total += item.time_shift_minutes
        return total
    
    def calculate_total_km(self, schedule: List[BusSchedule]) -> float:
        """
        Calcular kilómetros totales recorridos (rutas + deadhead).
        
        Args:
            schedule: Lista de BusSchedule
            
        Returns:
            Total de kilómetros
        """
        total_route_km = 0.0
        
        for bus in schedule:
            for item in bus.items:
                # Calcular km de la ruta (suma de distancias entre paradas)
                route_km = self._calculate_route_km(item.stops)
                total_route_km += route_km
        
        # Agregar deadhead
        deadhead_km = self.calculate_deadhead(schedule)
        
        return total_route_km + deadhead_km
    
    def calculate_variance(self, values: List[int]) -> float:
        """
        Calcular varianza de una lista de valores.
        
        Args:
            values: Lista de valores enteros
            
        Returns:
            Varianza poblacional
        """
        if not values or len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance
    
    def compare_schedules(
        self, 
        schedule1: List[BusSchedule], 
        schedule2: List[BusSchedule]
    ) -> Dict[str, any]:
        """
        Comparar dos schedules y retornar análisis detallado.
        
        Args:
            schedule1: Primer schedule
            schedule2: Segundo schedule
            
        Returns:
            Diccionario con comparación de métricas
        """
        score1 = self.evaluate_schedule(schedule1)
        score2 = self.evaluate_schedule(schedule2)
        metrics1 = self.calculate_metrics(schedule1)
        metrics2 = self.calculate_metrics(schedule2)
        
        return {
            "schedule1": {
                "score": round(score1, 2),
                "metrics": metrics1.to_dict()
            },
            "schedule2": {
                "score": round(score2, 2),
                "metrics": metrics2.to_dict()
            },
            "improvement": {
                "score_diff": round(score1 - score2, 2),
                "score_pct": round((score1 - score2) / score1 * 100, 2) if score1 > 0 else 0,
                "winner": "schedule1" if score1 < score2 else "schedule2" if score2 < score1 else "tie"
            }
        }
    
    def _get_end_location(self, item: ScheduleItem) -> Tuple[float, float]:
        """Obtener ubicación final de un ScheduleItem."""
        if item.stops and len(item.stops) > 0:
            last_stop = item.stops[-1]
            return (last_stop.lat, last_stop.lon)
        return (0.0, 0.0)
    
    def _get_start_location(self, item: ScheduleItem) -> Tuple[float, float]:
        """Obtener ubicación inicial de un ScheduleItem."""
        if item.stops and len(item.stops) > 0:
            first_stop = item.stops[0]
            return (first_stop.lat, first_stop.lon)
        return (0.0, 0.0)
    
    def _distance_between(
        self, 
        loc1: Tuple[float, float], 
        loc2: Tuple[float, float]
    ) -> float:
        """
        Calcular distancia entre dos ubicaciones.
        
        Primero intenta usar OSRM, luego fallback a Haversine.
        """
        if loc1 == (0.0, 0.0) or loc2 == (0.0, 0.0):
            return 0.0
        
        # Cache key
        cache_key = (f"{loc1[0]:.4f},{loc1[1]:.4f}", f"{loc2[0]:.4f},{loc2[1]:.4f}")
        
        if cache_key in self._distance_cache:
            return self._distance_cache[cache_key]
        
        # Intentar con OSRM primero
        try:
            travel_time = get_real_travel_time(loc1[0], loc1[1], loc2[0], loc2[1])
            if travel_time is not None:
                # Estimar distancia asumiendo velocidad promedio
                km = (travel_time / 60.0) * FALLBACK_SPEED_KMH
                self._distance_cache[cache_key] = km
                return km
        except Exception:
            pass
        
        # Fallback a Haversine
        km = _haversine_km(loc1[0], loc1[1], loc2[0], loc2[1])
        self._distance_cache[cache_key] = km
        return km
    
    def _calculate_route_km(self, stops: List[Stop]) -> float:
        """Calcular distancia total de una ruta dados sus stops."""
        if not stops or len(stops) < 2:
            return 0.0
        
        total = 0.0
        for i in range(len(stops) - 1):
            total += _haversine_km(
                stops[i].lat, stops[i].lon,
                stops[i + 1].lat, stops[i + 1].lon
            )
        return total


def evaluate_schedule(
    schedule: List[BusSchedule],
    weights: Optional[ObjectiveWeights] = None
) -> float:
    """
    Función convenience para evaluar un schedule.
    
    Args:
        schedule: Lista de BusSchedule
        weights: Pesos opcionales (usa default si None)
        
    Returns:
        Score del schedule
    """
    optimizer = MultiObjectiveOptimizer(weights)
    return optimizer.evaluate_schedule(schedule)


def get_schedule_metrics(
    schedule: List[BusSchedule],
    weights: Optional[ObjectiveWeights] = None
) -> ScheduleMetrics:
    """
    Función convenience para obtener métricas de un schedule.
    
    Args:
        schedule: Lista de BusSchedule
        weights: Pesos opcionales
        
    Returns:
        ScheduleMetrics
    """
    optimizer = MultiObjectiveOptimizer(weights)
    return optimizer.calculate_metrics(schedule)


__all__ = [
    'ObjectiveWeights',
    'ObjectivePresets',
    'ScheduleMetrics',
    'MultiObjectiveOptimizer',
    'evaluate_schedule',
    'get_schedule_metrics',
]
