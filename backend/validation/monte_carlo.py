"""
Validación Monte Carlo para robustez de schedules.

Simula incertidumbre en tiempos de viaje para verificar
que el schedule siga siendo factible en condiciones reales.
"""

import math
import random
import statistics
from typing import List, Callable, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import time

try:
    from backend.models import Route, BusSchedule, ScheduleItem
except ImportError:
    from models import Route, BusSchedule, ScheduleItem


@dataclass
class SimulationResult:
    """Resultado de simulación Monte Carlo."""
    schedule: List[BusSchedule]
    feasibility_rate: float  # % de escenarios factibles
    avg_violations: float    # Violaciones promedio
    worst_case_violations: int
    confidence_interval: Tuple[float, float]  # (lower, upper) 95%
    violation_distribution: Dict[int, int]  # count of violations -> frequency
    
    def to_dict(self) -> Dict:
        """Convertir a diccionario para serialización JSON."""
        return {
            "feasibility_rate": self.feasibility_rate,
            "feasibility_rate_pct": f"{self.feasibility_rate:.1%}",
            "avg_violations": round(self.avg_violations, 2),
            "worst_case_violations": self.worst_case_violations,
            "confidence_interval_95": {
                "lower": round(self.confidence_interval[0], 2),
                "upper": round(self.confidence_interval[1], 2)
            },
            "violation_distribution": self.violation_distribution,
            "n_buses": len(self.schedule),
            "total_routes": sum(len(bus.items) for bus in self.schedule)
        }


