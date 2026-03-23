import React, { useMemo } from 'react';
import { ArrowUpRight, Bus, CalendarRange, FolderKanban, Gauge, LayoutGrid, Map } from 'lucide-react';

import tuttiSymbol from '../assets/tutti-symbol.svg';
import {
  getNextActionLabel,
  getScopeLabel,
  getWorkspacePendingLabel,
  getWorkspaceReadinessConfig,
  getWorkspaceStatusLabel,
} from '../utils/workspaceStatus';

const VIEW_META = {
  dashboard: {
    label: 'Panel',
    icon: Gauge,
    eyebrow: 'Centro operativo',
    title: 'Estado general de optimizaciones',
    description: 'Controla borradores, publicaciones, conflictos y el siguiente paso recomendado.',
  },
  fleet: {
    label: 'Flota',
    icon: Bus,
    eyebrow: 'Recursos',
    title: 'Vehiculos, conductores y disponibilidad',
    description: 'Mantiene la flota real, la documentacion y la preparacion operativa semanal.',
  },
  studio: {
    label: 'Planificacion',
    icon: LayoutGrid,
    eyebrow: 'Produccion',
    title: 'Timeline, mapa y publicacion',
    description: 'Ajusta el horario por dia, valida la operacion y deja lista la publicacion.',
  },
};

