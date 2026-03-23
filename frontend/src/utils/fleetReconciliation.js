export const createFleetReconciliationModalState = () => ({
  open: false,
  items: [],
  companyMix: null,
  requiredBusCount: 0,
  realBoundCount: 0,
  pendingRealReconciliationCount: 0,
  availableRealVehicleCount: 0,
  companiesAvailable: 0,
  estimatedVirtualRemaining: 0,
  reconciliationSnapshot: null,
  dayLabel: '',
  scopeLabel: '',
  scopeVehicleCount: 0,
  scopeMode: 'company',
  busId: null,
  operationalSummary: null,
  candidateRejectionReasons: null,
  applying: false,
  intent: 'reconcile',
  pendingPublishPayload: null,
  previewDay: null,
  publishSuccessTitle: '',
  publishSuccessMessage: '',
});

export const formatMinuteValue = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '-';
  const normalized = Math.max(0, Math.round(numeric));
  const hours = String(Math.floor(normalized / 60)).padStart(2, '0');
  const minutes = String(normalized % 60).padStart(2, '0');
  return `${hours}:${minutes}`;
};

export const buildCompanyMixFallback = (items = []) => {
  const counters = new Map();
  (Array.isArray(items) ? items : []).forEach((row) => {
    const suggestions = Array.isArray(row?.suggested_real_vehicles || row?.suggestions)
      ? (row.suggested_real_vehicles || row.suggestions)
      : [];
    if (suggestions.length === 0) return;
    const best = suggestions[0] || {};
    const companyId = String(best.company_id || 'unassigned');
    const companyName = String(best.company_name || 'Empresa sin identificar');
    const current = counters.get(companyId) || {
      company_id: best.company_id || null,
      company_name: companyName,
      recommended_count: 0,
      coverable_assignments: 0,
      candidate_vehicle_count: 0,
      vehicle_codes: [],
    };
    current.recommended_count += 1;
    current.coverable_assignments += 1;
    if (best.vehicle_code && !current.vehicle_codes.includes(best.vehicle_code)) {
      current.vehicle_codes.push(best.vehicle_code);
    }
    current.candidate_vehicle_count = Math.max(current.candidate_vehicle_count, current.vehicle_codes.length);
    counters.set(companyId, current);
  });
  return {
    total_pending_buses: Array.isArray(items) ? items.length : 0,
    recommended_companies: Array.from(counters.values()).sort((a, b) => b.recommended_count - a.recommended_count),
    companies_with_options: counters.size,
    uncovered_buses: Math.max(0, (Array.isArray(items) ? items.length : 0) - counters.size),
  };
};

const REJECTION_REASON_LABELS = {
  vehicle_excluded: 'Vehiculo descartado manualmente',
  different_vehicle_selected: 'No coincide con el vehiculo exacto elegido',
  company_out_of_scope: 'Fuera de la empresa preferida',
  capacity_insufficient: 'Plazas insuficientes',
  reserved_in_published_workspace: 'Reservado en otra publicacion',
  already_used_in_reconciliation: 'Ya usado en esta reconciliacion',
  vehicle_missing_identifier: 'Vehiculo sin identificador util',
};

export const formatCandidateRejectionReason = (reason) => (
  REJECTION_REASON_LABELS[String(reason || '').trim()] || String(reason || 'Motivo no clasificado')
);

export const buildFleetReconciliationModalData = ({
  data,
  activeDay,
  busId = null,
  dayLabels = {},
  intent = 'reconcile',
  pendingPublishPayload = null,
  publishSuccessTitle = '',
  publishSuccessMessage = '',
}) => {
  const dayItems = Array.isArray(data?.reconciliation_day?.items)
    ? data.reconciliation_day.items
    : (Array.isArray(data?.pending_assignments) ? data.pending_assignments : []);
  const filteredItems = busId
    ? dayItems.filter((item) => String(item?.bus_id || '') === String(busId))
    : dayItems;
  const sourceCompanyMix = data?.reconciliation_day?.company_mix || data?.reconciliation?.company_mix || null;
  const modalCompanyMix = busId ? buildCompanyMixFallback(filteredItems) : sourceCompanyMix;
  const daySummary = data?.reconciliation_day || {};

  return {
    ...createFleetReconciliationModalState(),
    open: true,
    items: filteredItems,
    companyMix: modalCompanyMix,
    requiredBusCount: Number(daySummary?.required_bus_count || data?.required_bus_count || 0),
    realBoundCount: Number(daySummary?.real_bound_count || data?.real_bound_count || 0),
    pendingRealReconciliationCount: Number(
      daySummary?.pending_real_reconciliation_count || data?.pending_real_reconciliation_count || filteredItems.length || 0
    ),
    availableRealVehicleCount: Number(
      daySummary?.available_real_vehicle_count || data?.available_real_vehicle_count || data?.scope_vehicle_count || 0
    ),
    companiesAvailable: Number(daySummary?.companies_available || sourceCompanyMix?.companies_with_options || 0),
    estimatedVirtualRemaining: Number(daySummary?.estimated_virtual_remaining || sourceCompanyMix?.uncovered_buses || 0),
    reconciliationSnapshot: data?.reconciliation_snapshot?.days?.[activeDay] || null,
    dayLabel: dayLabels[activeDay] || activeDay,
    scopeLabel: data?.scope_label || '',
    scopeVehicleCount: Number(data?.scope_vehicle_count || 0),
    scopeMode: String(data?.scope_mode || 'company'),
    busId: busId || null,
    operationalSummary: data?.operational_summary || daySummary?.operational_summary || null,
    candidateRejectionReasons: data?.candidate_rejection_reasons || daySummary?.candidate_rejection_reasons || null,
    intent,
    pendingPublishPayload,
    previewDay: activeDay,
    publishSuccessTitle,
    publishSuccessMessage,
  };
};
