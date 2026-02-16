"""
Métricas avanzadas para evaluación de schedules.
"""

import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

try:
    from backend.models import Route, BusSchedule, ScheduleItem
except ImportError:
    from models import Route, BusSchedule, ScheduleItem


@dataclass
class EfficiencyMetrics:
    """Métricas de eficiencia de un schedule."""
    bus_utilization_rate: float  # % de tiempo productivo vs total
    avg_routes_per_bus: float
    total_deadhead_minutes: float
    total_deadhead_km: float
    avg_time_between_routes: float  # tiempo promedio entre rutas consecutivas
    coverage_ratio: float  # rutas asignadas / rutas totales
    bus_count_efficiency: float  # ratio óptimo vs actual
    
    def to_dict(self) -> Dict:
        return {
            "bus_utilization_rate": round(self.bus_utilization_rate, 3),
            "bus_utilization_pct": f"{self.bus_utilization_rate:.1%}",
            "avg_routes_per_bus": round(self.avg_routes_per_bus, 2),
            "total_deadhead_minutes": round(self.total_deadhead_minutes, 1),
            "total_deadhead_km": round(self.total_deadhead_km, 2),
            "avg_time_between_routes": round(self.avg_time_between_routes, 1),
            "coverage_ratio": round(self.coverage_ratio, 3),
            "coverage_pct": f"{self.coverage_ratio:.1%}",
            "bus_count_efficiency": round(self.bus_count_efficiency, 3)
        }


@dataclass
class RobustnessMetrics:
    """Métricas de robustez de un schedule."""
    min_buffer_time: float  # buffer mínimo entre rutas
    avg_buffer_time: float  # buffer promedio
    critical_transitions: int  # transiciones con < 5 min buffer
    max_chain_length: int  # máximo número de rutas consecutivas
    time_flexibility: float  # capacidad de absorber retrasos
    
    def to_dict(self) -> Dict:
        return {
            "min_buffer_time": round(self.min_buffer_time, 1),
            "avg_buffer_time": round(self.avg_buffer_time, 1),
            "critical_transitions": self.critical_transitions,
            "max_chain_length": self.max_chain_length,
            "time_flexibility": round(self.time_flexibility, 3)
        }


def calculate_efficiency_metrics(
    schedule: List[BusSchedule],
    routes: List[Route]
) -> EfficiencyMetrics:
    """
    Calcular métricas de eficiencia.
    
    Args:
        schedule: Schedule generado
        routes: Rutas originales
    
    Returns:
        EfficiencyMetrics
    """
    if not schedule:
        return EfficiencyMetrics(0, 0, 0, 0, 0, 0, 0)
    
    # Total de items
    total_items = sum(len(bus.items) for bus in schedule)
    avg_routes = total_items / len(schedule) if schedule else 0
    
    # Deadhead total
    total_deadhead = sum(
        item.deadhead_minutes
        for bus in schedule
        for item in bus.items
        if item.deadhead_minutes > 0
    )
    
    # Estimar km de deadhead (asumiendo 50 km/h)
    deadhead_km = (total_deadhead / 60) * 50
    
    # Tiempo promedio entre rutas (deadhead promedio)
    deadhead_items = [
        item.deadhead_minutes
        for bus in schedule
        for item in bus.items
        if item.deadhead_minutes > 0
    ]
    avg_time_between = statistics.mean(deadhead_items) if deadhead_items else 0
    
    # Coverage ratio
    assigned_route_ids = set()
    for bus in schedule:
        for item in bus.items:
            assigned_route_ids.add(item.route_id)
    coverage = len(assigned_route_ids) / len(routes) if routes else 0
    
    # Utilización: tiempo en ruta vs tiempo total
    # Estimación simplificada
    productive_time = sum(
        (item.end_time.hour * 60 + item.end_time.minute) - 
        (item.start_time.hour * 60 + item.start_time.minute)
        for bus in schedule
        for item in bus.items
    )
    total_time = productive_time + total_deadhead
    utilization = productive_time / total_time if total_time > 0 else 0
    
    # Eficiencia de conteo de buses
    # Teóricamente, el mínimo sería el máximo de rutas simultáneas
    theoretical_min = _estimate_theoretical_min_buses(routes)
    bus_efficiency = theoretical_min / len(schedule) if schedule else 0
    
    return EfficiencyMetrics(
        bus_utilization_rate=utilization,
        avg_routes_per_bus=avg_routes,
        total_deadhead_minutes=total_deadhead,
        total_deadhead_km=deadhead_km,
        avg_time_between_routes=avg_time_between,
        coverage_ratio=coverage,
        bus_count_efficiency=bus_efficiency
    )


