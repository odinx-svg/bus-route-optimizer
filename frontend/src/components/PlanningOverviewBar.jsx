import React, { useEffect, useState } from 'react';

import { DAY_LABELS } from '../utils/days';
import {
  getObjectiveDisplayLabel,
  getSolverDisplayLabel,
  getSolverReasonDetail,
  getSolverReasonLabel,
} from '../utils/optimizerDiagnostics';
import {
  getBlockingReasonText,
  getNextActionLabel,
  getPlanningStageLabels,
  getScopeLabel,
  getWorkspacePendingLabel,
  getWorkspaceReadinessConfig,
} from '../utils/workspaceStatus';

function PublicationStatusCard({ title, value, tone = 'neutral', helper = '', compact = false }) {
  const toneClass = {
    success: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100',
    warning: 'border-amber-500/25 bg-amber-500/10 text-amber-100',
    danger: 'border-rose-500/25 bg-rose-500/10 text-rose-100',
    neutral: 'border-white/10 bg-white/[0.03] text-slate-100',
  }[tone] || 'border-white/10 bg-white/[0.03] text-slate-100';

  return (
    <div className={`rounded-xl border ${compact ? 'px-3 py-2.5' : 'px-3 py-3'} ${toneClass}`}>
      <p className="text-[10px] uppercase tracking-[0.1em] opacity-80">{title}</p>
      <p className={`mt-1 font-semibold data-mono ${compact ? 'text-[16px]' : 'text-[18px]'}`}>{value}</p>
      {helper ? <p className={`mt-1 opacity-80 ${compact ? 'text-[10px]' : 'text-[11px]'}`}>{helper}</p> : null}
    </div>
  );
}

