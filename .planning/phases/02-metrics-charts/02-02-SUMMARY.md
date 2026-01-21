---
phase: 02-metrics-charts
plan: 02
subsystem: metrics-components
tags: [framer-motion, recharts, components, animation]

dependency-graph:
  requires:
    - 01-02 (GlassCard component)
    - 02-01 (TypeScript types, Recharts)
  provides:
    - AnimatedNumber spring counter component
    - MetricCard KPI display component
    - RoutesChart bar chart component
  affects:
    - 02-03 (MetricsSidebar will compose these)
    - Dashboard layout components

tech-stack:
  added: []
  patterns:
    - Framer Motion springs for animation (useSpring, useTransform)
    - Component composition (MetricCard wraps GlassCard)
    - Lucide icons for trend indicators
    - Dark theme Recharts styling

key-files:
  created:
    - frontend/src/components/metrics/AnimatedNumber.tsx
    - frontend/src/components/metrics/MetricCard.tsx
    - frontend/src/components/metrics/RoutesChart.tsx
  modified: []

decisions:
  - id: spring-physics
    choice: "mass: 0.8, stiffness: 75, damping: 15"
    rationale: "Feels responsive but not jarring for number animations"
  - id: trend-color-mapping
    choice: "neon-green for up, red-400 for down"
    rationale: "Up = good (efficiency gain), down = bad, matches dashboard aesthetic"
  - id: chart-height-explicit
    choice: "Wrapper div with explicit height, not relying on ResponsiveContainer"
    rationale: "Prevents ResponsiveContainer collapse when parent has no height"

metrics:
  duration: ~2 minutes
  completed: 2026-01-21
---

# Phase 02 Plan 02: AnimatedNumber + MetricCard + RoutesChart Summary

**One-liner:** Three metric visualization components: spring-animated counter, KPI card with trend indicators, and dark-themed Recharts bar chart.

## What Was Done

### Task 1: AnimatedNumber Component
- Created `frontend/src/components/metrics/AnimatedNumber.tsx`
- Framer Motion `useSpring` for physics-based number animation
- `useTransform` to format display without React re-renders during animation
- Props: `value`, `className`, `decimals` (optional)
- Integer values get `toLocaleString()` formatting (comma separators)

### Task 2: MetricCard Component
- Created `frontend/src/components/metrics/MetricCard.tsx`
- Wraps GlassCard from Phase 1 UI components
- Integrates AnimatedNumber for smooth value updates
- Lucide icons for trend direction (TrendingUp, TrendingDown, Minus)
- Trend color scheme:
  - Up: `text-neon-green` (positive change)
  - Down: `text-red-400` (negative change)
  - Neutral: `text-slate-400` (no change)
- Props: `label`, `value`, `unit`, `trend`, `trendLabel`, `decimals`

### Task 3: RoutesChart Component
- Created `frontend/src/components/metrics/RoutesChart.tsx`
- Recharts BarChart with named imports for tree-shaking
- Dark theme styling:
  - Grid: `#1e293b` (slate-800)
  - Text: `#94a3b8` (slate-400)
  - Axis: `#334155` (slate-700)
  - Bars: `#39FF14` (neon-green)
- X-axis rotated -45 degrees for bus ID labels
- Empty state handling with centered placeholder text
- Tooltip styled to match glass morphism aesthetic

## Verification Results

| Check | Result |
|-------|--------|
| `npx tsc --noEmit` | Pass (no errors) |
| `npm run build` | Pass (3.38s) |
| AnimatedNumber.tsx exists | Yes |
| MetricCard.tsx exists | Yes |
| RoutesChart.tsx exists | Yes |
| GlassCard import works | Yes |
| Recharts imports work | Yes |

## Deviations from Plan

None - plan executed exactly as written.

## Technical Notes

### AnimatedNumber Usage
```typescript
import { AnimatedNumber } from './AnimatedNumber';

// Integer with locale formatting
<AnimatedNumber value={1234} className="text-2xl" />
// Displays: 1,234

// Decimal with fixed precision
<AnimatedNumber value={87.5} decimals={1} />
// Displays: 87.5
```

### MetricCard Usage
```typescript
import { MetricCard } from './MetricCard';

<MetricCard
  label="Total Buses"
  value={24}
  trend="up"
  trendLabel="+3 vs last week"
/>

<MetricCard
  label="Efficiency"
  value={87.5}
  unit="%"
  decimals={1}
  trend="neutral"
/>
```

### RoutesChart Usage
```typescript
import { RoutesChart } from './RoutesChart';
import type { ChartDataPoint } from '../../types/metrics';

const data: ChartDataPoint[] = [
  { name: 'B-01', routes: 4 },
  { name: 'B-02', routes: 6 },
  { name: 'B-03', routes: 3 },
];

<RoutesChart data={data} height={250} />
```

## Commits

| Hash | Type | Description |
|------|------|-------------|
| bbe2054 | feat | Create AnimatedNumber component with spring animation |
| 277b287 | feat | Create MetricCard component with trend indicators |
| bf79fd5 | feat | Create RoutesChart bar chart with dark theme |

## Next Steps

- 02-03: MetricsSidebar that composes these components
- Wire up useMetrics hook to provide data to MetricCard instances
- Create additional chart types if needed (deadhead distribution, efficiency gauge)
