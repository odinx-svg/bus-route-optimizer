import React, { useEffect, useMemo, useState } from 'react';

import {
  buildCompanyMixFallback,
  formatCandidateRejectionReason,
  formatMinuteValue,
} from '../utils/fleetReconciliation';

function MetricCard({ label, value, tone = 'default' }) {
  const toneClass = {
    default: 'text-white',
    success: 'text-emerald-200',
    warning: 'text-amber-200',
    info: 'text-cyan-200',
  }[tone] || 'text-white';

  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
      <p className="text-[10px] uppercase tracking-[0.08em] text-slate-400">{label}</p>
      <p className={`mt-1 text-[26px] font-semibold ${toneClass}`}>{value}</p>
    </div>
  );
}

function SummaryChip({ label, value, tone = 'default' }) {
  const toneClass = {
    default: 'border-white/8 bg-white/[0.03] text-slate-300',
    success: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-100',
    warning: 'border-amber-500/20 bg-amber-500/10 text-amber-100',
    danger: 'border-rose-500/20 bg-rose-500/10 text-rose-100',
  }[tone] || 'border-white/8 bg-white/[0.03] text-slate-300';

  return (
    <div className={`rounded-lg border px-3 py-2 text-[11px] ${toneClass}`}>
      {label}: <span className="font-semibold">{value}</span>
    </div>
  );
}

