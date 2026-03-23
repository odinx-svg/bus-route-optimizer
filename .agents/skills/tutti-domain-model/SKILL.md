---
name: tutti-domain-model
description: Dominio operativo de Tutti Fleet Optimizer. Usar cuando se necesite entender o modificar las entidades core del sistema, sus invariantes, la semantica de Route/Stop/Schedule/Workspace/Fleet y el significado operativo de los datos que circulan entre parser, optimizer, flota, PDF y UI.
---

# Tutti Domain Model Skill

## Proposito

Esta skill evita errores semanticos al tocar modelos, payloads, validaciones o logica de negocio.

Activa esta skill cuando el trabajo afecte:
- `backend/models.py`
- `backend/db/models.py`
- `backend/db/schemas.py`
- `backend/api/workspaces.py`
- `backend/services/fleet_*.py`
- payloads de schedule, workspace o fleet

## Modelo mental minimo

- `Stop`: parada con coordenadas, orden, tiempo acumulado y pasajeros.
- `Route`: definicion de un servicio escolar en un sentido (`entry` o `exit`) con sus `stops`, horario y demanda.
- `ScheduleItem`: una ruta ya colocada dentro del plan de un bus, con horario final, posicionamiento y capacidad.
- `BusSchedule`: plan diario de un bus con varios `ScheduleItem`.
- Workspace: snapshot versionado del resultado operativo; publicar tiene efectos reales sobre flota y reconciliacion.
- Fleet assignment: binding entre buses del schedule y vehiculos reales o virtuales.

No inventes una entidad `Expedition` separada si el codigo actual no la modela asi. En este repo el equivalente operativo suele viajar como `Route` o `ScheduleItem`, segun la fase del pipeline.

## Workflow

1. Leer `references/DOMAIN.md`.
2. Si el cambio toca reglas de negocio, leer `references/INVARIANTS.md`.
3. Revisar los modelos reales en:
   - `backend/models.py`
   - `backend/db/models.py`
   - `backend/db/schemas.py`
4. Buscar tests existentes:
   - `backend/tests/test_models.py`
   - `backend/tests/test_workspace_crud.py`
   - `backend/tests/test_fleet_*.py`
5. Verificar que el cambio mantiene compatibilidad entre parser, optimizer, publish y PDF.

## Guardrails

- No renombres campos de payload sin revisar parser, optimizer, PDF, frontend y tests.
- No conviertas conceptos operativos en conceptos de UI.
- No simplifiques `entry` y `exit` como si fueran el mismo flujo.
- No asumas que `capacity_needed` y `vehicle_capacity_*` son equivalentes.
- No cambies estados de workspace o fleet sin seguir la semantica ya publicada.

## Cuando derivar

- Si el cambio entra en parsing Excel: usar `tutti-excel-ingestion`.
- Si modifica constraints, bloques u orden del solver: usar `tutti-optimizer-dev`.
- Si el cambio es backend general sin conflicto semantico: complementar con `tutti-backend-dev`.

## Referencias

- `references/DOMAIN.md`
- `references/INVARIANTS.md`

