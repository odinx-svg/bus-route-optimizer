import { GlassCard } from '../ui';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { AnimatedNumber } from './AnimatedNumber';
import type { TrendDirection } from '../../types/metrics';

interface MetricCardProps {
  /** Display label (e.g., "Total Buses") */
  label: string;
  /** Numeric value to display */
  value: number;
  /** Unit suffix (e.g., "%", "min", "km") */
  unit?: string;
  /** Trend direction for indicator arrow */
  trend?: TrendDirection;
  /** Optional trend description (e.g., "vs last week") */
  trendLabel?: string;
  /** Number of decimal places */
  decimals?: number;
}

const trendConfig = {
  up: {
    icon: TrendingUp,
    colorClass: 'text-neon-green',
    bgClass: 'bg-neon-green/10',
  },
  down: {
    icon: TrendingDown,
    colorClass: 'text-red-400',
    bgClass: 'bg-red-400/10',
  },
  neutral: {
    icon: Minus,
    colorClass: 'text-slate-400',
    bgClass: 'bg-slate-400/10',
  },
};

/**
 * KPI metric card with animated value and trend indicator.
 * Uses GlassCard from Phase 1 for consistent styling.
 */
export function MetricCard({
  label,
  value,
  unit,
  trend = 'neutral',
  trendLabel,
  decimals = 0,
}: MetricCardProps) {
  const { icon: TrendIcon, colorClass, bgClass } = trendConfig[trend];

  return (
    <GlassCard padding="sm" className="flex flex-col min-w-0">
      {/* Label */}
      <span className="text-xs text-slate-400 uppercase tracking-wider truncate">
        {label}
      </span>

      {/* Value + Unit */}
      <div className="flex items-baseline gap-1 mt-1">
        <AnimatedNumber
          value={value}
          decimals={decimals}
          className="text-2xl font-bold text-white"
        />
        {unit && (
          <span className="text-sm text-slate-400">{unit}</span>
        )}
      </div>

      {/* Trend indicator */}
      {trend !== 'neutral' && (
        <div className={`flex items-center gap-1 mt-2 ${colorClass}`}>
          <div className={`p-0.5 rounded ${bgClass}`}>
            <TrendIcon size={12} />
          </div>
          {trendLabel && (
            <span className="text-xs">{trendLabel}</span>
          )}
        </div>
      )}
    </GlassCard>
  );
}
