# Phase 2: Metrics & Charts - Research

**Researched:** 2026-01-21
**Domain:** React dashboard metrics visualization, Recharts charting, Framer Motion animations
**Confidence:** HIGH

## Summary

This research investigates how to build a KPI sidebar and statistics visualization using the existing Phase 1 foundation (GlassCard, NeonButton, Tailwind theme, Framer Motion). The application already has a working MapView component with basic metrics display that provides a template for the sidebar pattern.

Recharts v3.6.0 is the current stable version and is already available in the npm registry. It's the standard choice for React charting, built on D3 with declarative components. For dark theme support, Recharts requires explicit color configuration on each component (tick, stroke, fill props) rather than a global theme object.

Framer Motion's `useSpring` and `useTransform` hooks provide performant animated number counters without causing React re-renders. This pairs well with the existing Framer Motion installation (v12.27.5) and creates visual polish for KPI value changes.

**Primary recommendation:** Create MetricsSidebar as a dedicated component with MetricCard children, using GlassCard for containers. Install Recharts for the bar chart. Use Framer Motion's useSpring for animated counters on metric values.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| recharts | 3.6.0 | Declarative React charts | Most popular React chart lib, tree-shakeable, excellent TS support |
| framer-motion | 12.27.5 (installed) | Number animations | Already in project, useSpring is performant and simple |
| lucide-react | 0.263.1 (installed) | Trend indicator icons | Already in project, has TrendingUp/TrendingDown icons |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| GlassCard | (local) | Metric card container | Wrap each KPI for consistent styling |
| NeonButton | (local) | Not needed this phase | Future phase controls only |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Recharts | Victory | Victory has more complex API, Recharts simpler for bar charts |
| Recharts | Chart.js | Chart.js requires canvas, Recharts is SVG/React-native |
| Custom counter | react-countup | useSpring already available, no new dependency needed |

**Installation:**
```bash
cd frontend && npm install recharts
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
├── components/
│   ├── ui/                    # Phase 1 foundation
│   │   ├── GlassCard.tsx
│   │   ├── NeonButton.tsx
│   │   └── index.ts
│   ├── metrics/               # Phase 2 NEW
│   │   ├── MetricsSidebar.tsx # Container with all metrics
│   │   ├── MetricCard.tsx     # Single KPI with trend
│   │   ├── AnimatedNumber.tsx # Framer Motion counter
│   │   ├── RoutesChart.tsx    # Recharts bar chart
│   │   └── index.ts           # Barrel export
│   └── MapView.jsx            # Existing (will integrate sidebar)
├── hooks/
│   └── useMetrics.ts          # Compute metrics from schedule data
└── types/
    └── metrics.ts             # MetricData, ChartData types
```

### Pattern 1: MetricCard with GlassCard
**What:** Reusable KPI card showing value, label, trend indicator
**When to use:** For each individual metric in sidebar
**Example:**
```typescript
// Source: Phase 1 GlassCard + lucide-react icons
import { GlassCard } from '../ui';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { AnimatedNumber } from './AnimatedNumber';

interface MetricCardProps {
  label: string;
  value: number;
  unit?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
}

export function MetricCard({ label, value, unit, trend, trendValue }: MetricCardProps) {
  const TrendIcon = trend === 'up' ? TrendingUp : TrendingDown;
  const trendColor = trend === 'up' ? 'text-neon-green' : 'text-red-400';

  return (
    <GlassCard padding="sm" className="flex flex-col">
      <span className="text-xs text-slate-400 uppercase tracking-wider">{label}</span>
      <div className="flex items-baseline gap-1 mt-1">
        <AnimatedNumber value={value} className="text-2xl font-bold text-white" />
        {unit && <span className="text-sm text-slate-400">{unit}</span>}
      </div>
      {trend && trend !== 'neutral' && (
        <div className={`flex items-center gap-1 mt-2 ${trendColor}`}>
          <TrendIcon size={14} />
          <span className="text-xs">{trendValue}</span>
        </div>
      )}
    </GlassCard>
  );
}
```

### Pattern 2: Animated Number Counter
**What:** Framer Motion spring-based number animation
**When to use:** For smooth transitions when metric values change
**Example:**
```typescript
// Source: BuildUI recipe + Framer Motion docs
import { motion, useSpring, useTransform } from 'framer-motion';
import { useEffect } from 'react';

interface AnimatedNumberProps {
  value: number;
  className?: string;
  formatOptions?: Intl.NumberFormatOptions;
}

export function AnimatedNumber({ value, className, formatOptions }: AnimatedNumberProps) {
  const spring = useSpring(value, { mass: 0.8, stiffness: 75, damping: 15 });
  const display = useTransform(spring, (current) =>
    Math.round(current).toLocaleString(undefined, formatOptions)
  );

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  return <motion.span className={className}>{display}</motion.span>;
}
```

