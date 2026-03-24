import React, { useMemo } from 'react';
import { Bus, FolderKanban, Gauge, LayoutGrid } from 'lucide-react';

import tuttiSymbol from '../assets/tutti-symbol.svg';
import {
  getWorkspaceReadinessConfig,
  getWorkspaceStatusLabel,
} from '../utils/workspaceStatus';

const VIEW_META = {
  dashboard: {
    label: 'Panel',
    icon: Gauge,
    eyebrow: 'Centro operativo',
  },
  fleet: {
    label: 'Flota',
    icon: Bus,
    eyebrow: 'Recursos',
  },
  studio: {
    label: 'Planificacion',
    icon: LayoutGrid,
    eyebrow: 'Produccion',
  },
};

function ViewTabs({ viewMode, setViewMode, hasStudioAccess }) {
  const tabs = [
    { id: 'dashboard', label: 'Panel', icon: Gauge, disabled: false },
    { id: 'fleet', label: 'Flota', icon: Bus, disabled: false },
    { id: 'studio', label: 'Planificacion', icon: LayoutGrid, disabled: !hasStudioAccess },
  ];

  return (
    <nav className="flex flex-wrap items-center gap-1.5 xl:flex-nowrap">
      {tabs.map(({ id, label, icon: Icon, disabled }) => {
        const active = viewMode === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => !disabled && setViewMode(id)}
            disabled={disabled}
            title={disabled ? 'Abre una optimizacion desde Panel para entrar en Planificacion' : label}
            className={`gt-strip-tab ${active ? 'gt-strip-tab-active' : ''}`}
          >
            <Icon className="h-3.5 w-3.5" />
            <span>{label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function Header({ viewMode, setViewMode, hasStudioAccess, workspaceContext }) {
  const pageMeta = VIEW_META[viewMode] || VIEW_META.dashboard;

  const workspaceMeta = useMemo(() => {
    if (!workspaceContext) return null;
    const readiness = getWorkspaceReadinessConfig(workspaceContext.readiness_state);
    const statusLabel = getWorkspaceStatusLabel(workspaceContext);

    return {
      readiness,
      statusLabel,
      workspaceName: String(workspaceContext.name || '').trim(),
      activeDayLabel: String(workspaceContext.activeDayLabel || '').trim(),
    };
  }, [workspaceContext]);

  return (
    <header className="relative z-20 px-3 pt-2">
      <div className="gt-app-strip">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-xl border border-cyan-400/20 bg-[#07121f] shadow-[0_12px_28px_rgba(5,18,30,0.26)]">
            <img src={tuttiSymbol} alt="TUTTI" className="h-full w-full object-cover" />
          </div>

          <div className="flex min-w-0 items-center gap-2">
            <span className="rounded-full border border-cyan-500/18 bg-cyan-500/8 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
              TUTTI
            </span>
            <span className="hidden text-[10px] uppercase tracking-[0.16em] text-slate-500 lg:inline">
              {pageMeta.eyebrow}
            </span>
          </div>

          <div className="hidden h-5 w-px bg-white/10 xl:block" />

          <div className="hidden xl:block">
            <ViewTabs
              viewMode={viewMode}
              setViewMode={setViewMode}
              hasStudioAccess={hasStudioAccess}
            />
          </div>
        </div>

        <div className="flex min-w-0 items-center justify-end gap-2">
          <div className="xl:hidden">
            <ViewTabs
              viewMode={viewMode}
              setViewMode={setViewMode}
              hasStudioAccess={hasStudioAccess}
            />
          </div>

          {workspaceMeta ? (
            <div className="hidden min-w-0 items-center gap-2 rounded-2xl border border-white/10 bg-[#081320]/84 px-3 py-1.5 shadow-[0_10px_24px_rgba(2,8,23,0.24)] backdrop-blur md:flex">
              <FolderKanban className="h-3.5 w-3.5 flex-shrink-0 text-cyan-200" />
              <span className="max-w-[220px] truncate text-[12px] font-semibold text-white">
                {workspaceMeta.workspaceName || 'Optimizacion abierta'}
              </span>
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-slate-200">
                {workspaceMeta.statusLabel}
              </span>
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] ${workspaceMeta.readiness.chipClass}`}>
                {workspaceMeta.readiness.label}
              </span>
              {workspaceMeta.activeDayLabel ? (
                <span className="text-[11px] text-slate-400">
                  {workspaceMeta.activeDayLabel}
                </span>
              ) : null}
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

    <main className="relative z-10 flex flex-1 overflow-hidden px-3 pb-3 pt-2">
      <div className="flex min-h-0 w-full flex-1 overflow-hidden">
        {children}
      </div>
    </main>
  </div>
);

export default Layout;
