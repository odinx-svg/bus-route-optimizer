import React from 'react';
import { LayoutGrid, Gauge, Bus } from 'lucide-react';
import tuttiSymbol from '../assets/tutti-symbol.svg';
import { getWorkspaceStatusLabel } from '../utils/workspaceStatus';

const DAY_CONFIG = [
  { key: 'L', label: 'L', full: 'Lunes' },
  { key: 'M', label: 'M', full: 'Martes' },
  { key: 'Mc', label: 'Mc', full: 'Miercoles' },
  { key: 'X', label: 'X', full: 'Jueves' },
  { key: 'V', label: 'V', full: 'Viernes' },
];

const DaySelector = ({ scheduleByDay, activeDay, onDayChange }) => {
  if (!scheduleByDay) return null;

  return (
    <div className="flex items-center gap-0.5 gt-glass rounded-xl p-1">
      {DAY_CONFIG.map(({ key, label, full }) => {
        const isActive = activeDay === key;
        const buses = scheduleByDay[key]?.stats?.total_buses || 0;

        return (
          <button
            key={key}
            onClick={() => onDayChange(key)}
            title={`${full}: ${buses} buses`}
            className={`
              flex flex-col items-center px-3 py-1.5 rounded-lg transition-all duration-200 min-w-[44px] data-mono
              ${isActive
                    ? 'bg-gt-accent text-white shadow-gt-glow'
                    : 'text-gt-text-muted hover:text-gt-text hover:bg-white/5'
              }
            `}
          >
            <span className="text-[11px] font-semibold leading-none">{label}</span>
            <span className={`text-[9px] data-mono leading-none mt-0.5 ${isActive ? 'text-white/80' : 'text-gt-text-muted/60'}`}>
              {buses}
            </span>
          </button>
        );
      })}
    </div>
  );
};

const ViewTabs = ({ viewMode, setViewMode, hasStudioAccess }) => {
  const tabs = [
    { id: 'dashboard', label: 'Panel', icon: Gauge, requiresSchedule: false },
    { id: 'fleet', label: 'Flota', icon: Bus, requiresSchedule: false },
    { id: 'studio', label: 'Planificacion', icon: LayoutGrid, requiresSchedule: false },
  ];

  return (
    <div className="flex items-center gap-0.5 gt-glass rounded-xl p-1">
      {tabs.map(({ id, label, icon: Icon, requiresSchedule }) => {
        const disabled = id === 'studio' ? !hasStudioAccess : (requiresSchedule && !hasStudioAccess);
        return (
        <button
          key={id}
          onClick={() => !disabled && setViewMode(id)}
          disabled={disabled}
          className={`
            flex items-center gap-2 px-4 py-2 rounded-lg text-[11px] font-medium transition-all duration-200 disabled:cursor-not-allowed
            ${viewMode === id
              ? 'bg-gt-accent text-white shadow-gt-glow'
              : disabled
                ? 'text-gt-text-muted/30'
                : 'text-gt-text-muted hover:text-gt-text hover:bg-white/5'
            }
          `}
          title={disabled ? 'Abre una optimizacion desde Panel para entrar en Planificacion' : label}
        >
          <Icon className="w-3.5 h-3.5" />
          {label}
        </button>
        );
      })}
    </div>
  );
};

const Header = ({
  stats,
  scheduleByDay,
  activeDay,
  onDayChange,
  viewMode,
  setViewMode,
  hasStudioAccess,
  workspaceContext,
}) => {
  const showOperationalHeader = viewMode === 'studio';
  const sectionCopy = {
    dashboard: {
      title: 'Panel',
      subtitle: 'Centro de operaciones y seguimiento de optimizaciones',
    },
    fleet: {
      title: 'Flota',
      subtitle: 'Catalogo de vehiculos, empresas y carga masiva',
    },
    studio: {
      title: 'Planificacion',
      subtitle: 'Revision operativa, reconciliacion y publicacion',
    },
  }[viewMode] || {
    title: 'Tutti',
    subtitle: 'Control operativo',
  };

  return (
    <header className="gt-header-gradient gt-border-b flex items-center px-4 py-2.5 flex-shrink-0 z-50 gap-3">
      <div className="flex items-center gap-2.5 mr-1">
        <div className="w-10 h-10 rounded-[14px] border border-cyan-400/20 bg-[#0a1a29] flex items-center justify-center overflow-hidden shadow-[0_12px_32px_rgba(5,18,30,0.35)]">
          <img src={tuttiSymbol} alt="TUTTI" className="w-full h-full object-cover" />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-[12px] font-semibold text-gt-text tracking-[0.12em] uppercase data-mono">TUTTI</span>
          <span className="text-[9px] text-cyan-200/70 font-medium tracking-[0.16em] uppercase">
            {showOperationalHeader ? 'Operacion activa' : 'Centro de control'}
          </span>
        </div>
      </div>

      {!showOperationalHeader && (
        <div className="min-w-[200px]">
          <p className="text-[10px] uppercase tracking-[0.14em] text-cyan-300/90 data-mono">{sectionCopy.title}</p>
          <p className="text-[11px] text-gt-text-muted mt-0.5">{sectionCopy.subtitle}</p>
        </div>
      )}

      <ViewTabs
        viewMode={viewMode}
        setViewMode={setViewMode}
        hasStudioAccess={hasStudioAccess}
      />

      {workspaceContext && (
        <div className={`${showOperationalHeader ? 'hidden' : 'hidden xl:flex'} items-center gap-3 ml-1 rounded-xl border border-[#2a4057] bg-[#091425]/90 px-3 py-2 min-w-[320px]`}>
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Estado actual</p>
            <p className="text-[12px] font-semibold text-white truncate">
              {workspaceContext.name || 'Sin optimizacion abierta'}
            </p>
            <p className="text-[10px] text-slate-400 mt-0.5">
              {showOperationalHeader ? `Dia ${workspaceContext.activeDayLabel || activeDay || '-'}` : 'Vista general'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] text-slate-200">
              {getWorkspaceStatusLabel(workspaceContext)}
            </span>
          </div>
        </div>
      )}

      {showOperationalHeader && scheduleByDay && (
        <div className="ml-1 flex items-center gap-3">
          <div className="hidden md:block min-w-[170px]">
            <p className="text-[10px] uppercase tracking-[0.14em] text-cyan-300/90 data-mono">{sectionCopy.title}</p>
            <p className="text-[11px] text-gt-text-muted mt-0.5 truncate">
              {workspaceContext?.name || 'Sin planificacion abierta'}
            </p>
          </div>
          <DaySelector
            scheduleByDay={scheduleByDay}
            activeDay={activeDay}
            onDayChange={onDayChange}
          />
        </div>
      )}

      <div className="flex-1" />
    </header>
  );
};

const Layout = ({
  children,
  stats,
  scheduleByDay,
  activeDay,
  onDayChange,
  viewMode,
  setViewMode,
  hasStudioAccess = false,
  workspaceContext = null,
}) => {
  return (
    <div className="flex flex-col h-screen w-screen gt-bg text-gt-text font-sans overflow-hidden">
      <Header
        stats={stats}
        scheduleByDay={scheduleByDay}
        activeDay={activeDay}
        onDayChange={onDayChange}
        viewMode={viewMode}
        setViewMode={setViewMode}
        hasStudioAccess={hasStudioAccess}
        workspaceContext={workspaceContext}
      />
      <main className="flex-1 flex overflow-hidden px-4 pb-4 pt-2 gap-4">
        {children}
      </main>
    </div>
  );
};

export default Layout;
