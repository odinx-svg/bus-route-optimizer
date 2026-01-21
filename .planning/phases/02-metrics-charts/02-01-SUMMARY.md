---
phase: 02-metrics-charts
plan: 01
subsystem: metrics-foundation
tags: [recharts, typescript, hooks, types]

dependency-graph:
  requires:
    - 01-01 (TypeScript configuration)
  provides:
    - Recharts charting library
    - TypeScript types for schedule and metrics data
    - useMetrics hook for metric computation
  affects:
    - 02-02 (MetricCard component will consume types)
    - 02-03 (Chart components will use Recharts)
    - All future metric components

tech-stack:
  added:
    - recharts@3.6.0
  patterns:
    - Type-first development (types before hooks)
    - Memoized computed values with useMemo
    - Named exports for tree-shaking

key-files:
  created:
    - frontend/src/types/metrics.ts
    - frontend/src/hooks/useMetrics.ts
  modified:
    - frontend/package.json
    - frontend/package-lock.json

decisions:
  - id: recharts-3x
    choice: "Recharts 3.6.0 (latest 3.x)"
    rationale: "Current stable, tree-shakable with named imports"
  - id: metric-types-separate
    choice: "Types in dedicated file, not inline"
    rationale: "Reusable across components, single source of truth"
  - id: efficiency-formula
    choice: "efficiency = serviceTime / (serviceTime + deadhead) * 100"
    rationale: "Matches existing MapView.jsx calculation pattern"

metrics:
  duration: ~3 minutes
  completed: 2026-01-21
---

# Phase 02 Plan 01: Recharts + Types + useMetrics Summary

**One-liner:** Recharts 3.6.0 installed with TypeScript types and memoized useMetrics hook for fleet metric computation.

## What Was Done

### Task 1: Install Recharts
- Added recharts@3.6.0 to frontend dependencies
- 39 packages added (Recharts + dependencies)
- Verified build passes after installation

### Task 2: Create TypeScript types
- Created `frontend/src/types/` directory
- Created `metrics.ts` with 5 exports:
  - `ScheduleItem` - individual route item
  - `BusSchedule` - bus with items array
  - `Metrics` - computed fleet metrics
  - `ChartDataPoint` - chart data structure
  - `TrendDirection` - trend indicator type

### Task 3: Create useMetrics hook
- Created `frontend/src/hooks/` directory
- Created `useMetrics.ts` hook that:
  - Accepts `BusSchedule[] | null`
  - Returns `Metrics | null`
  - Memoized with useMemo for performance
  - Computes: totalBuses, totalRoutes, avgRoutesPerBus, totalDeadhead, efficiency

## Verification Results

| Check | Result |
|-------|--------|
| `npm ls recharts` | recharts@3.6.0 |
| `npx tsc --noEmit` | Pass (no errors) |
| `npm run build` | Pass (2.50s) |
| Files exist | Both created |

## Deviations from Plan

None - plan executed exactly as written.

## Technical Notes

### Type Structure
Types match the existing backend response structure observed in MapView.jsx:
- `route_id`, `start_time`, `end_time` are required
- `deadhead_minutes`, `school_name`, `contract_id` are optional
- `type` is 'entry' | 'exit' discriminator

### Efficiency Calculation
```typescript
efficiency = (serviceTime / (serviceTime + deadhead)) * 100
```
Rounded to 1 decimal place for display.

### Usage Pattern
```typescript
import { useMetrics } from '../hooks/useMetrics';
import type { BusSchedule } from '../types/metrics';

const metrics = useMetrics(schedule);
// metrics?.totalBuses, metrics?.efficiency, etc.
```

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 932b69e | feat | Install Recharts charting library |
| 1114662 | feat | Create TypeScript types for metrics system |
| 8fa6861 | feat | Create useMetrics hook for fleet calculations |

## Next Steps

- 02-02: MetricCard component using these types
- 02-03: Chart components using Recharts + ChartDataPoint type
