"""
Modelos Pydantic para validacion de compatibilidad de rutas.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from datetime import time
from enum import Enum


class RecommendationLevel(str, Enum):
    """Niveles de recomendacion basados en el buffer disponible."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    TIGHT = "tight"
    INCOMPATIBLE = "incompatible"


class Coordinates(BaseModel):
    """Coordenadas geograficas (latitud, longitud)."""
    
    lat: float = Field(..., ge=-90, le=90, description="Latitud en grados decimales")
    lon: float = Field(..., ge=-180, le=180, description="Longitud en grados decimales")
    
    class Config:
        json_schema_extra = {"example": {"lat": -33.4489, "lon": -70.6693}}


class RouteValidationRequest(BaseModel):
    """Solicitud de validacion para una ruta individual."""
    
    route_id: str = Field(..., description="ID unico de la ruta")
    start_coordinates: Coordinates = Field(..., description="Coordenadas de la primera parada")
    end_coordinates: Coordinates = Field(..., description="Coordenadas de la ultima parada")
    start_time: time = Field(..., description="Hora de inicio de la ruta")
    end_time: time = Field(..., description="Hora de termino de la ruta")
    route_type: Literal["entry", "exit"] = Field(..., description="Tipo de ruta")
    school_name: Optional[str] = Field(None, description="Nombre del colegio")
    
    @field_validator('end_time')
    @classmethod
    def validate_end_time(cls, v, info):
        values = info.data
        if 'start_time' in values:
            start = values['start_time']
            start_min = start.hour * 60 + start.minute
            end_min = v.hour * 60 + v.minute
            if end_min <= start_min:
                raise ValueError("end_time debe ser posterior a start_time")
        return v


class RouteCompatibilityResponse(BaseModel):
    """Respuesta de validacion de compatibilidad entre dos rutas."""
    
    compatible: bool = Field(..., description="Indica si las rutas son compatibles")
    travel_time_minutes: float = Field(..., ge=0, description="Tiempo de viaje en minutos")
    buffer_minutes: float = Field(..., description="Buffer disponible")
    time_available_minutes: float = Field(..., ge=0, description="Tiempo disponible entre rutas")
    margin_adequate: bool = Field(..., description="Margen adecuado (>5 min)")
    recommendation: RecommendationLevel = Field(..., description="Nivel de recomendacion")
    recommendation_text: str = Field(..., description="Texto explicativo")
    distance_km: Optional[float] = Field(None, description="Distancia estimada en km")
    used_cache: bool = Field(False, description="Indica si se uso cache")
    used_fallback: bool = Field(False, description="Indica si se uso fallback")


class BatchRouteValidationRequest(BaseModel):
    """Solicitud de validacion batch para secuencia de rutas."""
    
    routes_sequence: List[RouteValidationRequest] = Field(..., min_length=2)
    bus_id: Optional[str] = Field(None, description="ID del bus")
    
    @field_validator('routes_sequence')
    @classmethod
    def validate_sequence(cls, v):
        if len(v) < 2:
            raise ValueError("Se requieren al menos 2 rutas")
        for i in range(len(v) - 1):
            curr_end = v[i].end_time.hour * 60 + v[i].end_time.minute
            next_start = v[i + 1].start_time.hour * 60 + v[i + 1].start_time.minute
            if next_start < curr_end:
                raise ValueError(f"Ruta {i+1} inicia antes de que termine ruta {i}")
        return v


class BatchRouteValidationResponse(BaseModel):
    """Respuesta de validacion batch."""
    
    all_compatible: bool = Field(..., description="Todas las transiciones compatibles")
    validations: List[RouteCompatibilityResponse] = Field(...)
    total_routes: int = Field(..., ge=2)
    total_transitions: int = Field(..., ge=1)
    total_travel_time_minutes: float = Field(..., ge=0)
    min_buffer_minutes: float = Field(...)
    avg_buffer_minutes: float = Field(...)
    critical_transitions: List[int] = Field(default_factory=list)
    overall_recommendation: RecommendationLevel = Field(...)
    execution_time_ms: float = Field(..., ge=0)
    cache_hits: int = Field(default=0)


class OSRMHealthResponse(BaseModel):
    """Respuesta del estado de salud de OSRM."""
    
    status: Literal["healthy", "degraded", "unavailable"] = Field(...)
    response_time_ms: Optional[float] = Field(None)
    cache_size: int = Field(...)
    base_url: str = Field(...)
    error_message: Optional[str] = Field(None)
