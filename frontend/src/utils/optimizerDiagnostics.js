const SOLVER_LABELS = {
  auto: 'Auto inteligente',
  cp_sat: 'CP-SAT',
  pulp_v6: 'PuLP V6',
};

const OBJECTIVE_LABELS = {
  min_buses_viability: 'Minimo numero de buses',
  min_buses_viability_hybrid: 'Minimo numero de buses',
  min_km: 'Minimo kilometraje',
  min_deadhead: 'Minimo posicionamiento',
  operational_balance: 'Equilibrio operativo',
  publishable: 'Mas publicable',
};

const SOLVER_REASON_LABELS = {
  'auto:fallback_cp_sat_unavailable': 'CP-SAT no disponible',
  'auto:fallback_cp_sat_experimental': 'CP-SAT aun experimental',
  'auto:fallback_route_load_constraints': 'Reglas horarias avanzadas activas',
  'auto:fallback_balance_load_priority': 'Balanceo operativo prioritario',
  'auto:fallback_operational_objective': 'Objetivo operativo conservador',
  'auto:fallback_large_min_buses_instance': 'Instancia grande de minimo buses',
  'auto:fallback_instance_too_large': 'Instancia grande',
  'auto:cp_sat_candidate': 'Caso apto para CP-SAT',
  'explicit:cp_sat': 'CP-SAT solicitado',
  'explicit:fallback_cp_sat_unavailable': 'CP-SAT pedido pero no disponible',
  'explicit:pulp_v6': 'PuLP V6 solicitado',
  'fallback:unknown_solver': 'Solver no reconocido',
  'empty:no_routes': 'Sin rutas en el dia',
};

const SOLVER_REASON_DETAILS = {
  'auto:fallback_cp_sat_unavailable': 'Auto mantiene PuLP V6 porque OR-Tools no esta disponible.',
  'auto:fallback_cp_sat_experimental': 'Auto mantiene PuLP V6 porque CP-SAT sigue en modo experimental para datasets reales.',
  'auto:fallback_route_load_constraints': 'Auto mantiene PuLP V6 porque hay ventanas o limites de reparto activos.',
  'auto:fallback_balance_load_priority': 'Auto mantiene PuLP V6 porque el balanceo operativo pesa mas que la eficiencia pura.',
  'auto:fallback_operational_objective': 'Auto mantiene PuLP V6 porque el objetivo elegido prioriza estabilidad operativa.',
  'auto:fallback_large_min_buses_instance': 'Auto mantiene PuLP V6 porque el caso es grande y busca reducir buses.',
  'auto:fallback_instance_too_large': 'Auto mantiene PuLP V6 porque el caso es grande para esta fase de CP-SAT.',
  'auto:cp_sat_candidate': 'Auto puede usar CP-SAT porque el caso es apto para priorizar eficiencia.',
  'explicit:cp_sat': 'Se forzo CP-SAT desde reglas.',
  'explicit:fallback_cp_sat_unavailable': 'Se pidio CP-SAT, pero no esta disponible en este entorno.',
  'explicit:pulp_v6': 'Se forzo PuLP V6 desde reglas.',
  'fallback:unknown_solver': 'La preferencia no se reconocio y el motor volvio a PuLP V6.',
  'empty:no_routes': 'No hay rutas que optimizar en este dia.',
};

export const getSolverDisplayLabel = (value) => {
  const key = String(value || '').trim().toLowerCase();
  return SOLVER_LABELS[key] || String(value || 'Auto inteligente');
};

export const getObjectiveDisplayLabel = (value) => {
  const key = String(value || '').trim().toLowerCase();
  return OBJECTIVE_LABELS[key] || String(value || 'Minimo numero de buses');
};

export const getSolverReasonLabel = (diagnostics = null) => {
  const selection = diagnostics?.solver_selection || {};
  if (selection.reason_label) return String(selection.reason_label);
  const code = String(diagnostics?.solver_selection_reason || '').trim();
  return SOLVER_REASON_LABELS[code] || 'Decision sin detalle';
};

export const getSolverReasonDetail = (diagnostics = null) => {
  const selection = diagnostics?.solver_selection || {};
  if (selection.reason_detail) return String(selection.reason_detail);
  const code = String(diagnostics?.solver_selection_reason || '').trim();
  return SOLVER_REASON_DETAILS[code] || 'El motor no devolvio detalle adicional para esta decision.';
};

export const getPreferredSolverHint = (options = {}, routeCount = null) => {
  const preferredSolver = String(options?.preferred_solver || 'auto').trim().toLowerCase();

  if (preferredSolver === 'cp_sat') {
    return 'Forzando CP-SAT: util para comparar motores y para casos pequenos o medianos orientados a eficiencia.';
  }
  if (preferredSolver === 'pulp_v6') {
    return 'Forzando PuLP V6: opcion mas estable cuando pesan las reglas operativas, el balanceo o la publicabilidad.';
  }
  return 'Auto prioriza PuLP V6 por seguridad operativa. CP-SAT sigue disponible solo para pruebas forzadas mientras madura.';
};

export const getPrimarySelectedSolver = (summaryMetrics = null, fallback = 'auto') => {
  const usage = summaryMetrics && typeof summaryMetrics === 'object' ? summaryMetrics.solver_usage : null;
  if (!usage || typeof usage !== 'object') {
    return String(summaryMetrics?.requested_solver || fallback || 'auto');
  }
  const ranked = Object.entries(usage)
    .map(([solver, count]) => [solver, Number(count || 0)])
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1]);
  if (ranked.length === 0) {
    return String(summaryMetrics?.requested_solver || fallback || 'auto');
  }
  return String(ranked[0][0]);
};

export const getSolverUsageSummary = (summaryMetrics = null) => {
  const usage = summaryMetrics && typeof summaryMetrics === 'object' ? summaryMetrics.solver_usage : null;
  if (!usage || typeof usage !== 'object') {
    const requested = String(summaryMetrics?.requested_solver || '').trim();
    return requested ? `Pedido: ${getSolverDisplayLabel(requested)}` : 'Sin diagnostico de solver';
  }
  const ranked = Object.entries(usage)
    .map(([solver, count]) => [solver, Number(count || 0)])
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1]);
  if (ranked.length === 0) {
    const requested = String(summaryMetrics?.requested_solver || '').trim();
    return requested ? `Pedido: ${getSolverDisplayLabel(requested)}` : 'Sin diagnostico de solver';
  }
  return ranked
    .slice(0, 2)
    .map(([solver, count]) => `${getSolverDisplayLabel(solver)}: ${count} dia${count === 1 ? '' : 's'}`)
    .join(' | ');
};
