# Workspace Flow

## Files to read first

- `backend/api/workspaces.py`
- `backend/db/models.py`
- `backend/db/schemas.py`
- `backend/tests/test_workspace_crud.py`
- `backend/tests/test_workspace_publish_conflict_api.py`

## Operational model

- El workspace tiene versionado inmutable.
- `working_version` y `published_version` no son intercambiables.
- El estado derivado depende tanto del workspace como del contenido de la versión.

## High-risk areas

- publish con conflictos reales de flota
- snapshots de reconciliación stale
- restaurar o sobrescribir `working_version`
- shape mixto de `schedule_by_day` (`dict` con `schedule` vs listas legacy)

## Safe change checklist

- revisar helpers `_workspace_status_value`, `_build_readiness_summary`, `_to_workspace_response`
- revisar cómo se serializa y normaliza `schedule_by_day`
- revisar qué consume el frontend desde readiness/workflow

