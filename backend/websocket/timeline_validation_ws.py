"""
WebSocket para validación de timeline en tiempo real con OSRM.

Proporciona validación instantánea de compatibilidad entre rutas cuando el usuario
las mueve en el timeline, calculando tiempos de viaje reales con OSRM y cacheando
resultados para respuesta rápida.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, time as dt_time
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class CompatibilityQuality(str, Enum):
    """Calidad de la compatibilidad entre rutas."""
    EXCELLENT = "excellent"    # > 15 minutos de margen
    GOOD = "good"              # 10-15 minutos de margen
    TIGHT = "tight"            # 5-10 minutos de margen
    INCOMPATIBLE = "incompatible"  # < 5 minutos de margen


class TimelineValidationWebSocket:
    """
    WebSocket handler para validación de timeline en tiempo real.
    
    Características:
    - Validación de compatibilidad entre rutas en < 500ms
    - Cache de resultados OSRM para no repetir llamadas
    - Fallback si OSRM no responde
    - Mensajes de error claros al usuario
    - Indicador de "validando..." mientras espera
    """
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.osrm_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl_seconds = 300  # 5 minutos de TTL
        self.validation_states: Dict[str, Dict[str, Any]] = {}
        self._stats = {
            'validations': 0,
            'cache_hits': 0,
            'osrm_calls': 0,
            'fallbacks': 0,
            'errors': 0
        }

    @staticmethod
    def _import_osrm_dependencies():
        """Importa dependencias OSRM con fallback según contexto de ejecución."""
        try:
            from services.osrm_service import get_osrm_service
            from models.validation import Coordinates
        except ImportError:
            from backend.services.osrm_service import get_osrm_service
            from backend.models.validation import Coordinates
        return get_osrm_service, Coordinates
    
    def _get_cache_key(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> str:
        """Genera una clave de cache para coordenadas."""
        return f"{round(start_coords[0], 5)},{round(start_coords[1], 5)}|{round(end_coords[0], 5)},{round(end_coords[1], 5)}"
    
    def _get_from_cache(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> Optional[float]:
        """Obtiene tiempo de viaje del cache si existe y no ha expirado."""
        key = self._get_cache_key(start_coords, end_coords)
        entry = self.osrm_cache.get(key)
        
        if entry is None:
            return None
        
        # Verificar TTL
        if time.time() - entry.get('timestamp', 0) > self.cache_ttl_seconds:
            del self.osrm_cache[key]
            return None
        
        self._stats['cache_hits'] += 1
        return entry['travel_time']
    
    def _set_cache(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float], travel_time: float):
        """Guarda resultado en cache."""
        key = self._get_cache_key(start_coords, end_coords)
        self.osrm_cache[key] = {
            'travel_time': travel_time,
            'timestamp': time.time()
        }
    
    def _clear_expired_cache(self):
        """Limpia entradas expiradas del cache."""
        now = time.time()
        expired_keys = [
            k for k, v in self.osrm_cache.items()
            if now - v.get('timestamp', 0) > self.cache_ttl_seconds
        ]
        for k in expired_keys:
            del self.osrm_cache[k]
    
    def _get_quality(self, buffer_minutes: float) -> CompatibilityQuality:
        """Determina la calidad de compatibilidad basada en el buffer."""
        if buffer_minutes > 15:
            return CompatibilityQuality.EXCELLENT
        elif buffer_minutes > 10:
            return CompatibilityQuality.GOOD
        elif buffer_minutes > 5:
            return CompatibilityQuality.TIGHT
        else:
            return CompatibilityQuality.INCOMPATIBLE
    
    def _time_diff_minutes(self, time_a: str, time_b: str) -> float:
        """Calcula la diferencia en minutos entre dos horas (HH:MM)."""
        try:
            parts_a = time_a.split(':')
            parts_b = time_b.split(':')
            
            minutes_a = int(parts_a[0]) * 60 + int(parts_a[1])
            minutes_b = int(parts_b[0]) * 60 + int(parts_b[1])
            
            return minutes_b - minutes_a
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing times: {time_a}, {time_b} - {e}")
            return 0.0
    
    async def _get_travel_time_from_osrm(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float]
    ) -> Tuple[float, bool, Optional[str]]:
        """
        Obtiene tiempo de viaje desde OSRM.
        
        Returns:
            Tuple de (travel_time_minutes, from_fallback, error_message)
        """
        # Intentar obtener del cache primero
        cached = self._get_from_cache(start_coords, end_coords)
        if cached is not None:
            return cached, False, None
        
        self._stats['osrm_calls'] += 1
        
        try:
            # Importar servicio OSRM
            get_osrm_service, Coordinates = self._import_osrm_dependencies()
            
            osrm_service = get_osrm_service()
            
            start = Coordinates(lat=start_coords[0], lon=start_coords[1])
            end = Coordinates(lat=end_coords[0], lon=end_coords[1])
            
            result = await osrm_service.get_travel_time(start, end)
            
            if result.error:
                if result.from_fallback:
                    self._stats['fallbacks'] += 1
                    return result.minutes, True, f"Usando fallback: {result.error}"
                else:
                    self._stats['errors'] += 1
                    return result.minutes, False, result.error
            
            # Guardar en cache
            self._set_cache(start_coords, end_coords, result.minutes)
            
            return result.minutes, False, None
            
        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"Error calling OSRM: {e}")
            # Fallback: usar distancia euclidiana aproximada
            return self._fallback_travel_time(start_coords, end_coords), True, str(e)
    
    def _fallback_travel_time(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> float:
        """Calcula tiempo de viaje fallback basado en distancia euclidiana."""
        import math
        
        # Fórmula de Haversine simplificada
        R = 6371  # Radio de la Tierra en km
        lat1, lon1 = math.radians(start_coords[0]), math.radians(start_coords[1])
        lat2, lon2 = math.radians(end_coords[0]), math.radians(end_coords[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance_km = R * c
        
        # Velocidad promedio de 30 km/h para fallback
        return (distance_km / 30) * 60
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Acepta una nueva conexión WebSocket."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.validation_states[session_id] = {
            'pending_validations': {},
            'last_activity': time.time()
        }
        
        logger.info(f"[TimelineValidation WS] Connected: {session_id}")
        
        await self._send_message(websocket, {
            "type": "connected",
            "session_id": session_id,
            "message": "Conectado al validador de timeline",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def disconnect(self, session_id: str):
        """Desconecta una sesión."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.validation_states:
            del self.validation_states[session_id]
        
        logger.info(f"[TimelineValidation WS] Disconnected: {session_id}")
    
    async def handle_message(
        self,
        websocket: WebSocket,
        session_id: str,
        message: Dict[str, Any]
    ):
        """Maneja mensajes entrantes del cliente."""
        msg_type = message.get("type")
        
        try:
            if msg_type == "check_compatibility":
                await self._handle_check_compatibility(websocket, session_id, message)
            elif msg_type == "get_suggestions":
                await self._handle_get_suggestions(websocket, session_id, message)
            elif msg_type == "batch_validate":
                await self._handle_batch_validate(websocket, session_id, message)
            elif msg_type == "ping":
                await self._send_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif msg_type == "get_stats":
                await self._send_message(websocket, {
                    "type": "stats",
                    "stats": self._stats.copy(),
                    "cache_size": len(self.osrm_cache)
                })
            else:
                await self._send_error(websocket, f"Tipo de mensaje desconocido: {msg_type}")
                
        except Exception as e:
            logger.error(f"[TimelineValidation WS] Error handling message: {e}")
            await self._send_error(websocket, f"Error procesando mensaje: {str(e)}")
    
    async def _handle_check_compatibility(
        self,
        websocket: WebSocket,
        session_id: str,
        message: Dict[str, Any]
    ):
        """Maneja la validación de compatibilidad entre dos rutas."""
        start_time = time.time()
        
        route_a = message.get("route_a")
        route_b = message.get("route_b")
        request_id = message.get("request_id")
        
        if not route_a or not route_b:
            await self._send_error(websocket, "Se requieren route_a y route_b")
            return
        
        # Enviar indicador de validación en progreso
        await self._send_message(websocket, {
            "type": "validating",
            "request_id": request_id,
            "message": "Calculando tiempo de viaje..."
        })
        
        try:
            # Extraer coordenadas
            end_coords_a = self._extract_coordinates(route_a.get("endCoordinates", route_a.get("end_location")))
            start_coords_b = self._extract_coordinates(route_b.get("startCoordinates", route_b.get("start_location")))
            
            if not end_coords_a or not start_coords_b:
                await self._send_message(websocket, {
                    "type": "compatibility_result",
                    "request_id": request_id,
                    "is_compatible": False,
                    "travel_time_minutes": 0,
                    "buffer_minutes": 0,
                    "time_available": 0,
                    "quality": CompatibilityQuality.INCOMPATIBLE.value,
                    "error": "Coordenadas inválidas",
                    "validation_time_ms": round((time.time() - start_time) * 1000, 2)
                })
                return
            
            # Obtener tiempos
            end_time_a = route_a.get("endTime", route_a.get("end_time"))
            start_time_b = route_b.get("startTime", route_b.get("start_time"))
            
            # Calcular tiempo de viaje con OSRM (con cache y fallback)
            travel_time, from_fallback, error = await self._get_travel_time_from_osrm(
                end_coords_a, start_coords_b
            )
            
            # Calcular buffer disponible
            time_available = self._time_diff_minutes(end_time_a, start_time_b)
            buffer = time_available - travel_time
            
            # Determinar calidad
            quality = self._get_quality(buffer)
            is_compatible = buffer > 5  # 5 minutos de margen mínimo
            
            self._stats['validations'] += 1
            
            response = {
                "type": "compatibility_result",
                "request_id": request_id,
                "is_compatible": is_compatible,
                "travel_time_minutes": round(travel_time, 1),
                "buffer_minutes": round(buffer, 1),
                "time_available": round(time_available, 1),
                "quality": quality.value,
                "from_fallback": from_fallback,
                "validation_time_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if error:
                response["warning"] = error
            
            await self._send_message(websocket, response)
            
            logger.debug(
                f"[CheckCompatibility] {response['validation_time_ms']}ms - "
                f"buffer: {buffer:.1f}min, quality: {quality.value}"
            )
            
        except Exception as e:
            logger.error(f"[CheckCompatibility] Error: {e}")
            await self._send_message(websocket, {
                "type": "compatibility_result",
                "request_id": request_id,
                "is_compatible": False,
                "travel_time_minutes": 0,
                "buffer_minutes": 0,
                "time_available": 0,
                "quality": CompatibilityQuality.INCOMPATIBLE.value,
                "error": str(e),
                "validation_time_ms": round((time.time() - start_time) * 1000, 2)
            })
    
    async def _handle_get_suggestions(
        self,
        websocket: WebSocket,
        session_id: str,
        message: Dict[str, Any]
    ):
        """Genera sugerencias para ubicar una ruta en buses existentes."""
        start_time = time.time()
        
        route = message.get("route")
        buses = message.get("buses", [])
        request_id = message.get("request_id")
        
        if not route or not buses:
            await self._send_error(websocket, "Se requieren route y buses")
            return
        
        # Enviar indicador de procesamiento
        await self._send_message(websocket, {
            "type": "calculating_suggestions",
            "request_id": request_id,
            "message": f"Analizando {len(buses)} buses..."
        })
        
        try:
            suggestions = []
            
            for bus in buses:
                bus_id = bus.get("busId") or bus.get("id")
                bus_routes = bus.get("routes", [])
                
                # Evaluar cada posición posible
                for position in range(len(bus_routes) + 1):
                    score, reasons = await self._calculate_position_score(route, bus_routes, position)
                    
                    if score > 50:  # Solo sugerencias viables
                        suggestions.append({
                            "bus_id": bus_id,
                            "position": position,
                            "score": score,
                            "reasons": reasons,
                            "current_routes_count": len(bus_routes)
                        })
            
            # Ordenar por score descendente
            suggestions.sort(key=lambda x: x["score"], reverse=True)
            
            await self._send_message(websocket, {
                "type": "suggestions",
                "request_id": request_id,
                "suggestions": suggestions[:10],  # Top 10 sugerencias
                "total_evaluated": len(buses) * max(len(buses[0].get("routes", [])) + 1 if buses else 1, 1),
                "calculation_time_ms": round((time.time() - start_time) * 1000, 2)
            })
            
        except Exception as e:
            logger.error(f"[GetSuggestions] Error: {e}")
            await self._send_error(websocket, f"Error calculando sugerencias: {str(e)}")
    
    async def _handle_batch_validate(
        self,
        websocket: WebSocket,
        session_id: str,
        message: Dict[str, Any]
    ):
        """Valida múltiples pares de rutas en batch para eficiencia."""
        start_time = time.time()
        
        pairs = message.get("pairs", [])
        request_id = message.get("request_id")
        
        if not pairs:
            await self._send_error(websocket, "Se requiere lista de pares")
            return
        
        # Enviar indicador de procesamiento
        await self._send_message(websocket, {
            "type": "batch_validating",
            "request_id": request_id,
            "total": len(pairs),
            "message": f"Validando {len(pairs)} conexiones..."
        })
        
        try:
            results = []
            
            for i, pair in enumerate(pairs):
                route_a = pair.get("route_a")
                route_b = pair.get("route_b")
                pair_id = pair.get("id", f"pair_{i}")
                
                # Extraer coordenadas
                end_coords_a = self._extract_coordinates(route_a.get("endCoordinates", route_a.get("end_location")))
                start_coords_b = self._extract_coordinates(route_b.get("startCoordinates", route_b.get("start_location")))
                
                end_time_a = route_a.get("endTime", route_a.get("end_time"))
                start_time_b = route_b.get("startTime", route_b.get("start_time"))
                
                # Obtener tiempo de viaje
                travel_time, from_fallback, error = await self._get_travel_time_from_osrm(
                    end_coords_a, start_coords_b
                )
                
                time_available = self._time_diff_minutes(end_time_a, start_time_b)
                buffer = time_available - travel_time
                quality = self._get_quality(buffer)
                
                results.append({
                    "id": pair_id,
                    "is_compatible": buffer > 5,
                    "travel_time_minutes": round(travel_time, 1),
                    "buffer_minutes": round(buffer, 1),
                    "time_available": round(time_available, 1),
                    "quality": quality.value,
                    "from_fallback": from_fallback,
                    "warning": error if error else None
                })
                
                # Enviar progreso cada 5 validaciones
                if (i + 1) % 5 == 0:
                    await self._send_message(websocket, {
                        "type": "batch_progress",
                        "request_id": request_id,
                        "completed": i + 1,
                        "total": len(pairs)
                    })
            
            await self._send_message(websocket, {
                "type": "batch_results",
                "request_id": request_id,
                "results": results,
                "validation_time_ms": round((time.time() - start_time) * 1000, 2)
            })
            
        except Exception as e:
            logger.error(f"[BatchValidate] Error: {e}")
            await self._send_error(websocket, f"Error en validación batch: {str(e)}")
    
    async def _calculate_position_score(
        self,
        route: Dict[str, Any],
        bus_routes: List[Dict[str, Any]],
        position: int
    ) -> Tuple[int, List[str]]:
        """
        Calcula un score para insertar una ruta en una posición específica.
        
        Returns:
            Tuple de (score, reasons)
        """
        score = 100
        reasons = []
        
        route_coords = self._extract_coordinates(route.get("startCoordinates", route.get("start_location")))
        route_end_coords = self._extract_coordinates(route.get("endCoordinates", route.get("end_location")))
        route_start_time = route.get("startTime", route.get("start_time"))
        route_end_time = route.get("endTime", route.get("end_time"))
        
        # Verificar compatibilidad con ruta anterior (si existe)
        if position > 0 and bus_routes:
            prev_route = bus_routes[position - 1]
            prev_end_coords = self._extract_coordinates(
                prev_route.get("endCoordinates", prev_route.get("end_location"))
            )
            prev_end_time = prev_route.get("endTime", prev_route.get("end_time"))
            
            travel_time, _, _ = await self._get_travel_time_from_osrm(prev_end_coords, route_coords)
            buffer = self._time_diff_minutes(prev_end_time, route_start_time) - travel_time
            
            if buffer < 0:
                score -= 50
                reasons.append(f"Incompatible con ruta anterior (buffer: {buffer:.1f}min)")
            elif buffer < 5:
                score -= 20
                reasons.append(f"Margen ajustado con anterior ({buffer:.1f}min)")
            else:
                score += 10
                reasons.append(f"Buen margen con anterior ({buffer:.1f}min)")
        
        # Verificar compatibilidad con ruta siguiente (si existe)
        if position < len(bus_routes):
            next_route = bus_routes[position]
            next_start_coords = self._extract_coordinates(
                next_route.get("startCoordinates", next_route.get("start_location"))
            )
            next_start_time = next_route.get("startTime", next_route.get("start_time"))
            
            travel_time, _, _ = await self._get_travel_time_from_osrm(route_end_coords, next_start_coords)
            buffer = self._time_diff_minutes(route_end_time, next_start_time) - travel_time
            
            if buffer < 0:
                score -= 50
                reasons.append(f"Incompatible con ruta siguiente (buffer: {buffer:.1f}min)")
            elif buffer < 5:
                score -= 20
                reasons.append(f"Margen ajustado con siguiente ({buffer:.1f}min)")
            else:
                score += 10
                reasons.append(f"Buen margen con siguiente ({buffer:.1f}min)")
        
        # Bonus por balance de cargas
        if len(bus_routes) < 3:
            score += 5
            reasons.append("Bus con baja carga")
        
        return max(0, min(100, score)), reasons if reasons else ["Posición viable"]
    
    def _extract_coordinates(self, coords: Any) -> Optional[Tuple[float, float]]:
        """Extrae coordenadas de diferentes formatos."""
        if coords is None:
            return None
        
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            return (float(coords[0]), float(coords[1]))
        
        if isinstance(coords, dict):
            lat = coords.get("lat") or coords.get("latitude")
            lon = coords.get("lon") or coords.get("lng") or coords.get("longitude")
            if lat is not None and lon is not None:
                return (float(lat), float(lon))
        
        return None
    
    async def _send_message(self, websocket: WebSocket, data: Dict[str, Any]):
        """Envía un mensaje al websocket."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"[TimelineValidation WS] Error sending message: {e}")
    
    async def _send_error(self, websocket: WebSocket, message: str):
        """Envía un mensaje de error."""
        await self._send_message(websocket, {
            "type": "error",
            "error": message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del servicio."""
        return {
            **self._stats,
            "cache_size": len(self.osrm_cache),
            "active_connections": len(self.active_connections)
        }


# Instancia global del handler
timeline_validation_ws = TimelineValidationWebSocket()


# Función de conveniencia para el endpoint FastAPI
async def handle_timeline_validation_websocket(websocket: WebSocket, session_id: str):
    """
    Maneja una conexión WebSocket de validación de timeline.
    
    Uso en FastAPI:
        @app.websocket("/ws/timeline-validate")
        async def websocket_endpoint(websocket: WebSocket):
            await handle_timeline_validation_websocket(websocket, str(uuid.uuid4()))
    """
    await timeline_validation_ws.connect(websocket, session_id)
    
    try:
        while True:
            message = await websocket.receive_json()
            await timeline_validation_ws.handle_message(websocket, session_id, message)
    except WebSocketDisconnect:
        await timeline_validation_ws.disconnect(session_id)
    except Exception as e:
        logger.error(f"[TimelineValidation WS] Connection error: {e}")
        await timeline_validation_ws.disconnect(session_id)
