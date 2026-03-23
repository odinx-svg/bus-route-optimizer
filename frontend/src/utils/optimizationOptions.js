export const DEFAULT_OPTIMIZATION_OPTIONS = {
  objective: 'min_buses_viability',
  preferred_solver: 'auto',
  balance_load: true,
  load_balance_hard_spread_limit: 2,
  load_balance_target_band: 1,
  route_load_constraints: [],
  enable_greedy_warm_start: true,
  time_limit_seconds: null,
  fleet_scope_mode: 'company',
  fleet_scope_ute_id: null,
  virtual_bus_publish_policy: 'allow',
};

export const createEmptyRouteLoadConstraint = () => ({
  start_time: '07:30',
  end_time: '09:30',
  max_routes: 3,
  enabled: true,
  label: '',
});

export const normalizeOptimizationOptions = (raw) => {
  const source = raw && typeof raw === 'object' ? raw : {};
  const toInt = (value, fallback) => {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  };
  const spread = Math.max(1, Math.min(12, toInt(source.load_balance_hard_spread_limit, 2)));
  const objective = String(source.objective || 'min_buses_viability').toLowerCase();
  const preferredSolver = String(source.preferred_solver || 'auto').toLowerCase();
  const timeLimitRaw = source.time_limit_seconds;
  const timeLimitParsed = timeLimitRaw == null || timeLimitRaw === ''
    ? null
    : Math.max(1, Math.min(600, toInt(timeLimitRaw, 30)));
  const rawConstraints = Array.isArray(source.route_load_constraints)
    ? source.route_load_constraints
    : [];
  const constraintMap = new Map();
  rawConstraints
    .filter((item) => item && typeof item === 'object')
    .forEach((item) => {
      const startTime = String(item.start_time || item.start || '').trim();
      const endTime = String(item.end_time || item.end || '').trim();
      if (!startTime || !endTime) return;
      const label = String(item.label || '').trim() || `${startTime}-${endTime}`;
      const key = `${startTime}|${endTime}`;
      const nextValue = {
        start_time: startTime,
        end_time: endTime,
        max_routes: Math.max(1, toInt(item.max_routes, 1)),
        enabled: item.enabled !== false,
        label,
      };
      const current = constraintMap.get(key);
      if (!current) {
        constraintMap.set(key, nextValue);
        return;
      }
      constraintMap.set(key, {
        ...current,
        max_routes: Math.min(current.max_routes, nextValue.max_routes),
        enabled: current.enabled || nextValue.enabled,
        label: current.label || nextValue.label,
      });
    });
  const constraints = Array.from(constraintMap.values()).sort((a, b) => (
    `${a.start_time}-${a.end_time}`.localeCompare(`${b.start_time}-${b.end_time}`)
  ));

  return {
    objective: [
      'min_buses_viability',
      'min_buses_viability_hybrid',
      'min_km',
      'min_deadhead',
      'operational_balance',
      'publishable',
    ].includes(objective) ? objective : 'min_buses_viability',
    preferred_solver: ['auto', 'cp_sat', 'pulp_v6'].includes(preferredSolver) ? preferredSolver : 'auto',
    balance_load: source.balance_load !== false,
    load_balance_hard_spread_limit: spread,
    load_balance_target_band: Math.max(0, Math.min(spread, Math.min(6, toInt(source.load_balance_target_band, 1)))),
    route_load_constraints: constraints,
    enable_greedy_warm_start: source.enable_greedy_warm_start !== false,
    time_limit_seconds: timeLimitParsed,
    fleet_scope_mode: String(source.fleet_scope_mode || 'company').toLowerCase() === 'ute' ? 'ute' : 'company',
    fleet_scope_ute_id: String(source.fleet_scope_ute_id || '').trim() || null,
    virtual_bus_publish_policy: String(source.virtual_bus_publish_policy || 'allow').toLowerCase() === 'block'
      ? 'block'
      : 'allow',
  };
};
