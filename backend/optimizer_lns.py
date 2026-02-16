"""
Large Neighborhood Search (LNS) - Tutti Route Optimizer
=======================================================

FASE 3.2: Large Neighborhood Search (LNS)

Metaheurística para mejorar soluciones 5-15% sobre greedy actual.

Estrategia:
1. Empezar con solución inicial (greedy/ILP)
2. Destruir parte de la solución (remove routes)
3. Reconstruir con ILP/greedy
4. Aceptar si mejora
5. Repetir

Basado en el paper "Large Neighborhood Search" by Shaw (1998)
y adaptado para el problema de scheduling de buses escolares.
"""

import random
import logging
import math
import time as time_module
from typing import List, Callable, Dict, Tuple, Optional, Set, Any
from copy import deepcopy
from enum import Enum
from dataclasses import dataclass

from models import Route, BusSchedule, ScheduleItem
from optimizer_multi import (
    MultiObjectiveOptimizer, 
    ObjectiveWeights, 
    ScheduleMetrics
)
from optimizer_v6 import (
    optimize_v6, prepare_jobs, precompute_block_travel_matrix,
    build_block_chains, merge_all_blocks, local_search_improve,
    build_full_schedule, RouteJob, ChainedBus, to_minutes, from_minutes,
    coords_valid, haversine_travel_minutes,
    MIN_CONNECTION_BUFFER_MINUTES, DEADHEAD_BUFFER_MINUTES
)
from router_service import get_real_travel_time

logger = logging.getLogger(__name__)


class DestroyStrategy(Enum):
    """Estrategias para la fase de destrucción."""
    RANDOM = "random"
    WORST = "worst"
    RELATED = "related"
    CLUSTER = "cluster"
    SHAW = "shaw"


class RepairStrategy(Enum):
    """Estrategias para la fase de reparación."""
    GREEDY = "greedy"
    REGRET = "regret"
    ILP_SUBPROBLEM = "ilp"


@dataclass
class LNSConfig:
    """Configuración para el algoritmo LNS."""
    destroy_strategy: DestroyStrategy = DestroyStrategy.WORST
    repair_strategy: RepairStrategy = RepairStrategy.GREEDY
    destroy_rate: float = 0.3           # Porcentaje de rutas a destruir
    min_destroy_rate: float = 0.1       # Mínimo de rutas a destruir
    max_destroy_rate: float = 0.5       # Máximo de rutas a destruir
    max_iterations: int = 100           # Iteraciones máximas
    max_no_improvement: int = 20        # Iteraciones sin mejora para parar
    time_limit_seconds: float = 300.0   # Límite de tiempo total
    cooling_rate: float = 0.95          # Tasa de enfriamiento (SA)
    initial_temperature: float = 100.0  # Temperatura inicial (SA)
    adaptive_destroy: bool = True       # Ajustar dinámicamente destroy_rate
    verbose: bool = True


