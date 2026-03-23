# Fleet Operations

## Files to read first

- `backend/services/fleet_publication.py`
- `backend/services/fleet_reconciliation.py`
- `backend/services/fleet_assignment.py`
- `backend/api/fleet.py`
- `backend/api/workspaces.py`

## Core concepts

- `real` vs `virtual`
- preview vs publish
- reconciliation snapshot
- conflict detection against `published_fleet_assignments`
- company scope vs UTE scope

## High-risk changes

- changing conflict overlap logic
- changing vehicle requirement calculation
- changing assignment payload shape
- removing virtual fallback behavior

## Tests to keep close

- `backend/tests/test_fleet_publication.py`
- `backend/tests/test_fleet_reconciliation.py`
- `backend/tests/test_workspace_publish_conflict_api.py`

