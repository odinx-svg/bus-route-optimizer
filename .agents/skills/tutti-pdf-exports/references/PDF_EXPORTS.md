# PDF Exports

## Files to read first

- `backend/pdf_service.py`
- `backend/main.py`
- `frontend/src/App.jsx`
- `frontend/src/services/api.service.ts`

## Important behavior

- `generate_schedule_pdf(schedule, day_name=None)` es el punto central.
- El PDF genera:
  - página resumen
  - páginas por bus
  - tabla tipo Excel
  - link de Google Maps por bus
- El link se construye desde `stops` con `lat/lon`, no desde nombres de ruta.

## High-risk changes

- cambiar shape de `items`
- tocar ordenado por tiempo
- tocar `generate_google_maps_link`
- asumir que siempre hay coordenadas suficientes

