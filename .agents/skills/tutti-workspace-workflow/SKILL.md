---
name: tutti-workspace-workflow
description: Workflow de workspaces en Tutti Fleet Optimizer. Usar cuando se necesite modificar o revisar save/publish/archive, versionado, readiness states, snapshots por version y validaciones previas a publicar o restaurar planificaciones.
---

# Tutti Workspace Workflow Skill

## Proposito

Esta skill protege el flujo operativo de workspaces, donde un cambio aparentemente pequeño puede afectar publicación, flota y estados derivados.

Activa esta skill cuando el trabajo afecte:
- `backend/api/workspaces.py`
- `backend/db/models.py`
- `backend/db/schemas.py`
- payloads `schedule_by_day`, `fleet_snapshot`, `summary_metrics`
- lógica de readiness, publish, restore o archive

## Workflow

1. Leer `references/WORKSPACE_FLOW.md`.
2. Revisar `backend/api/workspaces.py` completo antes de tocar una rama puntual.
3. Si el cambio toca publicación real o reconciliación, complementar con `tutti-fleet-operations`.
4. Revisar tests:
   - `backend/tests/test_workspace_crud.py`
   - `backend/tests/test_workspace_publish_conflict_api.py`
5. Verificar si el cambio altera:
   - `status`
   - `workflow_stage`
   - `readiness_state`
   - `next_recommended_action`
   - `published_version_id` / `working_version_id`

## Guardrails

- No tratar `save`, `publish`, `active` o `draft` como simples labels de UI.
- No cambiar el shape de `schedule_by_day` sin revisar flota, frontend y PDF.
- No duplicar semántica de estado en varios sitios si ya hay helpers de derivación.
- No saltar validaciones de reconciliación o conflicto solo para “desbloquear” el flujo.

## Cuando derivar

- Si cambia flota, conflictos o reservas reales: usar `tutti-fleet-operations`.
- Si cambia el meaning de entidades o payloads: usar `tutti-domain-model`.
- Si es API general sin riesgo semántico especial: complementar con `tutti-backend-dev`.

## Referencias

- `references/WORKSPACE_FLOW.md`

