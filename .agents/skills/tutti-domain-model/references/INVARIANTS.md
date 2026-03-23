# Invariants

## Route and timing

- Una `Route` debe tener `type` valido: `entry` o `exit`.
- `entry` usa `arrival_time`; `exit` usa `departure_time`.
- Las rutas deben conservar `stops` ordenados por `order`.

## Schedule

- Un `BusSchedule` no debe perder items al serializar/deserializar.
- Un `ScheduleItem` debe mantener consistencia entre:
  - `route_id`
  - `type`
  - horario final
  - stops
- `positioning_minutes` y `deadhead_minutes` afectan validacion, margenes y PDF.

## Capacity

- `capacity_needed` representa demanda operativa.
- `vehicle_capacity_min/max` representa rango de flota compatible.
- No sustituir uno por otro sin revisar optimizer y fleet assignment.

## Workspace and fleet

- Publicar un workspace no es un cambio cosmetico: puede comprometer reservas de flota.
- Los estados `draft/active/inactive` o equivalentes deben mantener semantica operativa.
- Reconciliation y publication no son capas independientes; comparten snapshots y validaciones.

## Safe change checklist

- Revisar `backend/models.py`
- Revisar `backend/db/models.py`
- Revisar `backend/db/schemas.py`
- Revisar tests de modelos, workspace y fleet
- Verificar impacto en PDF y frontend si cambian nombres de campos

