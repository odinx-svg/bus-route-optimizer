# Project State: Dashboard Tutti

**Last Updated:** 2026-01-21
**Current Phase:** 2 of 6 (Metrics & Charts)
**Status:** In Progress

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-19)

**Core value:** Fleet managers can optimize school bus routes through a visually impressive, metrics-driven interface
**Current focus:** Phase 2 - Metrics & Charts

## Progress

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation | Complete | 2/2 |
| 2 | Metrics & Charts | In Progress | 2/? |
| 3 | Upload Flow | Pending | 0/? |
| 4 | Control Panel | Pending | 0/? |
| 5 | Playback | Pending | 0/? |
| 6 | 3D Globe | Pending | 0/? |

Progress: ███░░░░░░░ 25%

## Recent Activity

- 2026-01-21: Completed 02-02-PLAN (AnimatedNumber + MetricCard + RoutesChart)
- 2026-01-21: Completed 02-01-PLAN (Recharts + Types + useMetrics hook)
- 2026-01-20: Phase 1 verified (7/7 success criteria passed)
- 2026-01-20: Completed 01-02-PLAN (GlassCard + NeonButton components)
- 2026-01-20: Completed 01-01-PLAN (TypeScript + Tailwind dark theme foundation)

## Accumulated Decisions

| ID | Decision | Rationale | Made In |
|----|----------|-----------|---------|
| ts-mixed-mode | allowJs: true with strict: true | Incremental migration - new TS, existing JS untouched | 01-01 |
| font-hosting | Fontsource self-hosted Inter | No third-party requests, no FOUT | 01-01 |
| tailwind-extend | Use extend pattern, not replace | Preserve existing colors | 01-01 |
| glass-no-text-color | GlassCard does not set text color | Container component - consumers control for WCAG | 01-02 |
| button-type-prop | NeonButton has type prop (button/submit) | Required for forms, defaults to 'button' for safety | 01-02 |
| framer-motion-import | Standard framer-motion import path | Works now, v11 migration path available later | 01-02 |
| recharts-3x | Recharts 3.6.0 (latest 3.x) | Current stable, tree-shakable with named imports | 02-01 |
| metric-types-separate | Types in dedicated file, not inline | Reusable across components, single source of truth | 02-01 |
| efficiency-formula | efficiency = serviceTime / (serviceTime + deadhead) * 100 | Matches existing MapView.jsx calculation pattern | 02-01 |
| spring-physics | mass: 0.8, stiffness: 75, damping: 15 | Responsive but not jarring for number animations | 02-02 |
| trend-color-mapping | neon-green for up, red-400 for down | Up = good, down = bad, matches dashboard aesthetic | 02-02 |

## Session Continuity

Last session: 2026-01-21
Stopped at: Completed 02-02-PLAN.md
Resume file: None

## Next Action

Continue with Phase 2 plans (02-03 MetricsSidebar composition, etc.)

## Context for Claude

**Brownfield project:** Existing bus-route-optimizer with working backend (FastAPI) and basic frontend (React + JS + Leaflet).

**This milestone:** Visual overhaul with Dark Command aesthetic. Same backend, new frontend presentation.

**Key constraints:**
- New code in TypeScript, existing JS stays
- No backend changes
- No Supabase (deferred)

**Research findings:**
- Use React Three Fiber + r3f-globe for 3D
- Recharts 3.0 for charts
- Framer Motion for animations
- Watch for: backdrop-blur performance, WebGL context limits

**Established in Phase 1:**
- TypeScript configured with allowJs: true
- Tailwind extended with neon-green, cyan-blue, dark-bg, glass colors
- Inter font loaded via Fontsource
- Dark background app shell active
- GlassCard component (glass morphism container)
- NeonButton component (animated with green/cyan variants)
- UI components barrel export at components/ui

**Established in Phase 2 (so far):**
- Recharts 3.6.0 installed for charting
- TypeScript types at types/metrics.ts (ScheduleItem, BusSchedule, Metrics, ChartDataPoint, TrendDirection)
- useMetrics hook at hooks/useMetrics.ts for memoized metric computation
- AnimatedNumber component (Framer Motion spring counter)
- MetricCard component (KPI display with trend indicators)
- RoutesChart component (dark-themed Recharts bar chart)

---

*State initialized: 2026-01-19*
*Last updated: 2026-01-21*
