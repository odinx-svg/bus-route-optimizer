"""
Tests para los endpoints de validacion de compatibilidad de rutas.
"""

import pytest
from datetime import time


try:
    from backend.models.validation import (
        Coordinates, RouteValidationRequest, RecommendationLevel
    )
    from backend.config.osrm import osrm_config
except ImportError:
    from models.validation import (
        Coordinates, RouteValidationRequest, RecommendationLevel
    )
    from config.osrm import osrm_config


class TestCoordinates:
    """Tests para el modelo Coordinates."""
    
    def test_valid_coordinates(self):
        coord = Coordinates(lat=-33.4489, lon=-70.6693)
        assert coord.lat == -33.4489
        assert coord.lon == -70.6693
    
    def test_latitude_validation(self):
        with pytest.raises(ValueError):
            Coordinates(lat=91, lon=0)  # lat > 90
        with pytest.raises(ValueError):
            Coordinates(lat=-91, lon=0)  # lat < -90
    
    def test_longitude_validation(self):
        with pytest.raises(ValueError):
            Coordinates(lat=0, lon=181)  # lon > 180
        with pytest.raises(ValueError):
            Coordinates(lat=0, lon=-181)  # lon < -180


class TestRouteValidationRequest:
    """Tests para RouteValidationRequest."""
    
    def test_valid_request(self):
        req = RouteValidationRequest(
            route_id="R001",
            start_coordinates=Coordinates(lat=-33.4489, lon=-70.6693),
            end_coordinates=Coordinates(lat=-33.4567, lon=-70.6500),
            start_time=time(7, 30),
            end_time=time(8, 15),
            route_type="entry",
            school_name="Colegio Test"
        )
        assert req.route_id == "R001"
        assert req.route_type == "entry"
    
    def test_end_time_before_start(self):
        with pytest.raises(ValueError):
            RouteValidationRequest(
                route_id="R001",
                start_coordinates=Coordinates(lat=-33.4489, lon=-70.6693),
                end_coordinates=Coordinates(lat=-33.4567, lon=-70.6500),
                start_time=time(8, 0),
                end_time=time(7, 0),  # Before start
                route_type="entry"
            )


class TestOSRMConfig:
    """Tests para configuracion OSRM."""
    
    def test_default_values(self):
        assert osrm_config.TIMEOUT_SECONDS == 5.0
        assert osrm_config.MAX_RETRIES == 3
        assert osrm_config.FALLBACK_SPEED_KMH == 30.0
        assert osrm_config.MIN_MARGIN_MINUTES == 5.0
    
    def test_get_route_url(self):
        url = osrm_config.get_route_url()
        assert "/route/v1/driving" in url
    
    def test_get_table_url(self):
        url = osrm_config.get_table_url()
        assert "/table/v1/driving" in url


class TestRecommendationLevels:
    """Tests para niveles de recomendacion."""
    
    def test_recommendation_enum(self):
        assert RecommendationLevel.EXCELLENT == "excellent"
        assert RecommendationLevel.GOOD == "good"
        assert RecommendationLevel.ACCEPTABLE == "acceptable"
        assert RecommendationLevel.TIGHT == "tight"
        assert RecommendationLevel.INCOMPATIBLE == "incompatible"


@pytest.mark.asyncio
class TestOSRMService:
    """Tests para el servicio OSRM."""
    
    async def test_service_singleton(self):
        from services.osrm_service import get_osrm_service
        svc1 = get_osrm_service()
        svc2 = get_osrm_service()
        assert svc1 is svc2
    
    async def test_euclidean_distance(self):
        from services.osrm_service import OSRMService
        svc = OSRMService()
        start = Coordinates(lat=0, lon=0)
        end = Coordinates(lat=0, lon=1)  # 1 degree longitude at equator
        dist = svc._euclidean_distance_km(start, end)
        # Approximately 111km at equator
        assert 100 < dist < 120
    
    async def test_fallback_travel_time(self):
        from services.osrm_service import OSRMService
        svc = OSRMService()
        start = Coordinates(lat=0, lon=0)
        end = Coordinates(lat=0, lon=1)
        result = svc._fallback_travel_time(start, end)
        # At 30km/h, 111km should take about 222 minutes
        assert result.minutes > 0
        assert result.from_fallback is True
        assert result.distance_km is not None


@pytest.mark.asyncio
class TestValidationAPI:
    """Tests para endpoints de validacion (requiere FastAPI test client)."""
    
    async def test_validate_compatibility_endpoint_exists(self):
        """Verificar que el endpoint esta registrado."""
        import sys
        sys.path.insert(0, 'backend')
        from main import app
        
        routes = [r.path for r in app.routes if hasattr(r, 'methods')]
        assert "/api/v1/validate-route-compatibility" in routes
        assert "/api/v1/batch-validate-routes" in routes
        assert "/api/v1/osrm-health" in routes
