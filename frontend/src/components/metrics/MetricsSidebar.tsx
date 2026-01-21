import { GlassCard } from '../ui';
import { MetricCard } from './MetricCard';
import { RoutesChart } from './RoutesChart';
import { useMetrics } from '../../hooks/useMetrics';
import type { BusSchedule, ChartDataPoint, TrendDirection } from '../../types/metrics';

interface MetricsSidebarProps {
  /** Schedule data from optimization result */
  schedule: BusSchedule[] | null;
}

/**
 * Determine trend direction based on metric value and thresholds.
 * Higher efficiency is good (up), lower deadhead is good (up).
 */
function getEfficiencyTrend(efficiency: number): TrendDirection {
  if (efficiency >= 80) return 'up';
  if (efficiency < 60) return 'down';
  return 'neutral';
}

function getDeadheadTrend(deadhead: number, totalRoutes: number): TrendDirection {
  // Average deadhead per route - lower is better
  const avgDeadhead = totalRoutes > 0 ? deadhead / totalRoutes : 0;
  if (avgDeadhead <= 10) return 'up';
  if (avgDeadhead > 20) return 'down';
  return 'neutral';
}

/**
 * Left sidebar displaying fleet KPIs and routes chart.
 *
 * Displays:
 * - Total buses in service
 * - Total routes assigned
 * - Fleet efficiency percentage
 * - Total deadhead time
 * - Routes by bus bar chart
 */
export function MetricsSidebar({ schedule }: MetricsSidebarProps) {
  const metrics = useMetrics(schedule);

  // Prepare chart data: routes count per bus
  const chartData: ChartDataPoint[] = schedule?.map((bus) => ({
    name: bus.bus_id,
    routes: bus.items.length,
  })) || [];

  // Empty state when no data
  if (!metrics) {
    return (
      <div className="w-72 bg-dark-bg/50 border-r border-glass-border flex flex-col p-4">
        <h2 className="text-lg font-bold text-white mb-4">Fleet Metrics</h2>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-slate-500 text-sm text-center">
            Upload a schedule file and run optimization to see metrics
          </p>
        </div>
      </div>
    );
  }

  const efficiencyTrend = getEfficiencyTrend(metrics.efficiency);
  const deadheadTrend = getDeadheadTrend(metrics.totalDeadhead, metrics.totalRoutes);

  return (
    <div className="w-72 bg-dark-bg/50 border-r border-glass-border flex flex-col p-4 space-y-4">
      {/* Header */}
      <h2 className="text-lg font-bold text-white flex items-center gap-2">
        <span className="w-1.5 h-5 bg-neon-green rounded-full shadow-neon-green"></span>
        Fleet Metrics
      </h2>

      {/* KPI Grid - 2x2 */}
      <div className="grid grid-cols-2 gap-3">
        <MetricCard
          label="Total Buses"
          value={metrics.totalBuses}
          trend="neutral"
        />
        <MetricCard
          label="Total Routes"
          value={metrics.totalRoutes}
          trend="neutral"
        />
        <MetricCard
          label="Efficiency"
          value={metrics.efficiency}
          unit="%"
          decimals={1}
          trend={efficiencyTrend}
          trendLabel={efficiencyTrend === 'up' ? 'Good' : efficiencyTrend === 'down' ? 'Low' : undefined}
        />
        <MetricCard
          label="Deadhead"
          value={metrics.totalDeadhead}
          unit="min"
          trend={deadheadTrend}
          trendLabel={deadheadTrend === 'up' ? 'Low' : deadheadTrend === 'down' ? 'High' : undefined}
        />
      </div>

      {/* Routes Chart */}
      <GlassCard padding="sm" className="flex flex-col">
        <h3 className="text-sm font-medium text-slate-400 mb-3">Routes by Bus</h3>
        <RoutesChart data={chartData} height={180} />
      </GlassCard>
    </div>
  );
}