export default function FleetReconciliationModal({
  open = false,
  items = [],
  companyMix = null,
  requiredBusCount = 0,
  realBoundCount = 0,
  pendingRealReconciliationCount = 0,
  availableRealVehicleCount = 0,
  companiesAvailable = 0,
  estimatedVirtualRemaining = 0,
  reconciliationSnapshot = null,
  dayLabel = '',
  scopeLabel = '',
  scopeVehicleCount = 0,
  scopeMode = 'company',
  busId = null,
  operationalSummary = null,
  candidateRejectionReasons = null,
  applying = false,
  onApply = null,
  onClose,
}) {
  const effectiveCompanyMix = useMemo(() => (
    companyMix && typeof companyMix === 'object'
      ? companyMix
      : buildCompanyMixFallback(items)
  ), [companyMix, items]);
  const recommendedCompanies = useMemo(() => (
    Array.isArray(effectiveCompanyMix?.recommended_companies)
      ? effectiveCompanyMix.recommended_companies
      : []
  ), [effectiveCompanyMix]);
  const totalPendingBuses = Number(
    pendingRealReconciliationCount
    || effectiveCompanyMix?.total_pending_buses
    || items.length
    || 0
  );
  const uncoveredBuses = Number(
    estimatedVirtualRemaining
    || effectiveCompanyMix?.uncovered_buses
    || 0
  );
  const modalTitle = busId
    ? `Asignacion recomendada para ${busId}`
    : 'Asignacion recomendada de buses reales';
  const rejectionEntries = useMemo(() => (
    Object.entries(candidateRejectionReasons && typeof candidateRejectionReasons === 'object' ? candidateRejectionReasons : {})
      .map(([reason, count]) => ({ reason, count: Number(count || 0) }))
      .filter((row) => row.count > 0)
      .sort((a, b) => b.count - a.count)
  ), [candidateRejectionReasons]);
  const [allocationByCompany, setAllocationByCompany] = useState({});
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [preferredCompanyByBus, setPreferredCompanyByBus] = useState({});
  const [selectedVehicleByBus, setSelectedVehicleByBus] = useState({});
  const [excludedVehicleIdsByBus, setExcludedVehicleIdsByBus] = useState({});

  useEffect(() => {
    if (!open) return;
    const nextState = {};
    const snapshotAllocations = Array.isArray(reconciliationSnapshot?.company_allocations)
      ? reconciliationSnapshot.company_allocations
      : [];
    snapshotAllocations.forEach((company) => {
      const key = String(company?.company_id || 'unassigned');
      nextState[key] = Number(company?.count || 0);
    });
    recommendedCompanies.forEach((company) => {
      const key = String(company?.company_id || 'unassigned');
      if (typeof nextState[key] === 'undefined') {
        nextState[key] = Number(company?.recommended_count || 0);
      }
    });
    setAllocationByCompany(nextState);
    setPreferredCompanyByBus({});
    setSelectedVehicleByBus({});
    setExcludedVehicleIdsByBus({});
    setDetailsOpen(Boolean(busId));
  }, [busId, open, recommendedCompanies, reconciliationSnapshot]);

  if (!open) return null;

  const totalAssigned = Object.values(allocationByCompany).reduce((sum, value) => sum + Math.max(0, Number(value) || 0), 0);
  const remainingToDistribute = Math.max(0, totalPendingBuses - totalAssigned);
  const primaryRecommendation = recommendedCompanies[0] || null;

  const handleAllocationChange = (companyId, nextValue) => {
    const normalizedKey = String(companyId || 'unassigned');
    const parsed = Number.parseInt(nextValue, 10);
    setAllocationByCompany((prev) => ({
      ...prev,
      [normalizedKey]: Number.isFinite(parsed) ? Math.max(0, parsed) : 0,
    }));
  };

  const handlePreferredCompanyChange = (rowKey, companyId) => {
    setPreferredCompanyByBus((prev) => ({
      ...prev,
      [rowKey]: companyId || '',
    }));
    setSelectedVehicleByBus((prev) => ({
      ...prev,
      [rowKey]: '',
    }));
  };

  const handleVehicleSelectionChange = (rowKey, vehicleId, candidates = []) => {
    const normalizedVehicleId = String(vehicleId || '').trim();
    setSelectedVehicleByBus((prev) => ({
      ...prev,
      [rowKey]: normalizedVehicleId,
    }));
    if (!normalizedVehicleId) return;
    const selectedCandidate = (Array.isArray(candidates) ? candidates : []).find(
      (candidate) => String(candidate?.vehicle_id || '') === normalizedVehicleId
    );
    if (selectedCandidate?.company_id) {
      setPreferredCompanyByBus((prev) => ({
        ...prev,
        [rowKey]: String(selectedCandidate.company_id),
      }));
    }
  };

  const handleToggleExcludedVehicle = (rowKey, vehicleId) => {
    const normalizedVehicleId = String(vehicleId || '').trim();
    if (!normalizedVehicleId) return;
    setExcludedVehicleIdsByBus((prev) => {
      const current = Array.isArray(prev[rowKey]) ? prev[rowKey] : [];
      const exists = current.includes(normalizedVehicleId);
      const next = exists
        ? current.filter((value) => value !== normalizedVehicleId)
        : [...current, normalizedVehicleId];
      return {
        ...prev,
        [rowKey]: next,
      };
    });
    setSelectedVehicleByBus((prev) => (
      String(prev[rowKey] || '') === normalizedVehicleId
        ? { ...prev, [rowKey]: '' }
        : prev
    ));
  };

  const handleApply = () => {
    if (typeof onApply !== 'function') return;
    const payload = recommendedCompanies.map((company) => ({
      company_id: company?.company_id || null,
      count: Math.max(0, Number(allocationByCompany[String(company?.company_id || 'unassigned')] || 0)),
    }));
    const busSelections = (Array.isArray(items) ? items : []).map((row) => {
      const rowKey = `${row?.day || ''}::${row?.bus_id || ''}`;
      const companyId = String(preferredCompanyByBus[rowKey] || '').trim();
      const vehicleId = String(selectedVehicleByBus[rowKey] || '').trim();
      const excludedVehicleIds = Array.isArray(excludedVehicleIdsByBus[rowKey])
        ? excludedVehicleIdsByBus[rowKey].filter(Boolean)
        : [];
      if (!companyId && !vehicleId && excludedVehicleIds.length === 0) return null;
      return {
        day: row?.day || null,
        bus_id: row?.bus_id || '',
        company_id: companyId || null,
        vehicle_id: vehicleId || null,
        excluded_vehicle_ids: excludedVehicleIds,
      };
    }).filter(Boolean);
    onApply(payload, busSelections);
  };

  return (
    <div className="fixed inset-0 z-[1265] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/85 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative flex max-h-[92vh] w-full max-w-5xl flex-col rounded-xl border border-amber-500/35 bg-[#0b141f] p-4 shadow-2xl">
        <h3 className="text-[16px] font-semibold text-white">{modalTitle}</h3>
        <p className="mt-2 text-[12px] text-[#8ba3bd]">
          {busId
            ? 'Este bus provisional necesita una propuesta de empresa y un candidato real para cerrar la operacion.'
            : `La operacion del ${dayLabel ? dayLabel.toLowerCase() : 'dia'} usa ${Number(requiredBusCount || 0)} buses. Aqui decides cuantos cubres con flota real y de que empresa salen${scopeLabel ? ` dentro de ${scopeLabel}` : ''}.`}
        </p>
        {scopeMode === 'company' && Number(scopeVehicleCount || 0) === 0 && (
          <div className="mt-3 rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-100">
            Esta optimizacion esta en modo Empresa, pero la empresa principal actual no tiene buses activos dentro del ambito usado. Cambia la empresa principal del workspace o pasa a modo UTE.
          </div>
        )}
        <div className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
          <section className="rounded-xl border border-[#2a4057] bg-[#0d1724] p-4">
            <div className="grid gap-3 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.06] p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-cyan-200">Lectura rapida</p>
                <p className="mt-3 text-[22px] font-semibold text-white">
                  La operacion usa {Number(requiredBusCount || 0)} buses
                </p>
                <p className="mt-2 text-[13px] leading-6 text-slate-300">
                  {totalPendingBuses > 0
                    ? (primaryRecommendation
                      ? `Ya hay ${Number(realBoundCount || 0)} cubiertos con real. Te falta decidir ${totalPendingBuses} buses y la propuesta inicial empieza por ${primaryRecommendation.company_name || 'la empresa principal'}.`
                      : `Ya hay ${Number(realBoundCount || 0)} cubiertos con real. Te falta decidir ${totalPendingBuses} buses y no hay una empresa claramente dominante.`)
                    : 'No quedan pendientes de asignacion real. Puedes revisar el reparto o cerrar la reconciliacion.'}
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-2">
                <MetricCard label="Operacion del dia" value={Number(requiredBusCount || 0)} />
                <MetricCard label="Ya cubiertos con real" value={Number(realBoundCount || 0)} tone="success" />
                <MetricCard label="Pendientes de asignar" value={totalPendingBuses} />
                <MetricCard label="Flota disponible en alcance" value={Number(availableRealVehicleCount || scopeVehicleCount || 0)} tone="info" />
                <MetricCard label="Empresas disponibles" value={Number(companiesAvailable || effectiveCompanyMix?.companies_with_options || 0)} tone="info" />
                <MetricCard label="Provisionales si no completas" value={uncoveredBuses} tone="warning" />
              </div>
            </div>
            {operationalSummary && (
              <div className="mt-4 grid gap-2 md:grid-cols-4">
                <SummaryChip label="Requeridos" value={Number(operationalSummary.required_bus_count || requiredBusCount || 0)} />
                <SummaryChip label="Reales" value={Number(operationalSummary.real_bound_count || realBoundCount || 0)} tone="success" />
                <SummaryChip label="Pendientes" value={Number(operationalSummary.pending_real_reconciliation_count || totalPendingBuses || 0)} tone="warning" />
                <SummaryChip label="Asignaciones caducadas" value={Number(operationalSummary.stale_assignment_count || 0)} tone="danger" />
              </div>
            )}
            {rejectionEntries.length > 0 && (
              <div className="mt-4 rounded-xl border border-[#2a4057] bg-[#0a1320] p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8ba3bd]">Por que faltan candidatos</p>
                <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                  {rejectionEntries.map((entry) => (
                    <span key={entry.reason} className="rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-1 text-rose-100">
                      {formatCandidateRejectionReason(entry.reason)}: {entry.count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>

          <section className="rounded-xl border border-[#2a4057] bg-[#0d1724] p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8ba3bd]">Reparto por empresa</p>
                <p className="mt-1 text-[12px] text-slate-400">
                  Indica cuantos buses reales quieres sacar de cada empresa. El sistema intentara respetar este reparto en los pendientes.
                </p>
                <p className="mt-1 text-[11px] text-slate-500">
                  Operacion total: {Number(requiredBusCount || 0)}. Ya cubiertos: {Number(realBoundCount || 0)}. Te falta repartir: {totalPendingBuses}.
                </p>
              </div>
              <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[11px] text-slate-300">
                Total configurado: {totalAssigned}
              </div>
            </div>
            {totalPendingBuses > 0 && totalAssigned !== totalPendingBuses && (
              <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-100">
                {totalAssigned < totalPendingBuses
                  ? `Todavia faltan ${totalPendingBuses - totalAssigned} buses por repartir entre empresas.`
                  : `Hay ${totalAssigned - totalPendingBuses} buses de mas en el reparto. Ajusta los conteos si quieres un reparto exacto.`}
              </div>
            )}
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {recommendedCompanies.length > 0 ? recommendedCompanies.map((company) => (
                <div key={`${company.company_id || company.company_name}`} className="rounded-xl border border-[#2a4057] bg-[#0a1320] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[15px] font-semibold text-white">{company.company_name || 'Empresa sin identificar'}</p>
                      <p className="mt-1 text-[12px] text-slate-400">
                        Recomendacion inicial: {company.recommended_count || 0} bus{Number(company.recommended_count || 0) === 1 ? '' : 'es'}
                      </p>
                    </div>
                    <div className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold text-cyan-200">
                      {company.recommended_count || 0}
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-400">
                    <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
                      Cubre {company.coverable_assignments || 0} asignaciones
                    </div>
                    <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
                      {company.candidate_vehicle_count || 0} vehiculos candidatos
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between gap-3">
                    <label className="text-[12px] text-slate-300">Buses a tomar de esta empresa</label>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={allocationByCompany[String(company.company_id || 'unassigned')] ?? 0}
                      onChange={(event) => handleAllocationChange(company.company_id, event.target.value)}
                      className="w-24 rounded-lg border border-[#2a4057] bg-[#08111b] px-3 py-2 text-right text-[13px] text-white outline-none focus:border-cyan-400"
                    />
                  </div>
                  {Array.isArray(company.vehicle_codes) && company.vehicle_codes.length > 0 && (
                    <p className="mt-3 text-[11px] text-slate-400">Ejemplos de apoyo: {company.vehicle_codes.join(', ')}</p>
                  )}
                </div>
              )) : (
                <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-[12px] text-amber-100 md:col-span-2">
                  No hay una recomendacion clara por empresa porque no se encontraron candidatos reales libres.
                </div>
              )}
            </div>
          </section>

          <section className="rounded-xl border border-[#2a4057] bg-[#0d1724] p-4">
            <button type="button" onClick={() => setDetailsOpen((prev) => !prev)} className="flex w-full items-center justify-between gap-3 text-left">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8ba3bd]">Detalle por bus</p>
                <p className="mt-1 text-[12px] text-slate-400">
                  {detailsOpen ? 'Oculta el detalle tecnico si ya tienes clara la decision.' : `Ver detalle de los ${items.length} buses pendientes de asignacion real.`}
                </p>
              </div>
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[11px] text-slate-300">
                {detailsOpen ? 'Ocultar' : 'Ver detalle'}
              </span>
            </button>
            {detailsOpen && (
              <div className="mt-4 grid gap-3">
                {items.map((row, idx) => {
                  const candidates = Array.isArray(row?.suggested_real_vehicles || row?.suggestions)
                    ? (row?.suggested_real_vehicles || row?.suggestions)
                    : [];
                  const rowKey = `${row?.day || ''}::${row?.bus_id || ''}`;
                  const preferredCompanyId = String(preferredCompanyByBus[rowKey] || '').trim();
                  const excludedVehicleIds = Array.isArray(excludedVehicleIdsByBus[rowKey]) ? excludedVehicleIdsByBus[rowKey] : [];
                  const companyOptions = Array.from(new Map(
                    candidates.map((candidate) => [
                      String(candidate?.company_id || 'unassigned'),
                      { company_id: candidate?.company_id || null, company_name: candidate?.company_name || 'Empresa sin identificar' },
                    ])
                  ).values());
                  const filteredCandidates = candidates.filter((candidate) => {
                    const candidateVehicleId = String(candidate?.vehicle_id || '');
                    if (excludedVehicleIds.includes(candidateVehicleId)) return false;
                    if (preferredCompanyId && String(candidate?.company_id || 'unassigned') !== preferredCompanyId) return false;
                    return true;
                  });
                  const bestCandidate = candidates[0] || null;
                  const rowRejectionEntries = Object.entries(
                    row?.candidate_rejection_reasons && typeof row.candidate_rejection_reasons === 'object'
                      ? row.candidate_rejection_reasons
                      : {}
                  )
                    .map(([reason, count]) => ({ reason, count: Number(count || 0) }))
                    .filter((entry) => entry.count > 0)
                    .sort((a, b) => b.count - a.count);
                  return (
                    <div key={`${row?.day || 'D'}-${row?.bus_id || 'BUS'}-${idx}`} className="rounded-xl border border-[#2a4057] bg-[#0a1320] p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-amber-100">{row?.bus_id || '-'}</span>
                        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] text-slate-300">{row?.day || '-'}</span>
                        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] text-slate-300">
                          {formatMinuteValue(row?.time_window?.start_minute ?? row?.start_minute)} - {formatMinuteValue(row?.time_window?.end_minute ?? row?.end_minute)}
                        </span>
                        <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 text-[10px] text-cyan-100">
                          {row?.required_capacity ?? row?.required_seats ?? '-'} plazas
                        </span>
                      </div>
                      <p className="mt-3 text-[12px] text-slate-300">
                        Empresa recomendada: <span className="font-semibold text-white">{bestCandidate?.company_name || 'Sin recomendacion'}</span>
                      </p>
                      <p className="mt-1 text-[11px] text-slate-400">
                        Candidatos: {candidates.length > 0
                          ? candidates.slice(0, 3).map((candidate) => `${candidate.vehicle_code || candidate.vehicle_id} / ${candidate.company_name || 'Empresa'} (${candidate.seats_max}P)`).join(', ')
                          : 'Sin sugerencias libres'}
                      </p>
                      {rowRejectionEntries.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2 text-[10px]">
                          {rowRejectionEntries.slice(0, 4).map((entry) => (
                            <span key={`${rowKey}-${entry.reason}`} className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-300">
                              {formatCandidateRejectionReason(entry.reason)}: {entry.count}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <label className="text-[11px] text-slate-300">
                          Empresa preferida para este provisional
                          <select
                            value={preferredCompanyId}
                            onChange={(event) => handlePreferredCompanyChange(rowKey, event.target.value)}
                            className="mt-1 w-full rounded-lg border border-[#2a4057] bg-[#08111b] px-3 py-2 text-[12px] text-white outline-none focus:border-cyan-400"
                          >
                            <option value="">Automatico segun recomendacion</option>
                            {companyOptions.map((company) => (
                              <option key={`${rowKey}-${company.company_id || 'unassigned'}`} value={company.company_id || 'unassigned'}>
                                {company.company_name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="text-[11px] text-slate-300">
                          Bus real exacto
                          <select
                            value={String(selectedVehicleByBus[rowKey] || '')}
                            onChange={(event) => handleVehicleSelectionChange(rowKey, event.target.value, filteredCandidates)}
                            className="mt-1 w-full rounded-lg border border-[#2a4057] bg-[#08111b] px-3 py-2 text-[12px] text-white outline-none focus:border-cyan-400"
                          >
                            <option value="">Que el sistema lo elija</option>
                            {filteredCandidates.map((candidate) => (
                              <option key={`${rowKey}-${candidate.vehicle_id}`} value={candidate.vehicle_id}>
                                {(candidate.vehicle_code || candidate.vehicle_id)} · {candidate.company_name || 'Empresa'} · {candidate.seats_max}P
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      {candidates.length > 0 && (
                        <div className="mt-4">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">Candidatos visibles</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {candidates.map((candidate) => {
                              const candidateVehicleId = String(candidate?.vehicle_id || '');
                              const blocked = excludedVehicleIds.includes(candidateVehicleId);
                              return (
                                <button
                                  key={`${rowKey}-${candidateVehicleId}-toggle`}
                                  type="button"
                                  onClick={() => handleToggleExcludedVehicle(rowKey, candidateVehicleId)}
                                  className={`rounded-full border px-2.5 py-1 text-[10px] transition ${
                                    blocked
                                      ? 'border-rose-500/30 bg-rose-500/10 text-rose-100'
                                      : 'border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]'
                                  }`}
                                >
                                  {blocked ? 'Descartado' : 'Disponible'}: {candidate.vehicle_code || candidate.vehicle_id}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
                {items.length === 0 && (
                  <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 text-[12px] text-slate-500">
                    No hay buses pendientes de asignacion real en este dia.
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/10 pt-3">
          <div className="text-[11px] text-slate-400">
            {totalPendingBuses > 0
              ? (remainingToDistribute > 0
                ? `Quedan ${remainingToDistribute} buses sin repartir. Si aplicas ahora, el sistema intentara completar el resto con la mejor opcion disponible.`
                : 'La propuesta queda lista para aplicarse en el workspace.')
              : 'No quedan pendientes. Puedes cerrar o revisar el detalle de lo ya asignado.'}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-[#2a4057] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9eb2c8] transition hover:bg-white/5"
              disabled={applying}
            >
              Cerrar
            </button>
            <button
              type="button"
              onClick={handleApply}
              disabled={applying || (items.length === 0 && totalPendingBuses > 0)}
              className="rounded-md border border-cyan-500/35 bg-cyan-500/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {applying ? 'Aplicando...' : (totalPendingBuses > 0 ? 'Aplicar propuesta' : 'Revisar reparto')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
