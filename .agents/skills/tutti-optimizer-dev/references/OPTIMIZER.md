# Optimizer Map

## Main files

- Primary solver: `backend/optimizer_v6.py`
- Legacy context:
  - `backend/optimizer_v4.py`
  - `backend/optimizer_v5.py`
  - `backend/optimizer_lns.py`
  - `backend/optimizer_multi.py`
- Related services:
  - `backend/router_service.py`
  - `backend/services/optimization_pipeline_service.py`

## Core responsibilities in V6

- Block classification for morning entry / early exit / late entry / late exit
- Travel time estimation via OSRM or haversine fallback
- Intra-block chain building
- Cross-block matching
- Capacity compatibility
- Load balancing passes
- Final schedule materialization into `ScheduleItem`

## Constants worth treating as operational policy

- `MAX_ENTRY_SHIFT_MINUTES`
- `MAX_EXIT_EARLY_SHIFT_MINUTES`
- `MAX_EXIT_LATE_SHIFT_MINUTES`
- `MIN_CONNECTION_BUFFER_MINUTES`
- `DEADHEAD_BUFFER_MINUTES`
- `CAPACITY_MAX_DIFF`
- `ILP_TIME_LIMIT`
- `LOCAL_SEARCH_TIME_LIMIT`

Do not change these blindly. They are not cosmetic tuning knobs.

## Minimum review set for optimizer changes

- `backend/optimizer_v6.py`
- `backend/tests/test_optimizer.py`
- `backend/tests/test_optimizer_advanced.py`
- `backend/tests/test_pipeline_load_balance.py`
- any code reading `deadhead_minutes` or `positioning_minutes`

