# Routing and Maps

## Backend files

- `backend/router_service.py`
- `backend/tests/test_router_service.py`
- `backend/osrm_cache.json`

## Frontend files

- `frontend/src/services/RouteService.js`
- `frontend/src/components/MapView.jsx`
- `frontend/src/components/RouteStopsLayer.jsx`
- `frontend/src/components/MapLegend.jsx`

## Current architecture

- Backend OSRM:
  - travel-time focused
  - persistent disk cache
  - negative cache
  - circuit breaker
- Frontend OSRM:
  - route geometry focused
  - in-memory cache by route or connection key
  - fallback to straight lines

## High-risk changes

- cache invalidation
- endpoint normalization
- coordinate ordering (`lon,lat` vs `lat,lon`)
- fallback behavior when OSRM fails

