"""
WebSocket para validaciÃ³n de horarios en tiempo real.

Proporciona validaciÃ³n instantÃ¡nea mientras el usuario edita horarios manuales,
con retroalimentaciÃ³n inmediata sobre la viabilidad de las conexiones.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ScheduleValidationWebSocket:
    """
    WebSocket handler para validaciÃ³n de horarios en tiempo real.
    """
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.validator_instances: Dict[str, Any] = {}
        self.progressive_states: Dict[str, Any] = {}

    @staticmethod
    def _import_validation_models():
        """Importa modelos de validación con fallback según contexto de ejecución."""
        try:
            from models.validation_result import AssignedRoute, ProgressiveValidationState
        except ImportError:
            from backend.models.validation_result import AssignedRoute, ProgressiveValidationState
        return AssignedRoute, ProgressiveValidationState

    @staticmethod
    def _import_validator_services():
        """Importa servicios del validador con fallback según contexto de ejecución."""
        try:
            from services.manual_schedule_validator import ManualScheduleValidator, OSRMService
        except ImportError:
            from backend.services.manual_schedule_validator import ManualScheduleValidator, OSRMService
        return ManualScheduleValidator, OSRMService
        
    async def connect(self, websocket: WebSocket, session_id: str):
        """Acepta una nueva conexiÃ³n WebSocket."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"[ScheduleValidation WS] Connected: {session_id}")
        
        # Enviar mensaje de bienvenida
        await self._send_message(websocket, {
            "type": "connected",
            "session_id": session_id,
            "message": "Conectado al validador de horarios",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def disconnect(self, session_id: str):
        """Desconecta una sesiÃ³n."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.validator_instances:
            del self.validator_instances[session_id]
        if session_id in self.progressive_states:
            del self.progressive_states[session_id]
        logger.info(f"[ScheduleValidation WS] Disconnected: {session_id}")
    
    async def handle_message(
        self, 
        websocket: WebSocket, 
        session_id: str, 
        message: Dict[str, Any]
    ):
        """
        Maneja mensajes entrantes del cliente.
        
        Tipos de mensaje soportados:
        - validate_connection: Valida una conexiÃ³n entre dos rutas
        - validate_full_schedule: Valida un horario completo
        - validate_progressive: Valida progresivamente al agregar rutas
        - suggest_time: Solicita sugerencias de horarios
        - clear_cache: Limpia la cachÃ© de validaciones
        - ping: Heartbeat
        """
        msg_type = message.get("type")
        
        try:
            if msg_type == "validate_connection":
                await self._handle_validate_connection(websocket, session_id, message)
            elif msg_type == "validate_full_schedule":
                await self._handle_validate_full_schedule(websocket, session_id, message)
            elif msg_type == "validate_bus":
                await self._handle_validate_bus(websocket, session_id, message)
            elif msg_type == "validate_all_buses":
                await self._handle_validate_all_buses(websocket, session_id, message)
            elif msg_type == "validate_progressive":
                await self._handle_validate_progressive(websocket, session_id, message)
            elif msg_type == "suggest_time":
                await self._handle_suggest_time(websocket, session_id, message)
            elif msg_type == "clear_cache":
                await self._handle_clear_cache(websocket, session_id)
            elif msg_type == "ping":
                await self._send_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                await self._send_error(websocket, f"Tipo de mensaje desconocido: {msg_type}")
                
        except Exception as e:
            logger.error(f"[ScheduleValidation WS] Error handling message: {e}")
            await self._send_error(websocket, f"Error procesando mensaje: {str(e)}")
    
    async def _handle_validate_connection(
        self, 
        websocket: WebSocket, 
        session_id: str, 
        message: Dict[str, Any]
    ):
        """Maneja validaciÃ³n de una conexiÃ³n entre dos rutas."""
        self._import_validation_models()
        self._import_validator_services()
        
        route_a_data = message.get("route_a") or message.get("current_route")
        route_b_data = message.get("route_b") or message.get("next_route")
        
        if not route_a_data or not route_b_data:
            await self._send_error(websocket, "Se requieren route_a y route_b")
            return
        
        # Parsear rutas
        try:
            route_a = self._parse_assigned_route(route_a_data)
            route_b = self._parse_assigned_route(route_b_data)
        except Exception as e:
            await self._send_error(websocket, f"Error parseando rutas: {str(e)}")
            return
        
        # Crear o reutilizar validator
        validator = self._get_or_create_validator(session_id)
        
        # Validar con timing
        import time
        start = time.time()
        result = await validator.validate_connection(route_a, route_b)
        elapsed_ms = (time.time() - start) * 1000
        
        await self._send_message(websocket, {
            "type": "validation_result",
            "compatible": result.is_compatible,
            "buffer_minutes": round(result.buffer_minutes, 1),
            "travel_time": round(result.travel_time, 1),
            "time_available": round(result.time_available, 1),
            "suggested_start": result.suggested_start,
            "issue": result.issue.dict() if result.issue else None,
            "validation_time_ms": round(elapsed_ms, 2),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.debug(f"[ValidateConnection] {elapsed_ms:.1f}ms for {route_a.id}->{route_b.id}")
    
    async def _handle_validate_full_schedule(
        self, 
        websocket: WebSocket, 
        session_id: str, 
        message: Dict[str, Any]
    ):
        """Maneja validaciÃ³n de un horario completo."""
        self._import_validation_models()
        self._import_validator_services()
        
        routes_data = message.get("routes", [])
        
        if not routes_data:
            await self._send_error(websocket, "Se requiere lista de rutas")
            return
        
        # Parsear rutas
        try:
            routes = [self._parse_assigned_route(r) for r in routes_data]
        except Exception as e:
            await self._send_error(websocket, f"Error parseando rutas: {str(e)}")
            return
        
        # Validar
        validator = self._get_or_create_validator(session_id)
        
        import time
        start = time.time()
        result = await validator.validate_bus_schedule(routes)
        elapsed_ms = (time.time() - start) * 1000
        
        await self._send_message(websocket, {
            "type": "full_validation",
            "is_valid": result.is_valid,
            "issues": [issue.dict() for issue in result.issues],
            "issues_count": len(result.issues),
            "total_travel_time": round(result.total_travel_time, 1),
            "efficiency_score": round(result.efficiency_score, 1),
            "buffer_stats": result.buffer_stats,
            "validation_time_ms": round(elapsed_ms, 2),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"[ValidateFull] {elapsed_ms:.1f}ms for {len(routes)} routes")

    async def _handle_validate_bus(
        self,
        websocket: WebSocket,
        session_id: str,
        message: Dict[str, Any]
    ):
        """Maneja validaciÃ³n de un bus completo."""
        bus_id = message.get("bus_id", "unknown")
        routes_data = message.get("routes", [])

        if not routes_data:
            await self._send_error(websocket, "Se requiere lista de rutas para validar bus")
            return

        try:
            routes = [self._parse_assigned_route(r) for r in routes_data]
        except Exception as e:
            await self._send_error(websocket, f"Error parseando rutas del bus: {str(e)}")
            return

        validator = self._get_or_create_validator(session_id)

        import time
        start = time.time()
        result = await validator.validate_bus_schedule(routes)
        elapsed_ms = (time.time() - start) * 1000

        feasible = result.is_valid
        issues_count = len(result.issues)
        day = message.get("day")
        message_text = (
            f"Bus {bus_id} viable"
            if feasible
            else f"Bus {bus_id} con {issues_count} incidencias"
        )

        enriched_issues = []
        for issue in result.issues:
            issue_dict = issue.dict()
            issue_dict["bus_id"] = bus_id
            if day:
                issue_dict["day"] = day
            enriched_issues.append(issue_dict)

        await self._send_message(websocket, {
            "type": "bus_validation",
            "bus_id": bus_id,
            "feasible": feasible,
            "message": message_text,
            "issues": enriched_issues,
            "issues_count": issues_count,
            "total_travel_time": round(result.total_travel_time, 1),
            "efficiency_score": round(result.efficiency_score, 1),
            "validation_time_ms": round(elapsed_ms, 2),
            "timestamp": datetime.utcnow().isoformat()
        })

    @staticmethod
    def _build_summary(day_reports: List[Dict[str, Any]], incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Construye un resumen global de la validación."""
        total_buses = 0
        feasible_buses = 0
        buses_with_issues = 0

        for day_report in day_reports:
            summary = day_report.get("summary", {})
            total_buses += int(summary.get("total_buses", 0))
            feasible_buses += int(summary.get("feasible_buses", 0))
            buses_with_issues += int(summary.get("buses_with_issues", 0))

        error_issues = sum(1 for issue in incidents if issue.get("severity") == "error")
        warning_issues = sum(1 for issue in incidents if issue.get("severity") == "warning")
        info_issues = sum(1 for issue in incidents if issue.get("severity") == "info")

        return {
            "total_buses": total_buses,
            "feasible_buses": feasible_buses,
            "buses_with_issues": buses_with_issues,
            "incidents_total": len(incidents),
            "incidents_error": error_issues,
            "incidents_warning": warning_issues,
            "incidents_info": info_issues,
        }

    async def _handle_validate_all_buses(
        self,
        websocket: WebSocket,
        session_id: str,
        message: Dict[str, Any]
    ):
        """
        Valida todos los buses agrupando por día.

        Payload esperado:
        {
          "type": "validate_all_buses",
          "days": [
            {"day": "L", "buses": [{"bus_id": "B001", "routes": [...] }]}
          ],
          "include_valid_buses": false
        }
        """
        days_data = message.get("days", [])
        include_valid_buses = bool(message.get("include_valid_buses", False))

        # Compatibilidad con payload simplificado (un solo día)
        if not days_data:
            fallback_buses = message.get("buses", [])
            if fallback_buses:
                days_data = [{
                    "day": message.get("day", "L"),
                    "buses": fallback_buses
                }]

        if not days_data:
            await self._send_error(websocket, "Se requiere payload days con buses para validar")
            return

        validator = self._get_or_create_validator(session_id)

        import time
        start = time.time()

        day_reports: List[Dict[str, Any]] = []
        incidents: List[Dict[str, Any]] = []

        for day_entry in days_data:
            day_code = day_entry.get("day", "L")
            buses_data = day_entry.get("buses", [])
            bus_reports: List[Dict[str, Any]] = []

            day_total = len(buses_data)
            day_feasible = 0
            day_with_issues = 0

            for bus_data in buses_data:
                bus_id = bus_data.get("bus_id") or bus_data.get("id") or "unknown"
                routes_data = bus_data.get("routes") or bus_data.get("items") or []

                if not routes_data:
                    bus_report = {
                        "bus_id": bus_id,
                        "is_valid": True,
                        "issues_count": 0,
                        "issues": [],
                        "message": f"Bus {bus_id} sin rutas"
                    }
                    if include_valid_buses:
                        bus_reports.append(bus_report)
                    day_feasible += 1
                    continue

                try:
                    routes = [self._parse_assigned_route(route_data) for route_data in routes_data]
                except Exception as exc:
                    await self._send_error(
                        websocket,
                        f"Error parseando rutas del bus {bus_id} ({day_code}): {str(exc)}"
                    )
                    return

                result = await validator.validate_bus_schedule(routes)
                issue_dicts: List[Dict[str, Any]] = []

                for issue in result.issues:
                    issue_dict = issue.dict()
                    issue_dict["day"] = day_code
                    issue_dict["bus_id"] = bus_id
                    issue_dicts.append(issue_dict)
                    incidents.append(issue_dict)

                issues_count = len(issue_dicts)
                is_valid = bool(result.is_valid)

                if is_valid:
                    day_feasible += 1
                if issues_count > 0:
                    day_with_issues += 1

                bus_report = {
                    "bus_id": bus_id,
                    "is_valid": is_valid,
                    "issues_count": issues_count,
                    "issues": issue_dicts,
                    "message": (
                        f"Bus {bus_id} viable"
                        if is_valid
                        else f"Bus {bus_id} con {issues_count} incidencias"
                    ),
                    "total_travel_time": round(result.total_travel_time, 1),
                    "efficiency_score": round(result.efficiency_score, 1),
                    "buffer_stats": result.buffer_stats,
                }

                if include_valid_buses or issues_count > 0:
                    bus_reports.append(bus_report)

            day_reports.append({
                "day": day_code,
                "summary": {
                    "total_buses": day_total,
                    "feasible_buses": day_feasible,
                    "buses_with_issues": day_with_issues,
                    "incidents_total": sum(bus.get("issues_count", 0) for bus in bus_reports),
                },
                "buses": bus_reports
            })

        summary = self._build_summary(day_reports, incidents)
        elapsed_ms = (time.time() - start) * 1000

        await self._send_message(websocket, {
            "type": "all_buses_validation",
            "generated_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "days": day_reports,
            "incidents": incidents,
            "validation_time_ms": round(elapsed_ms, 2),
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _handle_validate_progressive(
        self, 
        websocket: WebSocket, 
        session_id: str, 
        message: Dict[str, Any]
    ):
        """Maneja validaciÃ³n progresiva al agregar rutas una por una."""
        _, ProgressiveValidationState = self._import_validation_models()
        self._import_validator_services()
        
        new_route_data = message.get("route")
        bus_id = message.get("bus_id", "default")
        reset = message.get("reset", False)
        
        if not new_route_data:
            await self._send_error(websocket, "Se requiere route")
            return
        
        # Obtener o crear estado progresivo
        state_key = f"{session_id}:{bus_id}"
        
        if reset or state_key not in self.progressive_states:
            self.progressive_states[state_key] = ProgressiveValidationState(bus_id=bus_id)
        
        state = self.progressive_states[state_key]
        
        # Parsear nueva ruta
        try:
            new_route = self._parse_assigned_route(new_route_data)
        except Exception as e:
            await self._send_error(websocket, f"Error parseando ruta: {str(e)}")
            return
        
        # Validar progresivamente
        validator = self._get_or_create_validator(session_id)
        
        import time
        start = time.time()
        result = await validator.validate_progressive(state, new_route)
        elapsed_ms = (time.time() - start) * 1000
        
        await self._send_message(websocket, {
            "type": "progressive_validation",
            "route_index": len(state.routes) - 1,
            "total_routes": len(state.routes),
            "is_valid": result.is_valid,
            "issues": [issue.dict() for issue in result.issues],
            "new_issues": [issue.dict() for issue in result.issues[-1:]] if result.issues else [],
            "total_travel_time": round(result.total_travel_time, 1),
            "efficiency_score": round(result.efficiency_score, 1),
            "validation_time_ms": round(elapsed_ms, 2),
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _handle_suggest_time(
        self, 
        websocket: WebSocket, 
        session_id: str, 
        message: Dict[str, Any]
    ):
        """Maneja solicitudes de sugerencias de horarios."""
        self._import_validator_services()
        
        current_route_data = message.get("current_route")
        next_route_data = message.get("next_route")
        travel_time = message.get("travel_time")
        
        if not current_route_data or not next_route_data:
            await self._send_error(websocket, "Se requieren current_route y next_route")
            return
        
        try:
            current_route = self._parse_assigned_route(current_route_data)
            next_route = self._parse_assigned_route(next_route_data)
        except Exception as e:
            await self._send_error(websocket, f"Error parseando rutas: {str(e)}")
            return
        
        # Si no se proporciona travel_time, calcularlo
        validator = self._get_or_create_validator(session_id)
        
        if travel_time is None:
            travel_time = await validator.osrm_service.get_travel_time(
                current_route.end_location,
                next_route.start_location
            ) or 15.0
        
        suggestion = validator.suggest_alternative_time(
            current_route, next_route, travel_time
        )
        
        await self._send_message(websocket, {
            "type": "suggestion",
            "suggested_start": suggestion.suggested_start_time.strftime("%H:%M"),
            "suggested_end": suggestion.suggested_end_time.strftime("%H:%M") if suggestion.suggested_end_time else None,
            "message": suggestion.message,
            "alternative_times": [t.strftime("%H:%M") for t in suggestion.alternative_times],
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _handle_clear_cache(self, websocket: WebSocket, session_id: str):
        """Limpia la cachÃ© del validador."""
        if session_id in self.validator_instances:
            self.validator_instances[session_id].clear_cache()
        
        # Limpiar estados progresivos de esta sesiÃ³n
        keys_to_remove = [k for k in self.progressive_states if k.startswith(f"{session_id}:")]
        for k in keys_to_remove:
            del self.progressive_states[k]
        
        await self._send_message(websocket, {
            "type": "cache_cleared",
            "message": "CachÃ© limpiada correctamente",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def _parse_assigned_route(self, data: Dict[str, Any]) -> 'AssignedRoute':
        """Parsea datos de ruta desde JSON."""
        AssignedRoute, _ = self._import_validation_models()
        from datetime import time as dt_time
        
        # Parsear tiempos
        def parse_time(t):
            if isinstance(t, str):
                parts = t.split(":")
                return dt_time(int(parts[0]), int(parts[1]))
            elif isinstance(t, dict):
                return dt_time(t.get("hour", 0), t.get("minute", 0))
            return t
        
        start_location = data.get("start_location", data.get("start_loc", (0.0, 0.0)))
        end_location = data.get("end_location", data.get("end_loc", (0.0, 0.0)))
        
        # Asegurar que sean tuplas
        if isinstance(start_location, list):
            start_location = tuple(start_location)
        if isinstance(end_location, list):
            end_location = tuple(end_location)
        
        return AssignedRoute(
            id=data.get("id", data.get("route_id", "unknown")),
            route_id=data.get("route_id", data.get("id", "unknown")),
            start_time=parse_time(data.get("start_time")),
            end_time=parse_time(data.get("end_time")),
            start_location=start_location,
            end_location=end_location,
            type=data.get("type", "entry"),
            school_name=data.get("school_name")
        )
    
    def _get_or_create_validator(self, session_id: str) -> 'ManualScheduleValidator':
        """Obtiene o crea una instancia del validador para la sesiÃ³n."""
        ManualScheduleValidator, OSRMService = self._import_validator_services()
        
        if session_id not in self.validator_instances:
            osrm_service = OSRMService()
            self.validator_instances[session_id] = ManualScheduleValidator(osrm_service)
        
        return self.validator_instances[session_id]
    
    async def _send_message(self, websocket: WebSocket, data: Dict[str, Any]):
        """EnvÃ­a un mensaje al websocket."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"[ScheduleValidation WS] Error sending message: {e}")
    
    async def _send_error(self, websocket: WebSocket, message: str):
        """Envia un mensaje de error."""
        await self._send_message(websocket, {
            "type": "error",
            "message": message,
            "error": message,
            "timestamp": datetime.utcnow().isoformat()
        })


# Instancia global del handler
validation_ws_handler = ScheduleValidationWebSocket()


# FunciÃ³n de conveniencia para el endpoint FastAPI
async def handle_schedule_validation_websocket(websocket: WebSocket, session_id: str):
    """
    Maneja una conexiÃ³n WebSocket de validaciÃ³n de horarios.
    
    Uso en FastAPI:
        @app.websocket("/ws/validate-schedule")
        async def websocket_endpoint(websocket: WebSocket):
            await handle_schedule_validation_websocket(websocket, str(uuid.uuid4()))
    """
    await validation_ws_handler.connect(websocket, session_id)
    
    try:
        while True:
            message = await websocket.receive_json()
            await validation_ws_handler.handle_message(websocket, session_id, message)
    except WebSocketDisconnect:
        await validation_ws_handler.disconnect(session_id)
    except Exception as e:
        logger.error(f"[ScheduleValidation WS] Connection error: {e}")
        await validation_ws_handler.disconnect(session_id)
