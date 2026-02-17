"""
Validador de horarios manuales en tiempo real.

Este modulo proporciona validacion instantanea de horarios manuales,
verificando que las conexiones entre rutas sean viables usando OSRM.
"""

import asyncio
import time as time_module
import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import time, timedelta

logger = logging.getLogger(__name__)


class OSRMService:
    """
    Servicio wrapper para OSRM que proporciona cache y manejo de errores.
    """
    
    def __init__(self, cache_ttl_seconds: int = 3600):
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = cache_ttl_seconds
        self._cache_timestamps: Dict[str, float] = {}
        
    def _get_cache_key(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float]
    ) -> str:
        """Genera clave de cache para una conexion."""
        return f"{origin[0]:.5f},{origin[1]:.5f}|{destination[0]:.5f},{destination[1]:.5f}"
    
    async def get_travel_time(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float]
    ) -> Optional[float]:
        """
        Obtiene tiempo de viaje entre dos puntos usando OSRM.
        
        Args:
            origin: (lat, lon) del origen
            destination: (lat, lon) del destino
            
        Returns:
            Tiempo en minutos o None si falla
        """
        cache_key = self._get_cache_key(origin, destination)
        
        # Verificar cache
        if cache_key in self._cache:
            timestamp = self._cache_timestamps.get(cache_key, 0)
            if time_module.time() - timestamp < self._cache_ttl:
                logger.debug(f"[OSRM Cache] Hit for {cache_key}")
                return self._cache[cache_key]
            else:
                # Expirado
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
        
        try:
            # Intentar importar desde router_service
            try:
                from backend.router_service import get_real_travel_time
            except ImportError:
                from router_service import get_real_travel_time
            
            # Avoid blocking the event loop on network-bound OSRM calls.
            travel_time = await asyncio.to_thread(
                get_real_travel_time,
                origin[0], origin[1],
                destination[0], destination[1]
            )
            
            if travel_time is not None:
                # Guardar en cache
                self._cache[cache_key] = float(travel_time)
                self._cache_timestamps[cache_key] = time_module.time()
                return float(travel_time)
            
            # Fallback: estimacion con distancia Haversine a velocidad promedio
            estimated = self._estimate_travel_time(origin, destination)
            logger.warning(f"[OSRM] Usando estimacion para {cache_key}: {estimated:.1f}min")
            return estimated
            
        except Exception as e:
            logger.error(f"[OSRM] Error obteniendo tiempo: {e}")
            # Fallback silencioso
            return self._estimate_travel_time(origin, destination)
    
    def _estimate_travel_time(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float]
    ) -> float:
        """
        Estima tiempo de viaje usando distancia Haversine.
        Asume velocidad promedio de 30 km/h en ciudad.
        """
        import math
        
        R = 6371  # Radio de la Tierra en km
        
        lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
        lat2, lon2 = math.radians(destination[0]), math.radians(destination[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        distance_km = R * c
        
        # 30 km/h promedio + 20% overhead
        speed_kmh = 30
        time_hours = distance_km / speed_kmh
        time_minutes = time_hours * 60 * 1.2
        
        return max(5.0, time_minutes)  # Minimo 5 minutos
    
    def clear_cache(self) -> None:
        """Limpia la cache de validaciones."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("[OSRM] Cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Retorna estadisticas de la cache."""
        now = time_module.time()
        valid_entries = sum(
            1 for k, v in self._cache_timestamps.items()
            if now - v < self._cache_ttl
        )
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self._cache) - valid_entries
        }