class MonteCarloValidator:
    """Validador de robustez vía simulación Monte Carlo."""
    
    def __init__(
        self,
        n_simulations: int = 1000,
        time_uncertainty: float = 0.2,  # 20% de variación
        distribution: str = "lognormal",  # lognormal o normal
        seed: Optional[int] = None
    ):
        self.n_simulations = n_simulations
        self.time_uncertainty = time_uncertainty
        self.distribution = distribution
        
        if seed is not None:
            random.seed(seed)
    
    def validate_schedule(
        self,
        schedule: List[BusSchedule],
        base_travel_times: Dict[Tuple[str, str], float],
        feasibility_checker: Optional[Callable] = None
    ) -> SimulationResult:
        """
        Validar un schedule vía Monte Carlo.
        
        Args:
            schedule: Schedule a validar
            base_travel_times: Tiempos base de viaje (route_id_i, route_id_j) -> minutos
            feasibility_checker: Función que verifica si schedule es factible
        
        Returns:
            SimulationResult con métricas de robustez
        """
        if feasibility_checker is None:
            feasibility_checker = check_schedule_feasibility
        
        feasible_count = 0
        violation_counts = []
        violation_distribution: Dict[int, int] = {}
        
        for sim in range(self.n_simulations):
            # Simular tiempos de viaje con incertidumbre
            simulated_times = self.simulate_travel_times(base_travel_times)
            
            # Verificar factibilidad con tiempos simulados
            is_feasible, violations = feasibility_checker(
                schedule, 
                simulated_times
            )
            
            if is_feasible:
                feasible_count += 1
            
            violation_counts.append(violations)
            violation_distribution[violations] = violation_distribution.get(violations, 0) + 1
        
        # Calcular métricas
        feasibility_rate = feasible_count / self.n_simulations
        avg_violations = statistics.mean(violation_counts)
        worst_case = max(violation_counts)
        
        # Intervalo de confianza 95%
        if len(violation_counts) > 1:
            std_dev = statistics.stdev(violation_counts)
            margin = 1.96 * std_dev / (self.n_simulations ** 0.5)
            ci = (avg_violations - margin, avg_violations + margin)
        else:
            ci = (avg_violations, avg_violations)
        
        return SimulationResult(
            schedule=schedule,
            feasibility_rate=feasibility_rate,
            avg_violations=avg_violations,
            worst_case_violations=worst_case,
            confidence_interval=ci,
            violation_distribution=violation_distribution
        )
    
    def validate_schedule_with_scenarios(
        self,
        schedule: List[BusSchedule],
        base_travel_times: Dict[Tuple[str, str], float],
        scenarios: List[Dict[str, any]]
    ) -> List[SimulationResult]:
        """
        Validar schedule contra múltiples escenarios.
        
        Args:
            schedule: Schedule a validar
            base_travel_times: Tiempos base de viaje
            scenarios: Lista de configuraciones de escenarios
                Cada escenario tiene: name, uncertainty, distribution
        
        Returns:
            Lista de SimulationResult, uno por escenario
        """
        results = []
        
        for scenario in scenarios:
            # Guardar configuración original
            orig_uncertainty = self.time_uncertainty
            orig_distribution = self.distribution
            
            # Aplicar configuración del escenario
            self.time_uncertainty = scenario.get('uncertainty', orig_uncertainty)
            self.distribution = scenario.get('distribution', orig_distribution)
            
            result = self.validate_schedule(schedule, base_travel_times)
            
            # Restaurar configuración
            self.time_uncertainty = orig_uncertainty
            self.distribution = orig_distribution
            
            results.append(result)
        
        return results
    
    def simulate_travel_times(
        self, 
        base_times: Dict[Tuple[str, str], float]
    ) -> Dict[Tuple[str, str], float]:
        """
        Simular tiempos de viaje con incertidumbre.
        
        Distribución lognormal es más realista para tiempos de viaje
        (siempre positiva, cola larga para tráfico pesado).
        """
        simulated = {}
        
        for key, base in base_times.items():
            if self.distribution == "lognormal":
                # Lognormal: media=base, sigma=uncertainty
                sigma = self.time_uncertainty
                mu = math.log(base) - (sigma ** 2) / 2
                simulated[key] = random.lognormvariate(mu, sigma)
            elif self.distribution == "normal":
                # Normal truncada en 0
                variation = base * self.time_uncertainty
                time_val = random.gauss(base, variation)
                simulated[key] = max(1, time_val)  # Mínimo 1 minuto
            elif self.distribution == "uniform":
                # Uniforme: +/- uncertainty%
                variation = base * self.time_uncertainty
                time_val = base + random.uniform(-variation, variation)
                simulated[key] = max(1, time_val)
            else:
                raise ValueError(f"Distribución no soportada: {self.distribution}")
        
        return simulated
    
    def get_robustness_grade(self, result: SimulationResult) -> str:
        """
        Obtener grado de robustez basado en factibilidad.
        
        Returns:
            'A' (>95%), 'B' (>85%), 'C' (>70%), 'D' (>50%), 'F' (<50%)
        """
        rate = result.feasibility_rate
        if rate >= 0.95:
            return 'A'
        elif rate >= 0.85:
            return 'B'
        elif rate >= 0.70:
            return 'C'
        elif rate >= 0.50:
            return 'D'
        else:
            return 'F'
    
    def get_recommendation(self, result: SimulationResult) -> str:
        """Obtener recomendación basada en el resultado."""
        grade = self.get_robustness_grade(result)
        
        recommendations = {
            'A': "ACEPTAR: Schedule muy robusto (>95% factibilidad)",
            'B': "ACEPTAR CON PRECAUCIÓN: Schedule robusto pero con margen de mejora",
            'C': "REVISAR: Schedule aceptable pero vulnerable a retrasos",
            'D': "RECHAZAR: Schedule poco robusto, necesita ajustes",
            'F': "RECHAZAR: Schedule inaceptable, requiere re-optimización"
        }
        
        return recommendations.get(grade, "REVISAR")
    
    def run_single_simulation(
        self,
        schedule: List[BusSchedule],
        base_travel_times: Dict[Tuple[str, str], float],
        sim_id: int = 0
    ) -> Dict[str, Any]:
        """
        Ejecutar una sola simulación y retornar datos detallados.
        
        Incluye métricas para visualización 3D:
        - x: Desviación de tiempos (variación respecto a tiempos base)
        - y: Duración total del schedule
        - z: Factibilidad (1 = factible, 0 = infactible)
        
        Args:
            schedule: Schedule a validar
            base_travel_times: Tiempos base de viaje
            sim_id: Identificador de simulación (para tracking)
            
        Returns:
            Diccionario con resultados de simulación incluyendo datos para scatter 3D
        """
        # Simular tiempos de viaje con incertidumbre
        simulated_times = self.simulate_travel_times(base_travel_times)
        
        # Verificar factibilidad con tiempos simulados
        is_feasible, violations = check_schedule_feasibility(schedule, simulated_times)
        
        # Calcular métricas para ejes 3D
        # X: Desviación de tiempos (variación promedio respecto a base)
        time_deviation = self._calculate_time_deviation(base_travel_times, simulated_times)
        
        # Y: Duración total del schedule
        duration = self._calculate_schedule_duration(schedule, simulated_times)
        
        return {
            "id": sim_id,
            "x": round(time_deviation, 4),   # Desviación tiempo (para eje X)
            "y": round(duration, 2),          # Duración total (para eje Y)
            "z": 1 if is_feasible else 0,     # Factibilidad (para eje Z/color)
            "feasible": is_feasible,
            "violations": violations,
            "simulated_times": simulated_times
        }
    
    def _calculate_time_deviation(
        self,
        base_times: Dict[Tuple[str, str], float],
        simulated_times: Dict[Tuple[str, str], float]
    ) -> float:
        """
        Calcular desviación promedio entre tiempos base y simulados.
        
        Args:
            base_times: Tiempos base de viaje
            simulated_times: Tiempos simulados
            
        Returns:
            Desviación promedio (ratio)
        """
        if not base_times:
            return 0.0
        
        deviations = []
        for key, base in base_times.items():
            simulated = simulated_times.get(key, base)
            if base > 0:
                deviation = abs(simulated - base) / base
                deviations.append(deviation)
        
        return sum(deviations) / len(deviations) if deviations else 0.0
    
    def _calculate_schedule_duration(
        self,
        schedule: List[BusSchedule],
        travel_times: Dict[Tuple[str, str], float]
    ) -> float:
        """
        Calcular duración total del schedule incluyendo tiempos de viaje.
        
        Args:
            schedule: Lista de BusSchedule
            travel_times: Tiempos de viaje entre rutas
            
        Returns:
            Duración total en minutos
        """
        total_duration = 0.0
        
        for bus in schedule:
            items = sorted(bus.items, key=lambda x: time_to_minutes(x.start_time))
            
            for i, item in enumerate(items):
                # Duración de la ruta
                duration = time_to_minutes(item.end_time) - time_to_minutes(item.start_time)
                total_duration += max(0, duration)
                
                # Tiempo de viaje a siguiente ruta (si existe)
                if i < len(items) - 1:
                    next_item = items[i + 1]
                    tt_key = (item.route_id, next_item.route_id)
                    travel_time = travel_times.get(tt_key, 15.0)
                    total_duration += travel_time
        
        return total_duration
    
    def validate_schedule_streaming(
        self,
        schedule: List[BusSchedule],
        base_travel_times: Dict[Tuple[str, str], float],
        batch_size: int = 50,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ) -> SimulationResult:
        """
        Validar schedule con soporte para streaming de progreso.
        
        Similar a validate_schedule pero permite reportar progreso
        mediante un callback que se llama cada batch_size simulaciones.
        
        Args:
            schedule: Schedule a validar
            base_travel_times: Tiempos base de viaje
            batch_size: Tamaño del batch para reportar progreso
            progress_callback: Función callback(completed, total, feasible_rate)
            
        Returns:
            SimulationResult con métricas de robustez
        """
        feasible_count = 0
        violation_counts = []
        violation_distribution: Dict[int, int] = {}
        scenarios = []
        
        for batch_start in range(0, self.n_simulations, batch_size):
            batch_end = min(batch_start + batch_size, self.n_simulations)
            
            for i in range(batch_start, batch_end):
                # Ejecutar simulación individual
                scenario = self.run_single_simulation(
                    schedule, base_travel_times, i
                )
                
                scenarios.append(scenario)
                
                if scenario["feasible"]:
                    feasible_count += 1
                
                violations = scenario["violations"]
                violation_counts.append(violations)
                violation_distribution[violations] = violation_distribution.get(violations, 0) + 1
            
            # Reportar progreso si hay callback
            if progress_callback:
                completed = min(batch_end, self.n_simulations)
                feasible_rate = feasible_count / completed if completed > 0 else 0.0
                progress_callback(completed, self.n_simulations, feasible_rate)
        
        # Calcular métricas finales
        feasibility_rate = feasible_count / self.n_simulations
        avg_violations = statistics.mean(violation_counts) if violation_counts else 0
        worst_case = max(violation_counts) if violation_counts else 0
        
        # Intervalo de confianza 95%
        if len(violation_counts) > 1:
            std_dev = statistics.stdev(violation_counts)
            margin = 1.96 * std_dev / (self.n_simulations ** 0.5)
            ci = (avg_violations - margin, avg_violations + margin)
        else:
            ci = (avg_violations, avg_violations)
        
        # Guardar escenarios para análisis posterior
        self._last_scenarios = scenarios
        
        return SimulationResult(
            schedule=schedule,
            feasibility_rate=feasibility_rate,
            avg_violations=avg_violations,
            worst_case_violations=worst_case,
            confidence_interval=ci,
            violation_distribution=violation_distribution
        )