export default function PlanningOverviewBar({
  workspace = null,
  activeDay = 'L',
  stats = null,
  scheduleByDay = null,
  onOpenReconciliation,
  onOpenRules,
  onPublishWeek,
  publishDisabled = false,
  optimizationOptions = null,
  workspaceCompanies = [],
}) {
  if (!workspace) return null;

  const [isExpanded, setIsExpanded] = useState(false);
  const readiness = getWorkspaceReadinessConfig(workspace.readiness_state);
  const pendingLabel = getWorkspacePendingLabel(workspace);
  const nextActionLabel = getNextActionLabel(workspace.next_recommended_action);
  const blockingText = getBlockingReasonText(workspace.blocking_reason);
  const stageItems = getPlanningStageLabels(workspace);
  const activeDaySchedule = Array.isArray(scheduleByDay?.[activeDay]?.schedule)
    ? scheduleByDay[activeDay].schedule
    : [];
  const activeDayMetadata = scheduleByDay?.[activeDay]?.metadata || {};
  const activeDayOptimizerDiagnostics = activeDayMetadata?.optimizer_diagnostics || {};
  const selectedSolver = String(
    activeDayOptimizerDiagnostics?.selected_solver
    || activeDayOptimizerDiagnostics?.solver_name
    || optimizationOptions?.preferred_solver
    || 'auto'
  );
  const requestedSolver = String(
    activeDayMetadata?.requested_solver
    || optimizationOptions?.preferred_solver
    || 'auto'
  );
  const solverReason = getSolverReasonLabel(activeDayOptimizerDiagnostics);
  const solverReasonDetail = getSolverReasonDetail(activeDayOptimizerDiagnostics);
  const selectedSolverLabel = getSolverDisplayLabel(selectedSolver);
  const requestedSolverLabel = getSolverDisplayLabel(requestedSolver);
  const objectiveLabel = getObjectiveDisplayLabel(optimizationOptions?.objective);
  const fleetReal = activeDaySchedule.filter((bus) => String(bus?.fleet_assignment_type || '').toLowerCase() === 'real').length;
  const fleetVirtual = activeDaySchedule.filter((bus) => String(bus?.fleet_assignment_type || '').toLowerCase() !== 'real').length;
  const weekFleetVirtual = Number(workspace?.pending_virtual_count ?? workspace?.summary_metrics?.fleet_virtual_created ?? 0);
  const scopeLabel = getScopeLabel(workspace.scope_summary);
  const hasConflict = Number(workspace?.conflict_count || 0) > 0;
  const capacitySummary = workspace?.capacity_summary || {};
  const overCapacity = Number(capacitySummary?.over_capacity || 0);
  const tightCapacity = Number(capacitySummary?.tight || 0);
  const missingVehicle = Number(capacitySummary?.missing_vehicle || 0);
  const blockingIssues = Array.isArray(workspace?.blocking_issues) ? workspace.blocking_issues : [];
  const operationalWarnings = Array.isArray(workspace?.operational_warnings) ? workspace.operational_warnings : [];
  const routeRulesCount = Array.isArray(optimizationOptions?.route_load_constraints)
    ? optimizationOptions.route_load_constraints.filter((row) => row?.enabled !== false).length
    : 0;
  const currentCompany = Array.isArray(workspaceCompanies)
    ? workspaceCompanies.find((company) => String(company.id) === String(workspace?.company_id || ''))
    : null;
  const companyScopeWithoutFleet = (
    String(optimizationOptions?.fleet_scope_mode || 'company') !== 'ute'
    && currentCompany
    && Number(currentCompany.active_vehicle_count || 0) === 0
  );

  useEffect(() => {
    if (hasConflict || fleetVirtual > 0 || Boolean(blockingText) || companyScopeWithoutFleet) {
      setIsExpanded(true);
    }
  }, [blockingText, companyScopeWithoutFleet, fleetVirtual, hasConflict]);

  const nextActionTone = hasConflict
    ? 'danger'
    : fleetVirtual > 0
      ? 'warning'
      : readiness.tone === 'ready' || workspace?.status === 'active'
        ? 'success'
        : 'info';

  const nextActionClass = {
    danger: 'border-rose-500/25 bg-rose-500/10 text-rose-100',
    warning: 'border-amber-500/25 bg-amber-500/10 text-amber-100',
    success: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100',
    info: 'border-cyan-500/25 bg-cyan-500/10 text-cyan-100',
  }[nextActionTone];

  return (
    <div className="mb-2 rounded-[18px] border border-[#304a62] bg-[#0d1623]/95 px-3 py-2.5">
      <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[10px] uppercase tracking-[0.16em] text-cyan-300/90 data-mono">Planificacion</p>
            <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] ${readiness.chipClass}`}>
              {readiness.label}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] text-slate-200">
              {scopeLabel}
            </span>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px]">
            <span className="text-[22px] font-semibold leading-none text-white" style={{ fontFamily: 'Sora, IBM Plex Sans, Segoe UI, sans-serif' }}>
              {workspace.name || 'Optimizacion activa'}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-slate-200">
              {DAY_LABELS[activeDay] || activeDay}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-slate-200">
              {stats?.buses ?? 0} buses
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-slate-200">
              {stats?.routes ?? 0} rutas
            </span>
            <span className={`rounded-full border px-2.5 py-1 ${fleetVirtual > 0 ? 'border-amber-500/25 bg-amber-500/10 text-amber-100' : 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100'}`}>
              {fleetVirtual} provisionales hoy
            </span>
            {hasConflict ? (
              <span className="rounded-full border border-rose-500/25 bg-rose-500/10 px-2.5 py-1 text-rose-100">
                {workspace?.conflict_count ?? 0} conflictos
              </span>
            ) : null}
            {overCapacity > 0 ? (
              <span className="rounded-full border border-rose-500/25 bg-rose-500/10 px-2.5 py-1 text-rose-100">
                {overCapacity} cortos de plazas
              </span>
            ) : null}
            {tightCapacity > 0 ? (
              <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-amber-100">
                {tightCapacity} justos
              </span>
            ) : null}
            <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 text-cyan-100">
              Siguiente: {nextActionLabel}
            </span>
          </div>
          <p className="mt-1 truncate text-[11px] text-slate-400">
            Pendiente principal: {pendingLabel.toLowerCase()}.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 xl:justify-end">
          {fleetVirtual > 0 ? (
            <button
              type="button"
              onClick={onOpenReconciliation}
              className="rounded-md border border-amber-500/35 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-100 hover:bg-amber-500/10"
            >
              Reconciliar flota
            </button>
          ) : null}
          <button
            type="button"
            onClick={onOpenRules}
            className="rounded-md border border-cyan-500/35 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-cyan-100 hover:bg-cyan-500/10"
          >
            Abrir reglas
          </button>
          <button
            type="button"
            onClick={onPublishWeek}
            disabled={publishDisabled}
            className="rounded-md bg-cyan-400 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#03131f] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Publicar semana
          </button>
          <button
            type="button"
            onClick={() => setIsExpanded((prev) => !prev)}
            className="rounded-md border border-white/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-100 hover:bg-white/5"
          >
            {isExpanded ? 'Ocultar' : 'Detalle'}
          </button>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
        <div className={`rounded-xl border px-3 py-2.5 ${nextActionClass}`}>
          <p className="text-[10px] uppercase tracking-[0.12em] opacity-80">Siguiente accion recomendada</p>
          <p className="mt-1 text-[13px] font-semibold">{nextActionLabel}</p>
          <p className="mt-1 text-[11px] opacity-90">
            {blockingText
              || (fleetVirtual > 0
                ? 'Todavia quedan buses provisionales. Reconciliar ahora evita problemas al publicar.'
                : companyScopeWithoutFleet
                  ? 'La empresa principal no tiene buses activos. Ajusta el ambito de flota antes de seguir.'
                  : 'El workspace esta en condiciones de seguir avanzando.')}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {stageItems.map((item) => (
            <div
              key={item.key}
              className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] ${
                item.done
                  ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100'
                  : item.active
                    ? 'border-cyan-500/25 bg-cyan-500/10 text-cyan-100'
                    : 'border-white/10 bg-white/[0.03] text-slate-400'
              }`}
            >
              {item.label}
            </div>
          ))}
        </div>
      </div>

      {isExpanded && (
        <div className="mt-3 space-y-3 rounded-xl border border-white/10 bg-[#09111b] p-3">
          {blockingText ? (
            <p className="text-[12px] text-amber-100">{blockingText}</p>
          ) : null}
          {blockingIssues.length > 0 && (
            <div className="space-y-2">
              {blockingIssues.map((issue, index) => (
                <div key={`${issue?.type || 'blocking'}-${index}`} className="rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-[12px] text-rose-100">
                  {issue?.message || 'Hay un bloqueo operativo pendiente de resolver.'}
                </div>
              ))}
            </div>
          )}
          {operationalWarnings.length > 0 && (
            <div className="space-y-2">
              {operationalWarnings.map((issue, index) => (
                <div key={`${issue?.type || 'warning'}-${index}`} className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-100">
                  {issue?.message || 'Hay una advertencia operativa que conviene revisar.'}
                </div>
              ))}
            </div>
          )}
          {companyScopeWithoutFleet ? (
            <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-100">
              La empresa principal actual del workspace es <span className="font-semibold">{currentCompany?.name}</span> y tiene 0 buses activos. Cambia la empresa principal o usa modo UTE para que la flota real aparezca en la asignacion.
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onOpenRules}
              className="rounded-md border border-cyan-500/35 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-cyan-100 hover:bg-cyan-500/10"
            >
              Reglas de optimizacion
            </button>
            {fleetVirtual > 0 && (
              <button
                type="button"
                onClick={onOpenReconciliation}
                className="rounded-md border border-amber-500/35 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-100 hover:bg-amber-500/10"
              >
                Reconciliar flota
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 xl:grid-cols-4">
            <PublicationStatusCard title="Flota real hoy" value={fleetReal} tone="success" helper="Buses reales del dia activo." compact />
            <PublicationStatusCard title="Estado de publicacion" value={readiness.label} helper="Resumen del estado operativo actual." compact />
            <PublicationStatusCard title="Provisionales hoy" value={fleetVirtual} tone={fleetVirtual > 0 ? 'warning' : 'success'} helper={weekFleetVirtual > fleetVirtual ? `Semana completa: ${weekFleetVirtual}` : (fleetVirtual > 0 ? 'Requieren asignacion real antes de publicar.' : 'No quedan pendientes.')} compact />
            <PublicationStatusCard title="Conflictos reales" value={workspace?.conflict_count ?? 0} tone={hasConflict ? 'danger' : 'success'} helper={hasConflict ? 'Hay una colision real con otra publicacion.' : 'No hay bloqueos detectados.'} compact />
          </div>

          <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
            <PublicationStatusCard title="Buses cortos" value={overCapacity} tone={overCapacity > 0 ? 'danger' : 'success'} helper={overCapacity > 0 ? 'Vehiculo real por debajo de la demanda.' : 'No hay deficits de plazas detectados.'} compact />
            <PublicationStatusCard title="Buses justos" value={tightCapacity} tone={tightCapacity > 0 ? 'warning' : 'success'} helper={tightCapacity > 0 ? 'Conviene revisar antes de publicar.' : 'Hay margen razonable de plazas.'} compact />
            <PublicationStatusCard title="Sin vehiculo/cap." value={missingVehicle} tone={missingVehicle > 0 ? 'warning' : 'success'} helper={missingVehicle > 0 ? 'Falta reconciliar o completar capacidad.' : 'Todas las unidades tienen capacidad visible.'} compact />
          </div>

          <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
            <PublicationStatusCard
              title="Solver activo"
              value={selectedSolverLabel}
              tone={selectedSolver === 'cp_sat' ? 'warning' : 'neutral'}
              helper={requestedSolver === selectedSolver ? `Pedido: ${requestedSolverLabel}` : `Pedido: ${requestedSolverLabel} -> activo: ${selectedSolverLabel}`}
              compact
            />
            <PublicationStatusCard
              title="Warm start"
              value={activeDayOptimizerDiagnostics?.warm_start_used ? 'Si' : (activeDayOptimizerDiagnostics?.warm_start_available ? 'Disponible' : 'No')}
              helper="Semilla greedy usada antes del solver."
              compact
            />
            <PublicationStatusCard
              title="Decision motor"
              value={solverReason || 'Sin detalle'}
              helper={solverReasonDetail}
              compact
            />
          </div>

          <div className="rounded-xl border border-white/10 bg-[#0d1623]/70 p-3">
            <p className="text-[10px] uppercase tracking-[0.1em] text-slate-500">Reglas activas</p>
            <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Ambito: {optimizationOptions?.fleet_scope_mode === 'ute' ? 'UTE' : 'Empresa'}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Objetivo: {objectiveLabel}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Solver pedido: {requestedSolverLabel}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Solver activo: {selectedSolverLabel}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Balanceo: {optimizationOptions?.balance_load === false ? 'Flexible' : 'Activo'}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Diferencia max: {optimizationOptions?.load_balance_hard_spread_limit ?? 2}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Ventanas: {routeRulesCount}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Publicacion: {optimizationOptions?.virtual_bus_publish_policy === 'block' ? 'Bloquear provisionales' : 'Permitir con aviso'}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
            <span className="rounded-md border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-cyan-100">Ruta</span>
            <span className="rounded-md border border-slate-500/20 bg-slate-500/10 px-2 py-1 text-slate-200">Posicionamiento</span>
            <span className="rounded-md border border-rose-500/20 bg-rose-500/10 px-2 py-1 text-rose-100">Conflicto</span>
            <span className="rounded-md border border-amber-500/20 bg-amber-500/10 px-2 py-1 text-amber-100">Bus provisional</span>
            <span className="rounded-md border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-cyan-100">Bus publicado</span>
          </div>
        </div>
      )}
    </div>
  );
}
