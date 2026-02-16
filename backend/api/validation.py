"""
API endpoints para validacion de compatibilidad de rutas usando OSRM.
"""

import logging
import time
from typing import List

from fastapi import APIRouter, HTTPException, status

try:
    from backend.services.osrm_service import get_osrm_service
    from backend.models.validation import (
        Coordinates, RouteValidationRequest, RouteCompatibilityResponse,
        BatchRouteValidationRequest, BatchRouteValidationResponse,
        RecommendationLevel, OSRMHealthResponse
    )
    from backend.config.osrm import osrm_config
except ImportError:
    from services.osrm_service import get_osrm_service
    from models.validation import (
        Coordinates, RouteValidationRequest, RouteCompatibilityResponse,
        BatchRouteValidationRequest, BatchRouteValidationResponse,
        RecommendationLevel, OSRMHealthResponse
    )
    from config.osrm import osrm_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["validation"])


def get_recommendation(buffer_minutes: float):
    """Determinar nivel de recomendacion basado en buffer."""
    min_margin = osrm_config.MIN_MARGIN_MINUTES
    
    if buffer_minutes < 0:
        return RecommendationLevel.INCOMPATIBLE, "Incompatible: tiempo de viaje excede disponible"
    elif buffer_minutes < min_margin:
        return RecommendationLevel.TIGHT, f"Margen ajustado ({buffer_minutes:.1f} min)"
    elif buffer_minutes < min_margin * 2:
        return RecommendationLevel.ACCEPTABLE, f"Margen aceptable ({buffer_minutes:.1f} min)"
    elif buffer_minutes < min_margin * 4:
        return RecommendationLevel.GOOD, f"Buen margen ({buffer_minutes:.1f} min)"
    else:
        return RecommendationLevel.EXCELLENT, f"Margen excelente ({buffer_minutes:.1f} min)"


def time_to_minutes(t) -> float:
    return t.hour * 60 + t.minute + t.second / 60


@router.post("/validate-route-compatibility", response_model=RouteCompatibilityResponse)
async def validate_route_compatibility(
    route_a_end: Coordinates,
    route_b_start: Coordinates,
    time_available_minutes: float
) -> RouteCompatibilityResponse:
    """Valida si dos rutas consecutivas son compatibles."""
    if time_available_minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="time_available_minutes debe ser mayor que 0"
        )
    
    osrm_service = get_osrm_service()
    travel_result = await osrm_service.get_travel_time(route_a_end, route_b_start)
    
    travel_time = travel_result.minutes
    buffer = time_available_minutes - travel_time
    min_margin = osrm_config.MIN_MARGIN_MINUTES
    compatible = buffer > min_margin
    
    recommendation, rec_text = get_recommendation(buffer)
    
    logger.info(
        f"[Validation] ({route_a_end.lat},{route_a_end.lon}) -> "
        f"({route_b_start.lat},{route_b_start.lon}) | "
        f"Travel: {travel_time:.1f}min | Buffer: {buffer:.1f}min"
    )
    
    return RouteCompatibilityResponse(
        compatible=compatible,
        travel_time_minutes=travel_time,
        buffer_minutes=buffer,
        time_available_minutes=time_available_minutes,
        margin_adequate=buffer > min_margin,
        recommendation=recommendation,
        recommendation_text=rec_text,
        distance_km=travel_result.distance_km,
        used_cache=travel_result.from_cache,
        used_fallback=travel_result.from_fallback
    )


