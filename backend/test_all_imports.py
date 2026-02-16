import sys
sys.path.insert(0, 'backend')

print("Testing imports...")

from config.osrm import osrm_config
print(f"[OK] config.osrm - Base URL: {osrm_config.BASE_URL}")

from models.validation import (
    Coordinates, RouteValidationRequest, RouteCompatibilityResponse,
    BatchRouteValidationRequest, BatchRouteValidationResponse,
    RecommendationLevel, OSRMHealthResponse
)
print("[OK] models.validation")

from services.osrm_service import get_osrm_service
print("[OK] services.osrm_service")

# Test API router import (without FastAPI running)
import api.validation
print("[OK] api.validation")

print("\nAll imports successful!")