class LNSOptimizer:
    """
    Large Neighborhood Search optimizer para scheduling de buses.
    
    Mejora soluciones iniciales mediante destrucción controlada
    y reconstrucción inteligente.
    """
    
    def __init__(
        self,
        weights: Optional[ObjectiveWeights] = None,
        config: Optional[LNSConfig] = None
    ):
        """
        Inicializar LNS optimizer.
        
        Args:
            weights: Pesos para función objetivo multi-criterio
            config: Configuración del algoritmo
        """
        self.weights = weights or ObjectiveWeights()
        self.config = config or LNSConfig()
        self.evaluator = MultiObjectiveOptimizer(self.weights)
        self.history: List[Dict[str, Any]] = []
        
        # Estado interno
        self._iteration = 0
        self._no_improvement_count = 0
        self._temperature = self.config.initial_temperature
        self._current_destroy_rate = self.config.destroy_rate
        self._connection_requirements_cache: Dict[str, int] = {}

    @staticmethod
    def _to_minutes(value: Any) -> int:
        if value is None:
            return 0
        if hasattr(value, "hour") and hasattr(value, "minute"):
            return int(value.hour) * 60 + int(value.minute)
        if isinstance(value, str):
            parts = value.split(":")
            if len(parts) >= 2:
                try:
                    return int(parts[0]) * 60 + int(parts[1])
                except Exception:
                    return 0
        return 0

    @staticmethod
    def _next_bus_id(schedule: List[BusSchedule]) -> str:
        max_num = 0
        for bus in schedule:
            bus_id = str(getattr(bus, "bus_id", "") or "")
            if bus_id.upper().startswith("B"):
                try:
                    max_num = max(max_num, int(bus_id[1:]))
                except Exception:
                    continue
        return f"B{max_num + 1:03d}"

    def _normalize_bus_ids(self, schedule: List[BusSchedule]) -> List[BusSchedule]:
        normalized = [bus for bus in schedule if getattr(bus, "items", None)]
        normalized.sort(
            key=lambda bus: min(
                (self._to_minutes(item.start_time) for item in bus.items),
                default=24 * 60,
            )
        )
        for idx, bus in enumerate(normalized, start=1):
            bus.bus_id = f"B{idx:03d}"
        return normalized
    
    def optimize(
        self,
        routes: List[Route],
        initial_schedule: Optional[List[BusSchedule]] = None,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        use_ml_assignment: bool = True,
    ) -> List[BusSchedule]:
        """
        Ejecutar LNS para mejorar la solución.
        
        Args:
            routes: Rutas a optimizar
            initial_schedule: Solución inicial (opcional, usa optimize_v6 si None)
            progress_callback: Callback para reportar progreso
            use_ml_assignment: Activar scoring ML en el optimizador base V6
            
        Returns:
            Mejor schedule encontrado
        """
        start_time = time_module.time()
        
        def report_progress(phase: str, progress: int, message: str):
            """Helper para reportar progreso."""
            if self.config.verbose:
                logger.info(f"[LNS] {phase}: {progress}% - {message}")
            if progress_callback:
                try:
                    progress_callback(phase, progress, message)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")
        
        # 1. Solución inicial
        report_progress("init", 0, "Generando solución inicial...")
        
        if initial_schedule is None:
            current = optimize_v6(
                routes,
                progress_callback=None,
                use_ml_assignment=use_ml_assignment,
            )
        else:
            current = deepcopy(initial_schedule)
        
        current_score = self.evaluator.evaluate_schedule(current)
        best = deepcopy(current)
        best_score = current_score
        
        # Preparar datos de bloques para reparación
        blocks = prepare_jobs(routes)
        block_tt = {}
        for b in [1, 2, 3, 4]:
            is_entry = b in (1, 3)
            block_tt[b] = precompute_block_travel_matrix(blocks[b], is_entry) if blocks[b] else {}
        
        report_progress("init", 10, f"Solución inicial: {len(current)} buses, score={current_score:.2f}")
        
        # 2. Bucle principal LNS
        self._iteration = 0
        self._no_improvement_count = 0
        self._temperature = self.config.initial_temperature
        
        while self._iteration < self.config.max_iterations:
            # Verificar tiempo límite
            elapsed = time_module.time() - start_time
            if elapsed > self.config.time_limit_seconds:
                report_progress("lns", 100, f"Tiempo límite alcanzado ({elapsed:.1f}s)")
                break
            
            # Calcular progreso
            progress = 10 + int((self._iteration / self.config.max_iterations) * 80)
            report_progress(
                "lns_iterating", 
                progress, 
                f"Iteración {self._iteration}/{self.config.max_iterations} - "
                f"Mejor: {len(best)} buses (score={best_score:.2f})"
            )
            
            # 2.1 Destruir
            destroyed, removed_routes = self._destroy(current)
            
            # 2.2 Reparar
            repaired = self._repair(destroyed, removed_routes, blocks, block_tt)
            repaired_score = self.evaluator.evaluate_schedule(repaired)
            
            # 2.3 Decidir si aceptar
            delta = repaired_score - current_score
            
            if delta < 0:
                # Mejora: aceptar
                current = repaired
                current_score = repaired_score
                self._no_improvement_count = 0
                
                if repaired_score < best_score:
                    best = deepcopy(repaired)
                    best_score = repaired_score
                    report_progress(
                        "lns_improved", 
                        progress, 
                        f"Nueva mejor solución: {len(best)} buses (score={best_score:.2f})"
                    )
            else:
                # No mejora: aceptar con probabilidad (Simulated Annealing)
                acceptance_prob = math.exp(-delta / self._temperature) if self._temperature > 0 else 0
                if random.random() < acceptance_prob:
                    current = repaired
                    current_score = repaired_score
                
                self._no_improvement_count += 1
            
            # 2.4 Actualizar temperatura
            self._temperature *= self.config.cooling_rate
            
            # 2.5 Adaptar destroy rate si está habilitado
            if self.config.adaptive_destroy:
                self._adapt_destroy_rate()
            
            # Guardar en historial
            self.history.append({
                "iteration": self._iteration,
                "current_score": current_score,
                "best_score": best_score,
                "temperature": self._temperature,
                "destroy_rate": self._current_destroy_rate,
                "accepted": delta < 0 or (delta >= 0 and random.random() < acceptance_prob)
            })
            
            self._iteration += 1
            
            # 2.6 Early stopping
            if self._no_improvement_count >= self.config.max_no_improvement:
                report_progress("lns", 95, f"Convergencia tras {self._iteration} iteraciones")
                break
        
        # 3. Resultado final
        best = self._normalize_bus_ids(best)
        report_progress("completed", 100, f"LNS completado: {len(best)} buses (score={best_score:.2f})")

        return best
    
    def _destroy(
        self, 
        schedule: List[BusSchedule]
    ) -> Tuple[List[BusSchedule], List[ScheduleItem]]:
        """
        Destruir parte de la solución según la estrategia configurada.
        
        Args:
            schedule: Schedule actual
            
        Returns:
            Tuple de (schedule destruido, items removidos)
        """
        destroyed = deepcopy(schedule)
        
        # Calcular cuántas rutas remover
        total_routes = sum(len(bus.items) for bus in destroyed)
        n_remove = max(1, int(total_routes * self._current_destroy_rate))
        
        if self.config.destroy_strategy == DestroyStrategy.RANDOM:
            return self._destroy_random(destroyed, n_remove)
        elif self.config.destroy_strategy == DestroyStrategy.WORST:
            return self._destroy_worst(destroyed, n_remove)
        elif self.config.destroy_strategy == DestroyStrategy.RELATED:
            return self._destroy_related(destroyed, n_remove)
        else:
            return self._destroy_random(destroyed, n_remove)
    
    def _destroy_random(
        self, 
        schedule: List[BusSchedule], 
        n_remove: int
    ) -> Tuple[List[BusSchedule], List[ScheduleItem]]:
        """Destruir aleatoriamente."""
        removed = []
        all_items = []
        
        # Recolectar todos los items con su bus
        for bus_idx, bus in enumerate(schedule):
            for item in bus.items:
                all_items.append((bus_idx, item))
        
        # Seleccionar aleatoriamente
        to_remove = random.sample(all_items, min(n_remove, len(all_items)))
        
        # Remover
        for bus_idx, item in to_remove:
            removed.append(item)
            schedule[bus_idx].items = [i for i in schedule[bus_idx].items if i.route_id != item.route_id]
        
        # Limpiar buses vacíos
        schedule = [b for b in schedule if b.items]
        
        return schedule, removed
    
    def _destroy_worst(
        self, 
        schedule: List[BusSchedule], 
        n_remove: int
    ) -> Tuple[List[BusSchedule], List[ScheduleItem]]:
        """
        Destruir rutas que más contribuyen al costo.
        
        Estrategia: remover de buses con menos rutas (más difíciles de justificar)
        o de posiciones con alto deadhead.
        """
        removed = []
        
        # Ordenar buses por número de rutas (menos primero)
        buses_sorted = sorted(enumerate(schedule), key=lambda x: len(x[1].items))
        
        removed_count = 0
        for bus_idx, bus in buses_sorted:
            if removed_count >= n_remove:
                break
            
            if not bus.items:
                continue
            
            # Remover algunas rutas de este bus
            n_from_bus = min(len(bus.items), n_remove - removed_count)
            
            # Estrategia: remover las que tienen mayor deadhead
            items_with_deadhead = [(i, item.deadhead_minutes) for i, item in enumerate(bus.items)]
            items_with_deadhead.sort(key=lambda x: -x[1])  # Mayor deadhead primero
            
            indices_to_remove = [i for i, _ in items_with_deadhead[:n_from_bus]]
            
            # Remover en orden inverso para no alterar índices
            for idx in sorted(indices_to_remove, reverse=True):
                removed.append(bus.items[idx])
                del bus.items[idx]
            
            removed_count += n_from_bus
        
        # Limpiar buses vacíos
        schedule = [b for b in schedule if b.items]
        
        return schedule, removed
    
    def _destroy_related(
        self, 
        schedule: List[BusSchedule], 
        n_remove: int
    ) -> Tuple[List[BusSchedule], List[ScheduleItem]]:
        """
        Destruir rutas relacionadas (geográficamente cercanas).
        
        Basado en el concepto de "relatedness" de Shaw (1998).
        """
        removed = []
        
        # Seleccionar semilla aleatoria
        all_items = []
        for bus in schedule:
            for item in bus.items:
                all_items.append(item)
        
        if not all_items:
            return schedule, removed
        
        seed = random.choice(all_items)
        removed.append(seed)
        
        # Remover de su bus
        for bus in schedule:
            bus.items = [i for i in bus.items if i.route_id != seed.route_id]
        
        # Calcular relatedness y remover las más relacionadas
        remaining = []
        for bus in schedule:
            for item in bus.items:
                relatedness = self._calculate_relatedness(seed, item)
                remaining.append((item, relatedness, bus))
        
        # Ordenar por relatedness
        remaining.sort(key=lambda x: x[1])
        
        # Remover las más relacionadas
        for i in range(min(n_remove - 1, len(remaining))):
            item_to_remove = remaining[i][0]
            removed.append(item_to_remove)
            for bus in schedule:
                bus.items = [i for i in bus.items if i.route_id != item_to_remove.route_id]
        
        # Limpiar buses vacíos
        schedule = [b for b in schedule if b.items]
        
        return schedule, removed
    
    def _calculate_relatedness(
        self, 
        item1: ScheduleItem, 
        item2: ScheduleItem
    ) -> float:
        """
        Calcular qué tan relacionadas son dos rutas.
        
        Menor valor = más relacionadas.
        """
        relatedness = 0.0
        
        # Diferencia temporal
        time1 = item1.start_time.hour * 60 + item1.start_time.minute
        time2 = item2.start_time.hour * 60 + item2.start_time.minute
        time_diff = abs(time1 - time2)
        relatedness += time_diff * 0.5
        
        # Distancia geográfica
        if item1.stops and item2.stops:
            loc1_end = (item1.stops[-1].lat, item1.stops[-1].lon)
            loc2_start = (item2.stops[0].lat, item2.stops[0].lon)
            
            from optimizer_v6 import haversine_km as _haversine_km
            dist = _haversine_km(loc1_end[0], loc1_end[1], loc2_start[0], loc2_start[1])
            relatedness += dist * 10
        
        # Mismo tipo
        if item1.type == item2.type:
            relatedness -= 30
        
        # Misma escuela
        if item1.school_name == item2.school_name:
            relatedness -= 50
        
        return max(0, relatedness)
    
    def _repair(
        self,
        partial_schedule: List[BusSchedule],
        unassigned_items: List[ScheduleItem],
        blocks: Dict[int, List[RouteJob]],
        block_tt: Dict[int, Dict[Tuple[int, int], int]]
    ) -> List[BusSchedule]:
        """
        Reconstruir solución insertando items no asignados.
        
        Args:
            partial_schedule: Schedule parcial
            unassigned_items: Items que necesitan ser reinsertados
            blocks: Bloques de jobs
            block_tt: Matrices de tiempos de viaje
            
        Returns:
            Schedule completo reparado
        """
        if self.config.repair_strategy == RepairStrategy.GREEDY:
            return self._repair_greedy(partial_schedule, unassigned_items, blocks, block_tt)
        elif self.config.repair_strategy == RepairStrategy.REGRET:
            return self._repair_regret(partial_schedule, unassigned_items, blocks, block_tt)
        else:
            return self._repair_greedy(partial_schedule, unassigned_items, blocks, block_tt)
    
    def _repair_greedy(
        self,
        partial_schedule: List[BusSchedule],
        unassigned_items: List[ScheduleItem],
        blocks: Dict[int, List[RouteJob]],
        block_tt: Dict[int, Dict[Tuple[int, int], int]]
    ) -> List[BusSchedule]:
        """
        Reparación greedy: insertar cada item en el mejor lugar encontrado.
        """
        repaired = deepcopy(partial_schedule)
        
        # Ordenar items por hora de inicio
        sorted_items = sorted(unassigned_items, key=lambda x: (x.start_time.hour, x.start_time.minute))
        
        for item in sorted_items:
            best_bus_idx = None
            best_position = None
            best_score = float('inf')
            
            # Intentar insertar en buses existentes
            for bus_idx, bus in enumerate(repaired):
                position, score = self._find_best_insertion(bus, item)
                if position is not None and score < best_score:
                    best_score = score
                    best_bus_idx = bus_idx
                    best_position = position
            
            if best_bus_idx is not None:
                # Insertar en bus existente
                bus = repaired[best_bus_idx]
                if best_position == -1:
                    bus.items.append(item)
                else:
                    bus.items.insert(best_position, item)
            else:
                # Crear nuevo bus
                new_bus_id = self._next_bus_id(repaired)
                repaired.append(BusSchedule(bus_id=new_bus_id, items=[item]))
        
        return repaired
    
    def _find_best_insertion(
        self, 
        bus: BusSchedule, 
        item: ScheduleItem
    ) -> Tuple[Optional[int], float]:
        """
        Encontrar la mejor posición para insertar un item en un bus.
        
        Returns:
            Tuple de (posición, score). Posición -1 = al final.
        """
        if not bus.items:
            return (0, 0.0)
        
        # Verificar factibilidad temporal
        item_start = item.start_time.hour * 60 + item.start_time.minute
        item_end = item.end_time.hour * 60 + item.end_time.minute
        
        best_position = None
        best_score = float('inf')
        
        # Probar todas las posiciones
        for pos in range(len(bus.items) + 1):
            # Construir schedule temporal
            temp_items = bus.items[:pos] + [item] + bus.items[pos:]
            
            # Verificar factibilidad
            if self._is_feasible_schedule(temp_items):
                # Calcular score (menor es mejor)
                score = self._evaluate_insertion(temp_items, pos)
                if score < best_score:
                    best_score = score
                    best_position = pos
        
        return (best_position, best_score) if best_position is not None else (None, float('inf'))
    
    def _item_start_location(self, item: ScheduleItem) -> Optional[Tuple[float, float]]:
        """Extract start coordinates from schedule item."""
        if not item.stops:
            return None
        first = item.stops[0]
        if not coords_valid(first.lat, first.lon):
            return None
        return (first.lat, first.lon)

    def _item_end_location(self, item: ScheduleItem) -> Optional[Tuple[float, float]]:
        """Extract end coordinates from schedule item."""
        if not item.stops:
            return None
        last = item.stops[-1]
        if not coords_valid(last.lat, last.lon):
            return None
        return (last.lat, last.lon)

    def _required_connection_minutes(self, current: ScheduleItem, next_item: ScheduleItem) -> int:
        """
        Required minutes between two routes:
        OSRM travel (or fallback) + minimum operational buffer.
        """
        end_loc = self._item_end_location(current)
        start_loc = self._item_start_location(next_item)
        if end_loc is None or start_loc is None:
            return 20 + MIN_CONNECTION_BUFFER_MINUTES

        key = f"{end_loc[0]:.5f},{end_loc[1]:.5f}|{start_loc[0]:.5f},{start_loc[1]:.5f}"
        if key in self._connection_requirements_cache:
            return self._connection_requirements_cache[key]

        osrm_time = get_real_travel_time(end_loc[0], end_loc[1], start_loc[0], start_loc[1])
        if osrm_time is not None:
            required = int(math.ceil(osrm_time)) + MIN_CONNECTION_BUFFER_MINUTES
        else:
            required = haversine_travel_minutes(end_loc[0], end_loc[1], start_loc[0], start_loc[1])
            if MIN_CONNECTION_BUFFER_MINUTES > DEADHEAD_BUFFER_MINUTES:
                required += MIN_CONNECTION_BUFFER_MINUTES - DEADHEAD_BUFFER_MINUTES

        self._connection_requirements_cache[key] = required
        return required

    def _is_feasible_schedule(self, items: List[ScheduleItem]) -> bool:
        """Verificar si una secuencia de items es temporal y operativamente factible."""
        if not items:
            return True

        ordered = sorted(items, key=lambda x: (x.start_time.hour, x.start_time.minute))

        for i in range(len(ordered) - 1):
            current = ordered[i]
            next_item = ordered[i + 1]

            current_end = current.end_time.hour * 60 + current.end_time.minute
            next_start = next_item.start_time.hour * 60 + next_item.start_time.minute
            available = next_start - current_end

            if available < 0:
                return False

            required = self._required_connection_minutes(current, next_item)
            if available < required:
                return False

        return True
    
    def _evaluate_insertion(self, items: List[ScheduleItem], inserted_pos: int) -> float:
        """Evaluar la calidad de una inserción."""
        score = 0.0
        
        # Penalizar deadhead adicional
        if inserted_pos > 0:
            prev_item = items[inserted_pos - 1]
            inserted = items[inserted_pos]
            
            if prev_item.stops and inserted.stops:
                from optimizer_v6 import haversine_km as _haversine_km
                dist = _haversine_km(
                    prev_item.stops[-1].lat, prev_item.stops[-1].lon,
                    inserted.stops[0].lat, inserted.stops[0].lon
                )
                score += dist * self.weights.deadhead_km
        
        if inserted_pos < len(items) - 1:
            inserted = items[inserted_pos]
            next_item = items[inserted_pos + 1]
            
            if inserted.stops and next_item.stops:
                from optimizer_v6 import haversine_km as _haversine_km
                dist = _haversine_km(
                    inserted.stops[-1].lat, inserted.stops[-1].lon,
                    next_item.stops[0].lat, next_item.stops[0].lon
                )
                score += dist * self.weights.deadhead_km
        
        return score
    
    def _repair_regret(
        self,
        partial_schedule: List[BusSchedule],
        unassigned_items: List[ScheduleItem],
        blocks: Dict[int, List[RouteJob]],
        block_tt: Dict[int, Dict[Tuple[int, int], int]]
    ) -> List[BusSchedule]:
        """
        Reparación con Regret-2: considerar segunda mejor opción.
        """
        repaired = deepcopy(partial_schedule)
        remaining = list(unassigned_items)
        
        while remaining:
            best_item_idx = None
            best_regret = -1
            best_insertion = None
            
            # Calcular regret para cada item restante
            for item_idx, item in enumerate(remaining):
                insertions = []
                
                for bus_idx, bus in enumerate(repaired):
                    position, score = self._find_best_insertion(bus, item)
                    if position is not None:
                        insertions.append((bus_idx, position, score))
                
                # También considerar nuevo bus
                insertions.append((-1, 0, self.weights.buses))
                
                if len(insertions) >= 2:
                    # Ordenar por score
                    insertions.sort(key=lambda x: x[2])
                    regret = insertions[1][2] - insertions[0][2]
                    
                    if regret > best_regret:
                        best_regret = regret
                        best_item_idx = item_idx
                        best_insertion = insertions[0]
            
            if best_item_idx is None:
                break
            
            # Insertar el item con mayor regret
            item = remaining.pop(best_item_idx)
            bus_idx, position, _ = best_insertion
            
            if bus_idx == -1:
                # Nuevo bus
                new_bus_id = self._next_bus_id(repaired)
                repaired.append(BusSchedule(bus_id=new_bus_id, items=[item]))
            else:
                # Insertar en bus existente
                bus = repaired[bus_idx]
                if position == -1:
                    bus.items.append(item)
                else:
                    bus.items.insert(position, item)
        
        return repaired
    
    def _adapt_destroy_rate(self):
        """Adaptar el destroy rate basado en el progreso reciente."""
        if len(self.history) < 10:
            return
        
        # Contar mejoras recientes
        recent = self.history[-10:]
        improvements = sum(1 for h in recent if h["accepted"])
        
        if improvements < 3:
            # Pocas mejoras: aumentar diversificación
            self._current_destroy_rate = min(
                self._current_destroy_rate * 1.1,
                self.config.max_destroy_rate
            )
        elif improvements > 7:
            # Muchas mejoras: enfocar en intensificación
            self._current_destroy_rate = max(
                self._current_destroy_rate * 0.9,
                self.config.min_destroy_rate
            )
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Obtener historial de iteraciones."""
        return self.history


def optimize_v6_lns(
    routes: List[Route],
    weights: Optional[ObjectiveWeights] = None,
    use_lns: bool = True,
    progress_callback: Optional[Callable[[str, int, str], None]] = None,
    config: Optional[LNSConfig] = None,
    use_ml_assignment: bool = True,
) -> List[BusSchedule]:
    """
    Optimización V6 con soporte opcional de LNS.
    
    Args:
        routes: Rutas a optimizar
        weights: Pesos para función objetivo multi-criterio
        use_lns: Si es True, usa LNS para mejorar la solución
        progress_callback: Callback de progreso
        config: Configuración LNS (usa default si None)
        use_ml_assignment: Activar scoring ML en el optimizador base V6
        
    Returns:
        Schedule optimizado
    """
    if not use_lns:
        # Solo optimización básica con evaluación multi-objetivo
        schedule = optimize_v6(
            routes,
            progress_callback,
            use_ml_assignment=use_ml_assignment,
        )
        return schedule
    
    # LNS completo
    lns = LNSOptimizer(weights=weights, config=config)
    return lns.optimize(
        routes,
        initial_schedule=None,
        progress_callback=progress_callback,
        use_ml_assignment=use_ml_assignment,
    )


def optimize_multi_objective(
    routes: List[Route],
    weights: Optional[ObjectiveWeights] = None,
    use_lns: bool = True,
    progress_callback: Optional[Callable[[str, int, str], None]] = None,
    use_ml_assignment: bool = True,
) -> Tuple[List[BusSchedule], ScheduleMetrics]:
    """
    Optimización multi-objetivo con métricas detalladas.
    
    Args:
        routes: Rutas a optimizar
        weights: Pesos para función objetivo
        use_lns: Usar LNS para mejorar solución
        progress_callback: Callback de progreso
        
    Returns:
        Tuple de (schedule, métricas)
    """
    schedule = optimize_v6_lns(
        routes,
        weights,
        use_lns,
        progress_callback,
        use_ml_assignment=use_ml_assignment,
    )
    
    optimizer = MultiObjectiveOptimizer(weights)
    metrics = optimizer.calculate_metrics(schedule)
    
    return schedule, metrics


__all__ = [
    'DestroyStrategy',
    'RepairStrategy',
    'LNSConfig',
    'LNSOptimizer',
    'optimize_v6_lns',
    'optimize_multi_objective',
]