### Pattern 3: Recharts Dark Theme Bar Chart
**What:** Responsive bar chart with dark theme colors
**When to use:** For routes by day/week visualization
**Example:**
```typescript
// Source: Recharts API docs + dark theme configuration
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

interface ChartData {
  name: string;
  routes: number;
}

interface RoutesChartProps {
  data: ChartData[];
}

export function RoutesChart({ data }: RoutesChartProps) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fill: '#94a3b8', fontSize: 12 }}
          axisLine={{ stroke: '#334155' }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: '#94a3b8', fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '8px',
            color: '#fff'
          }}
        />
        <Bar
          dataKey="routes"
          fill="#39FF14"
          radius={[4, 4, 0, 0]}
          maxBarSize={40}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

### Pattern 4: useMetrics Hook
**What:** Custom hook to compute metrics from schedule data
**When to use:** Centralize metric calculations, memoize for performance
**Example:**
```typescript
// Source: Existing MapView.jsx metrics calculation
import { useMemo } from 'react';
import type { BusSchedule } from '../types';

interface Metrics {
  totalBuses: number;
  totalRoutes: number;
  avgRoutesPerBus: number;
  totalDeadhead: number;
  efficiency: number;
  totalKm?: number;
}

export function useMetrics(schedule: BusSchedule[] | null): Metrics | null {
  return useMemo(() => {
    if (!schedule || schedule.length === 0) return null;

    let totalRoutes = 0;
    let totalDeadhead = 0;
    let totalServiceTime = 0;

    const parseTime = (t: string): number => {
      if (!t) return 0;
      const [h, m] = t.split(':').map(Number);
      return h * 60 + m;
    };

    schedule.forEach(bus => {
      totalRoutes += bus.items.length;
      bus.items.forEach(item => {
        totalDeadhead += item.deadhead_minutes || 0;
        const start = parseTime(item.start_time);
        const end = parseTime(item.end_time);
        totalServiceTime += end - start;
      });
    });

    const avgRoutesPerBus = totalRoutes / schedule.length;
    const efficiency = totalServiceTime > 0
      ? (totalServiceTime / (totalServiceTime + totalDeadhead)) * 100
      : 0;

    return {
      totalBuses: schedule.length,
      totalRoutes,
      avgRoutesPerBus: Math.round(avgRoutesPerBus * 10) / 10,
      totalDeadhead,
      efficiency: Math.round(efficiency * 10) / 10,
    };
  }, [schedule]);
}
```

### Anti-Patterns to Avoid
- **Setting React state for animated values:** useSpring sets innerHTML directly, much more performant than setState re-renders
- **Hardcoding hex colors in charts:** Use Tailwind color values or CSS variables for theme consistency
- **Making ResponsiveContainer without min-height:** Chart won't render properly, always set min-h-[200px] on container
- **Using global Recharts theme:** Recharts doesn't have a global theme API, must configure each component

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Number animation | Custom setInterval counter | Framer Motion useSpring | Physics-based, no re-renders, already installed |
| Bar charts | SVG/Canvas from scratch | Recharts BarChart | Responsive, tooltips, accessibility built-in |
| Trend indicators | Custom arrow SVGs | lucide-react TrendingUp/Down | Already installed, consistent icon style |
| Responsive charts | Width calculations | ResponsiveContainer | Handles resize events, debouncing |

**Key insight:** The existing MapView.jsx already has a metrics calculation pattern that can be extracted into a reusable hook. Recharts handles all chart complexity (scales, axes, tooltips, animations).

## Common Pitfalls

### Pitfall 1: ResponsiveContainer Height Collapse
**What goes wrong:** Chart renders as 0px height because ResponsiveContainer needs explicit height
**Why it happens:** ResponsiveContainer uses 100% height but parent has no height
**How to avoid:** Always set `min-h-[200px]` or explicit height on wrapper element
**Warning signs:** Chart doesn't appear, no console errors

### Pitfall 2: Recharts Tree-Shaking
**What goes wrong:** Entire Recharts bundle included (200KB+) instead of just used components
**Why it happens:** Using `import Recharts from 'recharts'` instead of named imports
**How to avoid:** Always use named imports: `import { BarChart, Bar } from 'recharts'`
**Warning signs:** Large bundle size in build output

### Pitfall 3: Animated Number Infinite Loop
**What goes wrong:** useEffect triggers infinite re-renders
**Why it happens:** Including `spring` in dependency array AND calling spring.set() in same effect
**How to avoid:** Follow exact pattern from BuildUI recipe with proper deps
**Warning signs:** Browser freezes, memory spike

### Pitfall 4: Dark Theme Text Invisibility
**What goes wrong:** Chart labels invisible on dark background
**Why it happens:** Recharts defaults to black text
**How to avoid:** Always set `tick={{ fill: '#94a3b8' }}` on XAxis/YAxis
**Warning signs:** Chart appears but no axis labels visible

### Pitfall 5: Sidebar Layout Shift
**What goes wrong:** Main content jumps when sidebar appears
**Why it happens:** Sidebar inserted without fixed width container
**How to avoid:** Use flexbox with fixed sidebar width, let main content flex-1
**Warning signs:** Map or content area resizes unexpectedly

## Code Examples

### Complete MetricsSidebar Integration
```typescript
// Source: Combining GlassCard, MetricCard, RoutesChart patterns
import { GlassCard } from '../ui';
import { MetricCard } from './MetricCard';
import { RoutesChart } from './RoutesChart';
import { useMetrics } from '../../hooks/useMetrics';

