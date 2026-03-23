---
name: tutti-routing-maps
description: Routing y mapas en Tutti Fleet Optimizer. Usar cuando se necesite trabajar con OSRM, calculo de tiempos y geometrias, cache de rutas, visualizacion Leaflet, capas de paradas, conexiones entre rutas y fallbacks geoespaciales en backend o frontend.
---

# Tutti Routing & Maps Skill

## Proposito

Esta skill cubre la frontera geoespacial del proyecto: OSRM, cache, geometrías, mapas y fallbacks.

Activa esta skill cuando el trabajo afecte:
- `backend/router_service.py`
- `frontend/src/services/RouteService.js`
- `frontend/src/components/MapView.jsx`
- `frontend/src/components/RouteStopsLayer.jsx`
- métricas o diagnósticos de routing

## Workflow

1. Leer `references/ROUTING_MAPS.md`.
2. Revisar primero backend y frontend juntos; aquí hay contrato implícito.
3. Confirmar si el cambio afecta:
   - tiempo de viaje
   - geometría de ruta
   - cache
   - fallback a líneas rectas/haversine
   - markers o popups en mapa
4. Revisar tests de `router_service`.

## Guardrails

- No cambies URL o formato OSRM sin revisar backend y frontend.
- No elimines cache o circuit breaker sin medir impacto.
- No asumas que toda ruta tiene geometría real; hay fallback.
- No mezcles problema de visualización con problema de cálculo operativo.

## Cuando derivar

- Si el cambio repercute en feasibility del solver: complementar con `tutti-optimizer-dev`.
- Si el cambio repercute en Google Maps del PDF: complementar con `tutti-pdf-exports`.
- Si el problema es UI de interacción más que geoespacial: complementar con `tutti-frontend-dev`.

## Referencias

- `references/ROUTING_MAPS.md`