@router.post("/batch-validate-routes", response_model=BatchRouteValidationResponse)
async def batch_validate_routes(request: BatchRouteValidationRequest) -> BatchRouteValidationResponse:
    """Valida una secuencia completa de rutas."""
    start_time = time.time()
    osrm_service = get_osrm_service()
    routes = request.routes_sequence
    validations: List[RouteCompatibilityResponse] = []
    cache_hits = 0
    
    for i in range(len(routes) - 1):
        current = routes[i]
        next_route = routes[i + 1]
        
        time_available = time_to_minutes(next_route.start_time) - time_to_minutes(current.end_time)
        
        if time_available < 0:
            validations.append(RouteCompatibilityResponse(
                compatible=False,
                travel_time_minutes=0,
                buffer_minutes=time_available,
                time_available_minutes=time_available,
                margin_adequate=False,
                recommendation=RecommendationLevel.INCOMPATIBLE,
                recommendation_text=f"Solapamiento: ruta {i+1} inicia antes",
                used_fallback=False
            ))
            continue
        
        travel_result = await osrm_service.get_travel_time(
            current.end_coordinates, next_route.start_coordinates
        )
        
        if travel_result.from_cache:
            cache_hits += 1
        
        travel_time = travel_result.minutes
        buffer = time_available - travel_time
        min_margin = osrm_config.MIN_MARGIN_MINUTES
        compatible = buffer > min_margin
        
        recommendation, rec_text = get_recommendation(buffer)
        
        validations.append(RouteCompatibilityResponse(
            compatible=compatible,
            travel_time_minutes=travel_time,
            buffer_minutes=buffer,
            time_available_minutes=time_available,
            margin_adequate=buffer > min_margin,
            recommendation=recommendation,
            recommendation_text=rec_text,
            distance_km=travel_result.distance_km,
            used_cache=travel_result.from_cache,
            used_fallback=travel_result.from_fallback
        ))
    
    all_compatible = all(v.compatible for v in validations)
    total_travel = sum(v.travel_time_minutes for v in validations)
    buffers = [v.buffer_minutes for v in validations]
    min_buffer = min(buffers) if buffers else 0
    avg_buffer = sum(buffers) / len(buffers) if buffers else 0
    
    critical = [i for i, v in enumerate(validations) if v.buffer_minutes < osrm_config.MIN_MARGIN_MINUTES]
    
    if min_buffer < 0:
        overall = RecommendationLevel.INCOMPATIBLE
    elif min_buffer < osrm_config.MIN_MARGIN_MINUTES:
        overall = RecommendationLevel.TIGHT
    elif min_buffer < osrm_config.MIN_MARGIN_MINUTES * 2:
        overall = RecommendationLevel.ACCEPTABLE
    elif min_buffer < osrm_config.MIN_MARGIN_MINUTES * 4:
        overall = RecommendationLevel.GOOD
    else:
        overall = RecommendationLevel.EXCELLENT
    
    exec_time = (time.time() - start_time) * 1000
    
    logger.info(f"[Batch] {len(routes)} routes, {len(validations)} transitions in {exec_time:.1f}ms")
    
    return BatchRouteValidationResponse(
        all_compatible=all_compatible,
        validations=validations,
        total_routes=len(routes),
        total_transitions=len(validations),
        total_travel_time_minutes=total_travel,
        min_buffer_minutes=min_buffer,
        avg_buffer_minutes=avg_buffer,
        critical_transitions=critical,
        overall_recommendation=overall,
        execution_time_ms=exec_time,
        cache_hits=cache_hits
    )


@router.get("/osrm-health", response_model=OSRMHealthResponse)
async def osrm_health() -> OSRMHealthResponse:
    """Verificar estado de salud de OSRM."""
    osrm_service = get_osrm_service()
    health = await osrm_service.health_check()
    
    return OSRMHealthResponse(
        status=health['status'],
        response_time_ms=health['response_time_ms'],
        cache_size=health['cache_size'],
        base_url=health['base_url'],
        error_message=health.get('error')
    )


@router.get("/osrm-stats")
async def osrm_stats() -> dict:
    """Estadisticas de uso de OSRM."""
    osrm_service = get_osrm_service()
    return {
        "stats": osrm_service.get_stats(),
        "cache_size": osrm_service.cache.size,
        "config": osrm_config.get_config_dict()
    }


@router.post("/osrm-clear-cache")
async def clear_osrm_cache() -> dict:
    """Limpiar cache de OSRM."""
    osrm_service = get_osrm_service()
    prev_size = osrm_service.cache.size
    osrm_service.clear_cache()
    return {"message": "Cache cleared", "previous_size": prev_size}