def time_to_minutes(t: time) -> int:
    """Convertir time a minutos desde medianoche."""
    return t.hour * 60 + t.minute


def check_schedule_feasibility(
    schedule: List[BusSchedule],
    travel_times: Dict[Tuple[str, str], float]
) -> Tuple[bool, int]:
    """
    Verificar si un schedule es factible con tiempos dados.
    
    Args:
        schedule: Lista de BusSchedule
        travel_times: Diccionario de tiempos de viaje (route_id_i, route_id_j) -> minutos
    
    Returns:
        (is_feasible, n_violations)
    """
    violations = 0
    
    for bus in schedule:
        items = sorted(bus.items, key=lambda x: time_to_minutes(x.start_time))
        
        for i in range(len(items) - 1):
            current = items[i]
            next_item = items[i + 1]
            
            # Tiempo de viaje entre rutas
            tt_key = (current.route_id, next_item.route_id)
            travel_time = travel_times.get(tt_key, 15.0)  # default 15min
            
            # Verificar si hay tiempo suficiente
            end_current = time_to_minutes(current.end_time)
            start_next = time_to_minutes(next_item.start_time)
            
            buffer = start_next - end_current
            
            # Si el buffer es menor que el tiempo de viaje, hay violación
            if buffer < travel_time:
                violations += 1
    
    return violations == 0, violations