class ManualScheduleValidator:
    """
    Validador de horarios manuales en tiempo real.
    
    Valida que las conexiones entre rutas tengan suficiente tiempo,
    usando OSRM para calcular tiempos de viaje reales.
    """
    
    # Umbrales de buffer (en minutos)
    MIN_BUFFER_RECOMMENDED = 5.0
    TIGHT_BUFFER_THRESHOLD = 10.0
    
    def __init__(self, osrm_service: Optional[OSRMService] = None):
        self.osrm_service = osrm_service or OSRMService()
        self.validation_cache: Dict[str, Any] = {}
        
    def _time_to_minutes(self, t: time) -> int:
        """Convierte time a minutos desde medianoche."""
        return t.hour * 60 + t.minute
    
    def _minutes_to_time(self, minutes: int) -> time:
        """Convierte minutos desde medianoche a time."""
        minutes = minutes % (24 * 60)
        return time(hour=minutes // 60, minute=minutes % 60)
    
    def _time_diff(self, t1: time, t2: time) -> float:
        """Calcula diferencia en minutos entre dos tiempos (t2 - t1)."""
        return self._time_to_minutes(t2) - self._time_to_minutes(t1)
    
    def _add_minutes(self, t: time, minutes: float) -> time:
        """Suma minutos a un tiempo."""
        total = self._time_to_minutes(t) + int(minutes)
        return self._minutes_to_time(total)
    
    def _get_validation_cache_key(
        self, 
        route_a: Any, 
        route_b: Any
    ) -> str:
        """Genera clave de cache para validacion."""
        return f"{route_a.id}:{route_a.end_time}->{route_b.id}:{route_b.start_time}"
    
    async def validate_connection(
        self, 
        route_a: Any, 
        route_b: Any
    ) -> Any:
        """
        Valida una conexion especifica entre dos rutas.
        
        Args:
            route_a: Ruta actual (debe tener end_time, end_location)
            route_b: Siguiente ruta (debe tener start_time, start_location)
            
        Returns:
            ConnectionValidationResult con el resultado detallado
        """
        try:
            from backend.models.validation_result import (
                ConnectionValidationResult, RouteIssue, IssueType
            )
        except ImportError:
            from models.validation_result import (
                ConnectionValidationResult, RouteIssue, IssueType
            )
        
        start_time = time_module.time()
        
        # Calcular tiempo disponible
        time_available = self._time_diff(route_a.end_time, route_b.start_time)
        
        # Si es negativo, hay solapamiento
        if time_available < 0:
            issue = RouteIssue(
                route_a=route_a.id,
                route_b=route_b.id,
                issue_type=IssueType.OVERLAPPING_ROUTES,
                message=f"Las rutas se solapan: {abs(time_available):.0f} minutos",
                suggestion="Ajusta los horarios para evitar solapamiento",
                severity="error",
                time_available=time_available,
                travel_time=0.0,
                buffer_minutes=time_available
            )
            return ConnectionValidationResult(
                is_compatible=False,
                buffer_minutes=time_available,
                travel_time=0.0,
                time_available=time_available,
                issue=issue
            )
        
        # Obtener tiempo de viaje desde OSRM
        travel_time = await self.osrm_service.get_travel_time(
            route_a.end_location,
            route_b.start_location
        )
        
        if travel_time is None:
            travel_time = 15.0  # Default fallback
        
        # Calcular buffer
        buffer = time_available - travel_time
        
        # Determinar compatibilidad y generar issue si aplica
        is_compatible = buffer >= 0
        issue = None
        suggested_start = None
        
        if buffer < 0:
            issue = RouteIssue(
                route_a=route_a.id,
                route_b=route_b.id,
                issue_type=IssueType.INSUFFICIENT_TIME,
                message=f"Faltan {abs(buffer):.1f} minutos",
                suggestion=f"Necesitas {travel_time + self.MIN_BUFFER_RECOMMENDED:.0f} min minimo",
                severity="error",
                time_available=time_available,
                travel_time=travel_time,
                buffer_minutes=buffer
            )
            # Sugerir hora alternativa
            min_start = self._add_minutes(
                route_a.end_time, 
                travel_time + self.MIN_BUFFER_RECOMMENDED
            )
            suggested_start = min_start.strftime("%H:%M")
            
        elif buffer < self.MIN_BUFFER_RECOMMENDED:
            issue = RouteIssue(
                route_a=route_a.id,
                route_b=route_b.id,
                issue_type=IssueType.TIGHT_BUFFER,
                message=f"Buffer muy justo: {buffer:.1f} min",
                suggestion=f"Considera {self.MIN_BUFFER_RECOMMENDED:.0f}-{self.TIGHT_BUFFER_THRESHOLD:.0f} min de margen",
                severity="warning",
                time_available=time_available,
                travel_time=travel_time,
                buffer_minutes=buffer
            )
        
        elapsed = time_module.time() - start_time
        logger.debug(f"[Validate] {route_a.id} -> {route_b.id}: {elapsed*1000:.1f}ms")
        
        return ConnectionValidationResult(
            is_compatible=is_compatible,
            buffer_minutes=buffer,
            travel_time=travel_time,
            time_available=time_available,
            suggested_start=suggested_start,
            issue=issue
        )
    
    async def validate_bus_schedule(
        self, 
        bus_routes: List[Any]
    ) -> Any:
        """
        Valida todas las conexiones de un bus.
        
        Args:
            bus_routes: Lista de rutas asignadas al bus (ordenadas por tiempo)
            
        Returns:
            ValidationResult con el resultado completo
        """
        try:
            from backend.models.validation_result import ValidationResult, RouteIssue
        except ImportError:
            from models.validation_result import ValidationResult, RouteIssue
        
        issues: List[RouteIssue] = []
        total_travel_time = 0.0
        buffers = []
        
        # Ordenar por hora de inicio si no estan ordenadas
        sorted_routes = sorted(
            bus_routes, 
            key=lambda r: self._time_to_minutes(r.start_time)
        )
        
        for i in range(len(sorted_routes) - 1):
            current = sorted_routes[i]
            next_route = sorted_routes[i + 1]
            
            result = await self.validate_connection(current, next_route)
            
            total_travel_time += result.travel_time
            buffers.append(result.buffer_minutes)
            
            if result.issue:
                issues.append(result.issue)
        
        # Calcular estadisticas de buffer
        buffer_stats = {}
        if buffers:
            buffer_stats = {
                "min": round(min(buffers), 1),
                "max": round(max(buffers), 1),
                "avg": round(sum(buffers) / len(buffers), 1),
                "negative_count": sum(1 for b in buffers if b < 0),
                "tight_count": sum(1 for b in buffers if 0 <= b < self.MIN_BUFFER_RECOMMENDED)
            }
        
        # Calcular puntaje de eficiencia
        efficiency = self.calculate_efficiency(sorted_routes, buffers)
        
        return ValidationResult(
            is_valid=len(issues) == 0 or all(i.severity != "error" for i in issues),
            issues=issues,
            total_travel_time=total_travel_time,
            efficiency_score=efficiency,
            buffer_stats=buffer_stats
        )
    
    def calculate_efficiency(
        self, 
        bus_routes: List[Any], 
        buffers: Optional[List[float]] = None
    ) -> float:
        """
        Calcula un puntaje de eficiencia para el horario (0-100).
        
        Considera:
        - Numero de rutas encadenadas
        - Buffers apropiados (ni muy cortos ni muy largos)
        - Uso eficiente del tiempo
        """
        if not bus_routes:
            return 0.0
        
        if buffers is None:
            # No podemos calcular sin buffers
            return 50.0
        
        # Puntaje base por numero de conexiones
        n_connections = len(buffers)
        if n_connections == 0:
            return 50.0
        
        # Puntaje por buffers optimos (entre 5-15 minutos)
        optimal_buffer_range = (5.0, 15.0)
        buffer_scores = []
        
        for buffer in buffers:
            if buffer < 0:
                buffer_scores.append(0)  # Buffer negativo = 0 puntos
            elif buffer < optimal_buffer_range[0]:
                # Buffer muy corto, escala lineal 0-80
                score = (buffer / optimal_buffer_range[0]) * 80
                buffer_scores.append(score)
            elif buffer <= optimal_buffer_range[1]:
                # Buffer optimo
                buffer_scores.append(100)
            else:
                # Buffer muy largo, penalizacion suave
                excess = buffer - optimal_buffer_range[1]
                score = max(50, 100 - excess * 2)
                buffer_scores.append(score)
        
        avg_buffer_score = sum(buffer_scores) / len(buffer_scores)
        
        # Bonus por multiples conexiones (hasta 4)
        connection_bonus = min(n_connections * 5, 20)
        
        # Calcular puntaje final
        efficiency = (avg_buffer_score * 0.8) + connection_bonus
        
        return min(100.0, max(0.0, efficiency))
    
    def suggest_alternative_time(
        self, 
        current_route: Any, 
        next_route: Any, 
        travel_time: float,
        prefer_earlier: bool = False
    ) -> Any:
        """
        Sugiere horarios alternativos si hay conflicto.
        
        Args:
            current_route: Ruta actual
            next_route: Ruta siguiente (la que se quiere ajustar)
            travel_time: Tiempo de viaje entre rutas
            prefer_earlier: Si se prefiere horario mas temprano
            
        Returns:
            SuggestionResult con sugerencias
        """
        try:
            from backend.models.validation_result import SuggestionResult
        except ImportError:
            from models.validation_result import SuggestionResult
        
        min_start = self._add_minutes(
            current_route.end_time,
            travel_time + self.MIN_BUFFER_RECOMMENDED
        )
        
        # Calcular hora de termino si tenemos duracion
        suggested_end = None
        duration = self._time_diff(next_route.start_time, next_route.end_time)
        if duration > 0:
            suggested_end = self._add_minutes(min_start, duration)
        
        # Generar alternativas
        alternatives = []
        for extra_minutes in [0, 5, 10, 15]:
            alt = self._add_minutes(
                current_route.end_time,
                travel_time + self.MIN_BUFFER_RECOMMENDED + extra_minutes
            )
            alternatives.append(alt)
        
        return SuggestionResult(
            suggested_start_time=min_start,
            suggested_end_time=suggested_end,
            message=f"Prueba iniciar esta ruta a las {min_start.strftime('%H:%M')}",
            alternative_times=alternatives[:3]
        )
    
    async def validate_progressive(
        self, 
        state: Any,
        new_route: Any
    ) -> Any:
        """
        Valida progresivamente al agregar una nueva ruta.
        
        Args:
            state: Estado actual de validacion
            new_route: Nueva ruta a agregar
            
        Returns:
            ValidationResult para todo el horario actualizado
        """
        try:
            from backend.models.validation_result import (
                ValidationResult, RouteIssue, ProgressiveValidationState
            )
        except ImportError:
            from models.validation_result import (
                ValidationResult, RouteIssue, ProgressiveValidationState
            )
        
        # Agregar ruta al estado
        state.add_route(new_route)
        
        # Si es la primera ruta, siempre es valida
        if len(state.routes) == 1:
            return ValidationResult(
                is_valid=True,
                issues=[],
                total_travel_time=0.0,
                efficiency_score=50.0
            )
        
        # Validar solo la ultima conexion
        prev_route = state.routes[-2]
        connection_result = await self.validate_connection(prev_route, new_route)
        
        # Actualizar estado
        state.total_travel_time += connection_result.travel_time
        if connection_result.issue:
            state.cumulative_issues.append(connection_result.issue)
        state.last_validated_index = len(state.routes) - 1
        
        # Recalcular eficiencia
        buffers = []
        for i in range(len(state.routes) - 1):
            time_avail = self._time_diff(
                state.routes[i].end_time,
                state.routes[i + 1].start_time
            )
            # Estimacion rapida del buffer
            buffers.append(time_avail - connection_result.travel_time)
        
        efficiency = self.calculate_efficiency(state.routes, buffers)
        
        # Determinar si es valido
        has_errors = any(i.severity == "error" for i in state.cumulative_issues)
        
        return ValidationResult(
            is_valid=not has_errors,
            issues=state.cumulative_issues,
            total_travel_time=state.total_travel_time,
            efficiency_score=efficiency,
            buffer_stats={"current_buffer": connection_result.buffer_minutes}
        )
    
    def clear_cache(self) -> None:
        """Limpia todas las caches del validador."""
        self.validation_cache.clear()
        self.osrm_service.clear_cache()
        logger.info("[Validator] All caches cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estadisticas de las caches."""
        return {
            "validation_cache_entries": len(self.validation_cache),
            "osrm_cache": self.osrm_service.get_cache_stats()
        }