interface MetricsSidebarProps {
  schedule: BusSchedule[] | null;
  previousMetrics?: Metrics | null; // For trend calculation
}

export function MetricsSidebar({ schedule, previousMetrics }: MetricsSidebarProps) {
  const metrics = useMetrics(schedule);

  if (!metrics) return null;

  // Calculate trends (compare to previous if available)
  const busTrend = previousMetrics
    ? (metrics.totalBuses < previousMetrics.totalBuses ? 'down' : 'up')
    : 'neutral';

  // Prepare chart data (routes by bus or by day)
  const chartData = schedule?.map((bus, i) => ({
    name: bus.bus_id,
    routes: bus.items.length
  })) || [];

  return (
    <div className="w-72 bg-dark-bg border-r border-glass-border flex flex-col p-4 space-y-4">
      <h2 className="text-lg font-bold text-white">Fleet Metrics</h2>

      <div className="grid grid-cols-2 gap-3">
        <MetricCard
          label="Total Buses"
          value={metrics.totalBuses}
          trend={busTrend}
          trendValue={busTrend === 'down' ? 'Optimized' : undefined}
        />
        <MetricCard
          label="Total Routes"
          value={metrics.totalRoutes}
        />
        <MetricCard
          label="Efficiency"
          value={metrics.efficiency}
          unit="%"
          trend={metrics.efficiency > 80 ? 'up' : 'down'}
        />
        <MetricCard
          label="Deadhead"
          value={metrics.totalDeadhead}
          unit="min"
          trend={metrics.totalDeadhead < 100 ? 'up' : 'down'}
        />
      </div>

      <GlassCard padding="sm">
        <h3 className="text-sm font-medium text-slate-400 mb-2">Routes by Bus</h3>
        <RoutesChart data={chartData} />
      </GlassCard>
    </div>
  );
}
```

### TypeScript Interfaces for Data
```typescript
// types/metrics.ts
export interface ScheduleItem {
  route_id: string;
  start_time: string;
  end_time: string;
  type: 'entry' | 'exit';
  original_start_time?: string;
  time_shift_minutes?: number;
  deadhead_minutes?: number;
  school_name?: string;
  contract_id?: string;
}

export interface BusSchedule {
  bus_id: string;
  items: ScheduleItem[];
}

export interface Metrics {
  totalBuses: number;
  totalRoutes: number;
  avgRoutesPerBus: number;
  totalDeadhead: number;
  efficiency: number;
}

export interface ChartDataPoint {
  name: string;
  routes: number;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Recharts v2 | Recharts v3.6.0 | 2024 | New `responsive` prop on charts, better tree-shaking |
| framer-motion | motion (v5+) | Jan 2026 | Package rename, same API, smaller bundle |
| Custom CSS animations | useSpring | Ongoing | Physics-based feels more natural |
| Chart.js canvas | Recharts SVG | Established | Better React integration, accessibility |

**Current notes:**
- Recharts 3.x is stable and recommended
- framer-motion is migrating to "motion" package name but v12 API unchanged
- lucide-react has TrendingUp, TrendingDown, ArrowUp, ArrowDown icons available

## Open Questions

Things that couldn't be fully resolved:

1. **Previous metrics for trend calculation**
   - What we know: Trends require comparing current vs previous values
   - What's unclear: Where to store "previous" optimization result
   - Recommendation: Start with static trends based on thresholds (efficiency > 80% = good), add history in future phase

2. **Km calculation**
   - What we know: Backend has distance data in OSRM calls
   - What's unclear: Whether total km is returned in schedule response
   - Recommendation: Check backend response, may need API enhancement or compute from route data

3. **Routes by week chart data**
   - What we know: Requirement mentions "day/week" bar chart
   - What's unclear: Current data doesn't have day-of-week assignment
   - Recommendation: Start with "routes by bus" chart, add day grouping when data available

## Sources

### Primary (HIGH confidence)
- Recharts official examples: https://recharts.org/en-US/examples/SimpleBarChart
- Framer Motion useSpring docs: https://motion.dev/docs/react-animation
- lucide-react icons: https://lucide.dev/icons/

### Secondary (MEDIUM confidence)
- BuildUI Animated Number recipe: https://buildui.com/recipes/animated-number - verified working pattern
- Recharts dark theme GitHub issue #548: https://github.com/recharts/recharts/issues/548 - tick fill solution
- shadcn/ui chart docs: https://ui.shadcn.com/docs/components/chart - CSS variable theming approach

### Tertiary (LOW confidence)
- Various blog posts on KPI cards - patterns synthesized from multiple sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Recharts is established, Framer Motion already in project
- Architecture: HIGH - Patterns based on existing MapView.jsx code
- Pitfalls: MEDIUM - Based on GitHub issues and common errors
- Code examples: HIGH - Tested patterns from official docs

**Research date:** 2026-01-21
**Valid until:** 2026-02-21 (Recharts stable, patterns well-established)
