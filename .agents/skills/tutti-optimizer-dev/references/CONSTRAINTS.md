# Constraint Notes

## High-risk areas

### Time windows
- Entry and exit blocks do not have symmetric flexibility.
- Feasibility depends on both official times and travel/connection buffers.

### Connection feasibility
- OSRM and fallback logic both affect whether a chain is possible.
- `positioning_minutes` and `deadhead_minutes` are not decorative; they feed PDF, diagnostics and validation.

### Capacity compatibility
- Demand and fleet range are soft/hard mixed signals depending on helper used.
- Small-service behavior has dedicated thresholds and should not be merged into generic capacity logic without tests.

### Load balance
- The optimizer does not only minimize bus count; later phases also rebalance route spread.
- Changing rebalance passes can alter output quality without changing feasibility.

## Before editing constraints

- Identify exactly which helper or phase owns the behavior.
- Search for tests covering that branch.
- Inspect diagnostics and metrics fields touched by the change.

## After editing constraints

- Re-run optimizer tests.
- Inspect whether route assignment count changes unexpectedly.
- Inspect whether spread, deadhead or infeasibility behavior moved.

