import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

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

function PublicationStatusCard({ title, value, tone = 'neutral', helper = '' }) {
  const toneClass = {
    success: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100',
    warning: 'border-amber-500/25 bg-amber-500/10 text-amber-100',
    danger: 'border-rose-500/25 bg-rose-500/10 text-rose-100',
    neutral: 'border-white/10 bg-white/[0.03] text-slate-100',
  }[tone] || 'border-white/10 bg-white/[0.03] text-slate-100';

  return (
    <div className={`rounded-xl border px-3 py-2.5 ${toneClass}`}>
      <p className="text-[10px] uppercase tracking-[0.1em] opacity-80">{title}</p>
      <p className="mt-1 text-[16px] font-semibold data-mono">{value}</p>
      {helper ? <p className="mt-1 text-[10px] opacity-80">{helper}</p> : null}
    </div>
  );
}

export function PlanningDetailPanel({
  workspace = null,
  activeDay = 'L',
  stats = null,
  scheduleByDay = null,
  optimizationOptions = null,
  workspaceCompanies = [],
  onOpenReconciliation,
  onOpenRules,
  onClose,
}) {
  if (!workspace) return null;

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

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em] text-cyan-300/90 data-mono">Detalle operativo</p>
          <p className="mt-1 text-[16px] font-semibold text-white">{workspace.name || 'Optimizacion activa'}</p>
          <p className="mt-1 text-[11px] text-slate-400">
            {scopeLabel} · {DAY_LABELS[activeDay] || activeDay} · {readiness.label}
          </p>
        </div>
        {typeof onClose === 'function' ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/10 px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-200 hover:bg-white/5"
          >
            Cerrar
          </button>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
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

        <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3">
          <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Estado principal</p>
          <p className="mt-1 text-[14px] font-semibold text-white">{nextActionLabel}</p>
          <p className="mt-1 text-[11px] text-slate-400">
            {blockingText || `Pendientes: ${pendingLabel}.`}
          </p>
        </div>

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
            La empresa principal actual es <span className="font-semibold">{currentCompany?.name}</span> y tiene 0 buses activos. Cambia la empresa principal o usa modo UTE para que la flota real aparezca en la asignacion.
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <PublicationStatusCard title="Buses hoy" value={stats?.buses ?? 0} helper={`${stats?.routes ?? 0} rutas en el dia activo`} />
          <PublicationStatusCard title="Flota real hoy" value={fleetReal} tone="success" helper="Vehiculos reales asignados al dia." />
          <PublicationStatusCard title="Provisionales hoy" value={fleetVirtual} tone={fleetVirtual > 0 ? 'warning' : 'success'} helper={weekFleetVirtual > fleetVirtual ? `Semana completa: ${weekFleetVirtual}` : 'Sin pendientes relevantes.'} />
          <PublicationStatusCard title="Conflictos reales" value={workspace?.conflict_count ?? 0} tone={hasConflict ? 'danger' : 'success'} helper={hasConflict ? 'Hay conflictos reales detectados.' : 'No hay bloqueos detectados.'} />
          <PublicationStatusCard title="Buses cortos" value={overCapacity} tone={overCapacity > 0 ? 'danger' : 'success'} helper={overCapacity > 0 ? 'Deficit de plazas en vehiculo real.' : 'No hay deficit detectado.'} />
          <PublicationStatusCard title="Buses justos" value={tightCapacity} tone={tightCapacity > 0 ? 'warning' : 'success'} helper={tightCapacity > 0 ? 'Conviene revisar antes de publicar.' : 'Hay margen razonable.'} />
          <PublicationStatusCard title="Sin vehiculo/cap." value={missingVehicle} tone={missingVehicle > 0 ? 'warning' : 'success'} helper={missingVehicle > 0 ? 'Falta reconciliar o completar capacidad.' : 'Todo visible.'} />
          <PublicationStatusCard title="Solver activo" value={selectedSolverLabel} tone={selectedSolver === 'cp_sat' ? 'warning' : 'neutral'} helper={requestedSolver === selectedSolver ? `Pedido: ${requestedSolverLabel}` : `Pedido: ${requestedSolverLabel} -> activo: ${selectedSolverLabel}`} />
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

        <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3">
          <p className="text-[10px] uppercase tracking-[0.1em] text-slate-500">Diagnostico motor</p>
          <div className="mt-2 grid grid-cols-1 gap-3 xl:grid-cols-2">
            <PublicationStatusCard title="Decision motor" value={solverReason || 'Sin detalle'} helper={solverReasonDetail} />
            <PublicationStatusCard title="Pendiente actual" value={pendingLabel} helper={blockingText || 'Sin bloqueos adicionales.'} />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onOpenRules}
            className="rounded-md border border-cyan-500/35 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-cyan-100 hover:bg-cyan-500/10"
          >
            Reglas
          </button>
          {fleetVirtual > 0 ? (
            <button
              type="button"
              onClick={onOpenReconciliation}
              className="rounded-md border border-amber-500/35 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-100 hover:bg-amber-500/10"
            >
              Reconciliar flota
            </button>
          ) : null}
        </div>
      </div>
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
  studioTab = 'map',
  inspectorOpen = true,
  detailOpen = false,
  onToggleInspector,
  onToggleDetail,
}) {
  if (!workspace) return null;

  const readiness = getWorkspaceReadinessConfig(workspace.readiness_state);
  const nextActionLabel = getNextActionLabel(workspace.next_recommended_action);
  const activeDaySchedule = Array.isArray(scheduleByDay?.[activeDay]?.schedule)
    ? scheduleByDay[activeDay].schedule
    : [];
  const fleetVirtual = activeDaySchedule.filter((bus) => String(bus?.fleet_assignment_type || '').toLowerCase() !== 'real').length;
  const hasConflict = Number(workspace?.conflict_count || 0) > 0;
  const stageToneClass = hasConflict
    ? 'border-rose-500/25 bg-rose-500/10 text-rose-100'
    : fleetVirtual > 0
      ? 'border-amber-500/25 bg-amber-500/10 text-amber-100'
      : 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100';
  const modeLabel = {
    map: 'Mapa',
    mixed: 'Mixto',
    workspace: 'Timeline',
  }[studioTab] || 'Mapa';

  return (
    <div className="rounded-[16px] border border-[#2a4057] bg-[#0a1420]/92 px-3 py-2 shadow-[0_14px_34px_rgba(2,6,23,0.22)]">
      <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-[18px] font-semibold text-white xl:text-[19px]" style={{ fontFamily: 'Sora, IBM Plex Sans, Segoe UI, sans-serif' }}>
              {workspace.name || 'Optimizacion activa'}
            </p>
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] ${readiness.chipClass}`}>
              {readiness.label}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-300">
              {DAY_LABELS[activeDay] || activeDay}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-300">
              {modeLabel}
            </span>
            <span className={`rounded-full border px-2 py-0.5 text-[10px] ${stageToneClass}`}>
              {nextActionLabel}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
            <span>{getScopeLabel(workspace.scope_summary)}</span>
            <span className="text-slate-600">•</span>
            <span>{stats?.buses ?? 0} buses</span>
            <span className="text-slate-600">•</span>
            <span>{stats?.routes ?? 0} rutas</span>
            {fleetVirtual > 0 ? (
              <>
                <span className="text-slate-600">•</span>
                <span className="text-amber-200">{fleetVirtual} provisionales</span>
              </>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 xl:justify-end">
          {fleetVirtual > 0 ? (
            <button
              type="button"
              onClick={onOpenReconciliation}
              className="rounded-md border border-amber-500/35 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-amber-100 hover:bg-amber-500/10"
            >
              Reconciliar
            </button>
          ) : null}
          <button
            type="button"
            onClick={onOpenRules}
            className="rounded-md border border-cyan-500/35 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-cyan-100 hover:bg-cyan-500/10"
          >
            Reglas
          </button>
          <button
            type="button"
            onClick={onToggleInspector}
            className={`rounded-md border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] ${
              inspectorOpen
                ? 'border-white/10 bg-white/[0.05] text-slate-100'
                : 'border-white/10 bg-white/[0.02] text-slate-300'
            }`}
          >
            {inspectorOpen ? <ChevronRight className="mr-1 inline h-3.5 w-3.5" /> : <ChevronLeft className="mr-1 inline h-3.5 w-3.5" />}
            Inspector
          </button>
          <button
            type="button"
            onClick={onToggleDetail}
            className={`rounded-md border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] ${
              detailOpen
                ? 'border-cyan-500/35 bg-cyan-500/10 text-cyan-100'
                : 'border-white/10 text-slate-100 hover:bg-white/5'
            }`}
          >
            Detalle
          </button>
          <button
            type="button"
            onClick={onPublishWeek}
            disabled={publishDisabled}
            className="rounded-md bg-cyan-400 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#03131f] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Publicar
          </button>
        </div>
      </div>
    </div>
  );
}