function ViewTabs({ viewMode, setViewMode, hasStudioAccess }) {
  const tabs = [
    { id: 'dashboard', label: 'Panel', icon: Gauge, disabled: false },
    { id: 'fleet', label: 'Flota', icon: Bus, disabled: false },
    { id: 'studio', label: 'Planificacion', icon: LayoutGrid, disabled: !hasStudioAccess },
  ];

  return (
    <nav className="flex flex-wrap items-center gap-2">
      {tabs.map(({ id, label, icon: Icon, disabled }) => {
        const active = viewMode === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => !disabled && setViewMode(id)}
            disabled={disabled}
            title={disabled ? 'Abre una optimizacion desde Panel para entrar en Planificacion' : label}
            className={`gt-topbar-tab ${active ? 'gt-topbar-tab-active' : ''}`}
          >
            <Icon className="h-4 w-4" />
            <span>{label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function ContextChip({ icon: Icon, label, value, tone = 'default' }) {
  if (!value) return null;

  const toneClass = {
    default: 'border-white/10 bg-white/[0.04] text-slate-200',
    info: 'border-cyan-500/25 bg-cyan-500/10 text-cyan-100',
    warning: 'border-amber-500/25 bg-amber-500/10 text-amber-100',
    danger: 'border-rose-500/25 bg-rose-500/10 text-rose-100',
    success: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100',
  }[tone] || 'border-white/10 bg-white/[0.04] text-slate-200';

  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] ${toneClass}`}>
      {Icon ? <Icon className="h-3.5 w-3.5 opacity-80" /> : null}
      <span className="text-slate-400">{label}</span>
      <span className="font-semibold text-current">{value}</span>
    </div>
  );
}

function Header({ viewMode, setViewMode, hasStudioAccess, workspaceContext }) {
  const pageMeta = VIEW_META[viewMode] || VIEW_META.dashboard;
  const PageIcon = pageMeta.icon;

  const workspaceMeta = useMemo(() => {
    if (!workspaceContext) return null;
    const readiness = getWorkspaceReadinessConfig(workspaceContext.readiness_state);
    const statusLabel = getWorkspaceStatusLabel(workspaceContext);
    const pendingLabel = getWorkspacePendingLabel(workspaceContext);
    const nextActionLabel = getNextActionLabel(workspaceContext.next_recommended_action);
    const scopeLabel = getScopeLabel(workspaceContext.scope_summary);
    const conflicts = Number(workspaceContext.conflict_count || 0);
    const pendingVirtual = Number(workspaceContext.pending_virtual_count || 0);

    return {
      readiness,
      statusLabel,
      pendingLabel,
      nextActionLabel,
      scopeLabel,
      conflicts,
      pendingVirtual,
      cityLabel: String(workspaceContext.city_label || '').trim(),
      workspaceName: String(workspaceContext.name || '').trim(),
      activeDayLabel: String(workspaceContext.activeDayLabel || '').trim(),
    };
  }, [workspaceContext]);

  return (
    <header className="relative z-20 px-4 pt-4">
      <div className="gt-shell-card overflow-hidden">
        <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.16),transparent_30%),radial-gradient(circle_at_top_right,rgba(37,99,235,0.14),transparent_28%)]" />

        <div className="relative flex flex-col gap-4 px-5 py-4 xl:px-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="flex min-w-0 items-start gap-4">
              <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center overflow-hidden rounded-[18px] border border-cyan-400/20 bg-[#07121f] shadow-[0_18px_48px_rgba(5,18,30,0.38)]">
                <img src={tuttiSymbol} alt="TUTTI" className="h-full w-full object-cover" />
              </div>

              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-cyan-500/20 bg-cyan-500/8 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
                    TUTTI
                  </span>
                  <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    {pageMeta.eyebrow}
                  </span>
                </div>

                <div className="mt-3 flex flex-col gap-2 xl:flex-row xl:items-center">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-cyan-100">
                      <PageIcon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <h1
                        className="truncate text-[22px] font-semibold text-[#eef6fd]"
                        style={{ fontFamily: 'Sora, IBM Plex Sans, Segoe UI, sans-serif' }}
                      >
                        {pageMeta.title}
                      </h1>
                      <p className="mt-1 max-w-3xl text-[12px] text-slate-400">
                        {pageMeta.description}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col items-start gap-3 xl:items-end">
              <ViewTabs
                viewMode={viewMode}
                setViewMode={setViewMode}
                hasStudioAccess={hasStudioAccess}
              />

              {workspaceMeta ? (
                <div className="rounded-2xl border border-white/10 bg-[#081320]/82 px-4 py-3 shadow-[0_18px_38px_rgba(2,8,23,0.32)] backdrop-blur">
                  <div className="flex flex-wrap items-center gap-2">
                    <FolderKanban className="h-4 w-4 text-cyan-200" />
                    <span className="max-w-[240px] truncate text-[13px] font-semibold text-white">
                      {workspaceMeta.workspaceName || 'Optimizacion abierta'}
                    </span>
                    <span className="rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-slate-200 border-white/10 bg-white/[0.04]">
                      {workspaceMeta.statusLabel}
                    </span>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] ${workspaceMeta.readiness.chipClass}`}>
                      {workspaceMeta.readiness.label}
                    </span>
                  </div>

                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                    {workspaceMeta.cityLabel ? <span>{workspaceMeta.cityLabel}</span> : null}
                    {workspaceMeta.cityLabel && workspaceMeta.scopeLabel ? <span className="text-slate-600">•</span> : null}
                    <span>{workspaceMeta.scopeLabel}</span>
                    {workspaceMeta.activeDayLabel ? <span className="text-slate-600">•</span> : null}
                    {workspaceMeta.activeDayLabel ? <span>Dia activo: {workspaceMeta.activeDayLabel}</span> : null}
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-3 text-[12px] text-slate-400">
                  Abre o crea una optimizacion desde Panel para entrar en Planificacion con contexto operativo.
                </div>
              )}
            </div>
          </div>

          {workspaceMeta ? (
            <div className="flex flex-wrap gap-2">
              <ContextChip icon={ArrowUpRight} label="Siguiente paso" value={workspaceMeta.nextActionLabel} tone="info" />
              <ContextChip icon={Map} label="Estado" value={workspaceMeta.pendingLabel} tone="default" />
              <ContextChip
                icon={CalendarRange}
                label="Pendientes"
                value={String(workspaceMeta.pendingVirtual)}
                tone={workspaceMeta.pendingVirtual > 0 ? 'warning' : 'success'}
              />
              <ContextChip
                icon={Bus}
                label="Conflictos"
                value={String(workspaceMeta.conflicts)}
                tone={workspaceMeta.conflicts > 0 ? 'danger' : 'success'}
              />
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

const Layout = ({
  children,
  viewMode,
  setViewMode,
  hasStudioAccess = false,
  workspaceContext = null,
}) => (
  <div className="relative flex h-screen w-screen flex-col overflow-hidden gt-bg text-gt-text font-sans">
    <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.12),transparent_34%),linear-gradient(180deg,rgba(8,16,28,0.94),rgba(11,17,32,1))]" />

    <Header
      viewMode={viewMode}
      setViewMode={setViewMode}
      hasStudioAccess={hasStudioAccess}
      workspaceContext={workspaceContext}
    />

    <main className="relative z-10 flex flex-1 overflow-hidden px-4 pb-4 pt-3">
      <div className="flex min-h-0 w-full flex-1 overflow-hidden rounded-[22px] border border-white/6 bg-[#07111d]/44 p-0 shadow-[0_24px_80px_rgba(2,6,23,0.42)] backdrop-blur-[3px]">
        {children}
      </div>
    </main>
  </div>
);

export default Layout;