def extract_travel_times_from_schedule(
    schedule: List[BusSchedule],
    default_time: float = 15.0
) -> Dict[Tuple[str, str], float]:
    """
    Extraer tiempos de viaje de un schedule.
    
    Usa los deadhead_minutes registrados en los items del schedule.
    Si no hay deadhead, usa el valor por defecto.
    
    Args:
        schedule: Schedule con items que tienen deadhead_minutes
        default_time: Tiempo por defecto si no hay deadhead
    
    Returns:
        Diccionario de tiempos de viaje (route_id_i, route_id_j) -> minutos
    """
    travel_times = {}
    
    for bus in schedule:
        items = bus.items
        for i in range(len(items) - 1):
            current = items[i]
            next_item = items[i + 1]
            
            key = (current.route_id, next_item.route_id)
            # Usar deadhead real del schedule (calculado por el optimizador)
            # Si no hay deadhead registrado (>0), usar el default
            travel_times[key] = next_item.deadhead_minutes if next_item.deadhead_minutes > 0 else default_time
    
    return travel_times


def estimate_base_travel_times(
    routes: List[Route],
    osrm_provider: Optional[Callable] = None
) -> Dict[Tuple[str, str], float]:
    """
    Estimar tiempos base de viaje entre rutas.
    
    Args:
        routes: Lista de rutas
        osrm_provider: Función opcional para obtener tiempos reales de OSRM
    
    Returns:
        Diccionario de tiempos estimados
    """
    from optimizer_v6 import haversine_km
    
    FALLBACK_SPEED_KMH = 50
    DEADHEAD_BUFFER = 3
    
    travel_times = {}
    
    for i, route_a in enumerate(routes):
        for j, route_b in enumerate(routes):
            if i == j:
                continue
            
            # Obtener coordenadas de fin de A y inicio de B
            if route_a.stops and route_b.stops:
                end_a = route_a.stops[-1]
                start_b = route_b.stops[0]
                
                # Intentar usar OSRM si está disponible
                if osrm_provider:
                    try:
                        tt = osrm_provider(end_a.lat, end_a.lon, start_b.lat, start_b.lon)
                        if tt is not None:
                            travel_times[(route_a.id, route_b.id)] = tt + DEADHEAD_BUFFER
                            continue
                    except Exception:
                        pass
                
                # Fallback a haversine
                km = haversine_km(end_a.lat, end_a.lon, start_b.lat, start_b.lon)
                minutes = max(5, int((km / FALLBACK_SPEED_KMH) * 60) + DEADHEAD_BUFFER)
                travel_times[(route_a.id, route_b.id)] = float(minutes)
    
    return travel_times


