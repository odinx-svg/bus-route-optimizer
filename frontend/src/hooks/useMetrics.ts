import { useMemo } from 'react';
import type { BusSchedule, Metrics } from '../types/metrics';

/**
 * Compute fleet metrics from schedule data.
 * Memoized for performance - only recalculates when schedule changes.
 */
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
