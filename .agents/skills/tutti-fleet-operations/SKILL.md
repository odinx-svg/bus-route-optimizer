---
name: tutti-fleet-operations
description: Operacion de flota en Tutti Fleet Optimizer. Usar cuando se necesite tocar asignacion real/virtual, reconciliacion operativa, publicacion de reservas, fleet snapshots, scope por empresa o UTE y compatibilidad entre schedule y vehiculos disponibles.
---

# Tutti Fleet Operations Skill

## Proposito

Esta skill encapsula la parte más operativa del sistema: la unión entre planificaciones y vehículos reales.

Activa esta skill cuando el trabajo afecte:
- `backend/api/fleet.py`
- `backend/services/fleet_assignment.py`
- `backend/services/fleet_publication.py`
- `backend/services/fleet_reconciliation.py`
- `backend/services/fleet_repository.py`
- `backend/services/fleet_scope.py`

## Workflow

1. Leer `references/FLEET_OPERATIONS.md`.
2. Revisar primero:
   - `backend/services/fleet_publication.py`
   - `backend/services/fleet_reconciliation.py`
   - `backend/api/fleet.py`
3. Revisar tests:
   - `backend/tests/test_fleet_publication.py`
   - `backend/tests/test_fleet_reconciliation.py`
   - `backend/tests/test_fleet_import_api.py`
   - `backend/tests/test_fleet_excel_import_and_scope.py`
4. Verificar si el cambio toca:
   - `assigned_vehicle_id`
   - `fleet_assignment_type`
   - `fleet_snapshot`
   - `reconciliation_snapshot`
   - published fleet assignments

## Guardrails

- No confundas preview con commit operativo.
- No trates un bus virtual como si fuera un error por definición; puede ser un estado intermedio válido.
- No ignores scope por empresa/UTE.
- No rompas compatibilidad con payloads ya publicados.
- No alteres conflictos reales entre workspaces sin revisar publicación y tests de conflicto.

## Cuando derivar

- Si el cambio nace en estados del workspace: usar `tutti-workspace-workflow`.
- Si el cambio toca entidades o meaning de payloads: usar `tutti-domain-model`.
- Si es CRUD o API base de backend sin semántica de flota: complementar con `tutti-backend-dev`.

## Referencias

- `references/FLEET_OPERATIONS.md`