def calculate_robustness_metrics(schedule: List[BusSchedule]) -> RobustnessMetrics:
    """
    Calcular métricas de robustez de un schedule.
    
    Args:
        schedule: Schedule a analizar
    
    Returns:
        RobustnessMetrics
    """
    if not schedule:
        return RobustnessMetrics(0, 0, 0, 0, 0)
    
    buffers = []
    critical = 0
    max_chain = 0
    
    for bus in schedule:
        items = sorted(bus.items, key=lambda x: x.start_time)
        
        if len(items) > max_chain:
            max_chain = len(items)
        
        for i in range(len(items) - 1):
            current = items[i]
            next_item = items[i + 1]
            
            # Calcular buffer
            end_current = current.end_time.hour * 60 + current.end_time.minute
            start_next = next_item.start_time.hour * 60 + next_item.start_time.minute
            buffer = start_next - end_current
            
            buffers.append(buffer)
            
            if buffer < 5:  # Menos de 5 minutos es crítico
                critical += 1
    
    if buffers:
        min_buffer = min(buffers)
        avg_buffer = statistics.mean(buffers)
        # Flexibilidad: proporción de buffers > 10 min
        flexibility = sum(1 for b in buffers if b >= 10) / len(buffers)
    else:
        min_buffer = 0
        avg_buffer = 0
        flexibility = 0
    
    return RobustnessMetrics(
        min_buffer_time=min_buffer,
        avg_buffer_time=avg_buffer,
        critical_transitions=critical,
        max_chain_length=max_chain,
        time_flexibility=flexibility
    )


def calculate_multi_objective_score(
    schedule: List[BusSchedule],
    routes: List[Route],
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Calcular score multi-objetivo ponderado.
    
    Args:
        schedule: Schedule a evaluar
        routes: Rutas originales
        weights: Pesos para cada objetivo
            - w_buses: peso para número de buses (default: 1.0)
            - w_deadhead: peso para deadhead (default: 0.01)
            - w_robustness: peso para robustez (default: 0.5)
            - w_utilization: peso para utilización (default: 0.3)
    
    Returns:
        Score total (menor es mejor)
    """
    if weights is None:
        weights = {
            'w_buses': 1.0,
            'w_deadhead': 0.01,
            'w_robustness': 0.5,
            'w_utilization': 0.3
        }
    
    # Número de buses
    n_buses = len(schedule)
    
    # Deadhead total
    total_deadhead = sum(
        item.deadhead_minutes
        for bus in schedule
        for item in bus.items
        if item.deadhead_minutes > 0
    )
    
    # Métricas de robustez
    robustness = calculate_robustness_metrics(schedule)
    # Penalizar transiciones críticas
    robustness_score = robustness.critical_transitions * 10 - robustness.min_buffer_time
    
    # Utilización
    efficiency = calculate_efficiency_metrics(schedule, routes)
    utilization_penalty = (1 - efficiency.bus_utilization_rate) * 100
    
    # Score ponderado
    score = (
        weights['w_buses'] * n_buses * 100 +
        weights['w_deadhead'] * total_deadhead +
        weights['w_robustness'] * robustness_score +
        weights['w_utilization'] * utilization_penalty
    )
    
    return score


def compare_schedules(
    schedule_a: List[BusSchedule],
    schedule_b: List[BusSchedule],
    routes: List[Route],
    name_a: str = "Algorithm A",
    name_b: str = "Algorithm B"
) -> Dict:
    """
    Comparar dos schedules en múltiples dimensiones.
    
    Returns:
        Dict con comparación detallada
    """
    eff_a = calculate_efficiency_metrics(schedule_a, routes)
    eff_b = calculate_efficiency_metrics(schedule_b, routes)
    
    rob_a = calculate_robustness_metrics(schedule_a)
    rob_b = calculate_robustness_metrics(schedule_b)
    
    score_a = calculate_multi_objective_score(schedule_a, routes)
    score_b = calculate_multi_objective_score(schedule_b, routes)
    
    return {
        "comparison": {
            name_a: {
                "buses": len(schedule_a),
                "efficiency": eff_a.to_dict(),
                "robustness": rob_a.to_dict(),
                "score": round(score_a, 2)
            },
            name_b: {
                "buses": len(schedule_b),
                "efficiency": eff_b.to_dict(),
                "robustness": rob_b.to_dict(),
                "score": round(score_b, 2)
            }
        },
        "winner": name_a if score_a < score_b else name_b,
        "score_difference": round(abs(score_a - score_b), 2),
        "improvement_pct": round(abs(score_a - score_b) / max(score_a, score_b) * 100, 1)
    }


def _estimate_theoretical_min_buses(routes: List[Route]) -> int:
    """
    Estimar número mínimo teórico de buses.
    
    Basado en el máximo número de rutas simultáneas.
    """
    if not routes:
        return 0
    
    # Convertir a intervalos de tiempo
    intervals = []
    for route in routes:
        if route.type == "entry" and route.arrival_time:
            start = route.arrival_time.hour * 60 + route.arrival_time.minute - 30  # estimado
            end = route.arrival_time.hour * 60 + route.arrival_time.minute
        elif route.type == "exit" and route.departure_time:
            start = route.departure_time.hour * 60 + route.departure_time.minute
            end = route.departure_time.hour * 60 + route.departure_time.minute + 30
        else:
            continue
        intervals.append((start, end))
    
    if not intervals:
        return len(routes)  # fallback
    
    # Encontrar máximo overlap
    events = []
    for start, end in intervals:
        events.append((start, 1))
        events.append((end, -1))
    
    events.sort()
    
    max_overlap = 0
    current_overlap = 0
    for _, delta in events:
        current_overlap += delta
        max_overlap = max(max_overlap, current_overlap)
    
    return max_overlap


# Import statistics aquí para evitar import circular
import statistics

__all__ = [
    'EfficiencyMetrics',
    'RobustnessMetrics',
    'calculate_efficiency_metrics',
    'calculate_robustness_metrics',
    'calculate_multi_objective_score',
    'compare_schedules'
]