# =============================================================================
# API Integration Helper Functions
# =============================================================================

def create_validation_report(
    schedule: List[BusSchedule],
    routes: List[Route],
    n_simulations: int = 1000,
    uncertainty_levels: List[float] = None
) -> Dict:
    """
    Crear reporte completo de validación Monte Carlo.
    
    Args:
        schedule: Schedule a validar
        routes: Rutas originales (para estimar tiempos base)
        n_simulations: Número de simulaciones por escenario
        uncertainty_levels: Niveles de incertidumbre a probar
    
    Returns:
        Diccionario con reporte completo
    """
    if uncertainty_levels is None:
        uncertainty_levels = [0.1, 0.2, 0.3]  # 10%, 20%, 30%
    
    # Estimar tiempos base
    base_times = estimate_base_travel_times(routes)
    
    validator = MonteCarloValidator(n_simulations=n_simulations)
    
    # Probar múltiples niveles de incertidumbre
    scenario_results = []
    for uncertainty in uncertainty_levels:
        validator.time_uncertainty = uncertainty
        result = validator.validate_schedule(schedule, base_times)
        
        scenario_results.append({
            "uncertainty": f"{uncertainty:.0%}",
            "result": result.to_dict(),
            "grade": validator.get_robustness_grade(result),
            "recommendation": validator.get_recommendation(result)
        })
    
    # Resultado con incertidumbre estándar (20%)
    validator.time_uncertainty = 0.2
    standard_result = validator.validate_schedule(schedule, base_times)
    
    return {
        "summary": {
            "n_simulations": n_simulations,
            "n_buses": len(schedule),
            "n_routes": sum(len(bus.items) for bus in schedule),
            "overall_grade": validator.get_robustness_grade(standard_result),
            "overall_recommendation": validator.get_recommendation(standard_result)
        },
        "standard_result": standard_result.to_dict(),
        "scenario_analysis": scenario_results,
        "timestamp": datetime.now().isoformat()
    }


# Import para la función create_validation_report
from datetime import datetime


__all__ = [
    'MonteCarloValidator',
    'SimulationResult', 
    'check_schedule_feasibility',
    'extract_travel_times_from_schedule',
    'estimate_base_travel_times',
    'create_validation_report'
]
