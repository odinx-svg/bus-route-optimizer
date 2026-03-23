import { ALL_DAYS } from './days';

const getBusItems = (bus) => {
  if (Array.isArray(bus?.items)) return bus.items;
  if (Array.isArray(bus?.routes)) return bus.routes;
  return [];
};

export const buildScheduleStats = (buses = []) => {
  const totalBuses = Array.isArray(buses) ? buses.length : 0;
  const allItems = (buses || []).flatMap((bus) => getBusItems(bus));
  const totalRoutes = allItems.length;
  const totalEntries = allItems.filter((item) => item?.type === 'entry').length;
  const totalExits = allItems.filter((item) => item?.type === 'exit').length;
  const routesPerBus = (buses || [])
    .map((bus) => getBusItems(bus).length)
    .filter((count) => Number.isFinite(count) && count > 0);
  const avgRoutesPerBus = totalBuses > 0
    ? Math.round((totalRoutes / totalBuses) * 10) / 10
    : 0;
  const sortedCounts = [...routesPerBus].sort((a, b) => a - b);
  const minRoutes = sortedCounts.length > 0 ? sortedCounts[0] : 0;
  const maxRoutes = sortedCounts.length > 0 ? sortedCounts[sortedCounts.length - 1] : 0;
  const spread = Math.max(0, maxRoutes - minRoutes);
  const mid = Math.floor(sortedCounts.length / 2);
  const medianRoutes = sortedCounts.length === 0
    ? 0
    : (
        sortedCounts.length % 2 === 0
          ? (sortedCounts[mid - 1] + sortedCounts[mid]) / 2
          : sortedCounts[mid]
      );
  const absDev = sortedCounts.length === 0
    ? 0
    : sortedCounts.reduce((sum, value) => sum + Math.abs(value - medianRoutes), 0);

  return {
    total_buses: totalBuses,
    total_entries: totalEntries,
    total_exits: totalExits,
    avg_routes_per_bus: avgRoutesPerBus,
    median_routes_per_bus: Number(medianRoutes.toFixed(2)),
    min_routes_per_bus: minRoutes,
    max_routes_per_bus: maxRoutes,
    load_spread_routes: spread,
    load_abs_dev_sum: Number(absDev.toFixed(2)),
    load_balanced: spread <= 2,
  };
};

export const buildDayScheduleData = ({ buses = [], metadata = null, unassignedRoutes = [] } = {}) => ({
  schedule: Array.isArray(buses) ? buses : [],
  stats: buildScheduleStats(buses),
  metadata: metadata || {},
  unassigned_routes: Array.isArray(unassignedRoutes) ? unassignedRoutes : [],
});

export const createEmptyScheduleByDay = () => (
  ALL_DAYS.reduce((acc, day) => {
    acc[day] = { schedule: [], stats: null };
    return acc;
  }, {})
);

export const createEmptyPinnedBusesByDay = () => (
  ALL_DAYS.reduce((acc, day) => {
    acc[day] = [];
    return acc;
  }, {})
);

export const normalizeWorkspaceScheduleByDay = (scheduleByDay) => {
  const base = createEmptyScheduleByDay();
  if (!scheduleByDay || typeof scheduleByDay !== 'object') return base;

  for (const day of ALL_DAYS) {
    const dayPayload = scheduleByDay?.[day];
    if (!dayPayload) continue;
    const buses = Array.isArray(dayPayload?.schedule)
      ? dayPayload.schedule
      : (Array.isArray(dayPayload?.buses) ? dayPayload.buses : []);
    base[day] = {
      ...buildDayScheduleData({
        buses,
        metadata: dayPayload?.metadata || {},
        unassignedRoutes: dayPayload?.unassigned_routes || [],
      }),
      stats: dayPayload?.stats || buildScheduleStats(buses),
    };
  }
  return base;
};
