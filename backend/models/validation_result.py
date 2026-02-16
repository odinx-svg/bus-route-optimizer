"""
Modelos de datos para validación de horarios manuales.

Este módulo define las estructuras de datos utilizadas por el validador
de horarios en tiempo real.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
from datetime import time
from enum import Enum


class IssueType(str, Enum):
    """Tipos de problemas de validación."""
    
    INSUFFICIENT_TIME = "INSUFFICIENT_TIME"
    TIGHT_BUFFER = "TIGHT_BUFFER"
    INVALID_TIME_RANGE = "INVALID_TIME_RANGE"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    OVERLAPPING_ROUTES = "OVERLAPPING_ROUTES"


class RouteIssue(BaseModel):
    """
    Representa un problema detectado en la validación.
    """
    
    route_a: str = Field(..., description="ID de la ruta actual")
    route_b: str = Field(..., description="ID de la siguiente ruta")
    issue_type: IssueType = Field(..., description="Tipo de problema")
    message: str = Field(..., description="Mensaje descriptivo del problema")
    suggestion: Optional[str] = Field(None, description="Sugerencia para corregir")
    severity: str = Field("error", description="Severidad: error, warning, info")
    time_available: Optional[float] = Field(None, description="Tiempo disponible entre rutas (min)")
    travel_time: Optional[float] = Field(None, description="Tiempo de viaje requerido (min)")
    buffer_minutes: Optional[float] = Field(None, description="Buffer resultante (min)")
    day: Optional[str] = Field(None, description="Día de operación (L, M, Mc, X, V)")
    bus_id: Optional[str] = Field(None, description="Bus asociado a la incidencia")


class ValidationResult(BaseModel):
    """
    Resultado completo de la validación de un horario.
    """
    
    is_valid: bool = Field(..., description="Indica si el horario es válido")
    issues: List[RouteIssue] = Field(default_factory=list, description="Lista de problemas encontrados")
    total_travel_time: float = Field(0.0, description="Tiempo total de viaje en minutos")
    efficiency_score: float = Field(0.0, description="Puntaje de eficiencia (0-100)")
    buffer_stats: dict = Field(default_factory=dict, description="Estadísticas de buffers")
    
    def to_dict(self) -> dict:
        """Convierte el resultado a diccionario."""
        return {
            "is_valid": self.is_valid,
            "issues_count": len(self.issues),
            "issues": [issue.dict() for issue in self.issues],
            "total_travel_time": round(self.total_travel_time, 1),
            "efficiency_score": round(self.efficiency_score, 1),
            "buffer_stats": self.buffer_stats
        }


class ConnectionValidationResult(BaseModel):
    """
    Resultado de validación de una conexión específica entre dos rutas.
    """
    
    is_compatible: bool = Field(..., description="Las rutas son compatibles")
    buffer_minutes: float = Field(..., description="Minutos de margen disponibles")
    travel_time: float = Field(..., description="Tiempo de viaje estimado (OSRM)")
    time_available: float = Field(..., description="Tiempo disponible entre rutas")
    suggested_start: Optional[str] = Field(None, description="Hora sugerida de inicio")
    issue: Optional[RouteIssue] = Field(None, description="Problema detectado si hay")
    
    def to_dict(self) -> dict:
        """Convierte el resultado a diccionario."""
        result = {
            "is_compatible": self.is_compatible,
            "buffer_minutes": round(self.buffer_minutes, 1),
            "travel_time": round(self.travel_time, 1),
            "time_available": round(self.time_available, 1),
        }
        if self.suggested_start:
            result["suggested_start"] = self.suggested_start
        if self.issue:
            result["issue"] = self.issue.dict()
        return result


class AssignedRoute(BaseModel):
    """
    Ruta asignada con información de tiempo y ubicación.
    Utilizada para validación de conexiones.
    """
    
    id: str = Field(..., description="ID único de la ruta")
    route_id: str = Field(..., description="ID de la ruta original")
    start_time: time = Field(..., description="Hora de inicio")
    end_time: time = Field(..., description="Hora de término")
    start_location: Tuple[float, float] = Field(..., description="Coordenadas de inicio (lat, lon)")
    end_location: Tuple[float, float] = Field(..., description="Coordenadas de término (lat, lon)")
    type: str = Field(..., description="Tipo: entry o exit")
    school_name: Optional[str] = Field(None, description="Nombre del colegio")
    
    class Config:
        json_encoders = {
            time: lambda t: t.strftime("%H:%M")
        }


class ValidationCacheEntry(BaseModel):
    """
    Entrada de caché para validaciones previas.
    """
    
    key: str = Field(..., description="Clave de caché")
    result: ConnectionValidationResult = Field(..., description="Resultado cacheado")
    timestamp: float = Field(..., description="Timestamp de creación")
    expires_at: float = Field(..., description="Timestamp de expiración")


class ProgressiveValidationState(BaseModel):
    """
    Estado de validación progresiva para un bus.
    """
    
    bus_id: str = Field(..., description="ID del bus")
    routes: List[AssignedRoute] = Field(default_factory=list, description="Rutas agregadas")
    last_validated_index: int = Field(-1, description="Último índice validado")
    cumulative_issues: List[RouteIssue] = Field(default_factory=list, description="Issues acumulados")
    total_travel_time: float = Field(0.0, description="Tiempo total de viaje acumulado")
    
    def add_route(self, route: AssignedRoute) -> int:
        """Agrega una ruta y retorna su índice."""
        self.routes.append(route)
        return len(self.routes) - 1
    
    def get_last_route(self) -> Optional[AssignedRoute]:
        """Obtiene la última ruta agregada."""
        if self.routes:
            return self.routes[-1]
        return None


class SuggestionResult(BaseModel):
    """
    Resultado de una sugerencia inteligente.
    """
    
    suggested_start_time: time = Field(..., description="Hora de inicio sugerida")
    suggested_end_time: Optional[time] = Field(None, description="Hora de término sugerida")
    message: str = Field(..., description="Mensaje explicativo")
    alternative_times: List[time] = Field(default_factory=list, description="Alternativas válidas")
    
    class Config:
        json_encoders = {
            time: lambda t: t.strftime("%H:%M")
        }
