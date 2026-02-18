import React from 'react';
import { Map as MapIcon, LayoutGrid, Box, Activity, Bus, Gauge } from 'lucide-react';

const DAY_CONFIG = [
  { key: 'L', label: 'L', full: 'Lunes' },
  { key: 'M', label: 'M', full: 'Martes' },
  { key: 'Mc', label: 'Mc', full: 'Miercoles' },
  { key: 'X', label: 'X', full: 'Jueves' },
  { key: 'V', label: 'V', full: 'Viernes' },
];

const MetricBadge = ({ value, label, color = 'text-white', icon: Icon }) => (
  <div className="control-card flex items-center gap-1.5 px-2.5 py-1.5 rounded-md">
    {Icon && <Icon className="w-3 h-3 text-slate-500" />}
    <span className={`text-[12px] font-semibold data-mono ${color}`}>{value}</span>
    <span className="text-[10px] text-slate-500 uppercase tracking-[0.12em]">{label}</span>
  </div>
);

const DaySelector = ({ scheduleByDay, activeDay, onDayChange }) => {
  if (!scheduleByDay) return null;

  return (
    <div className="flex items-center gap-0.5 bg-[#101a26] rounded-md p-0.5 border border-[#2b4056]">
      {DAY_CONFIG.map(({ key, label, full }) => {
        const isActive = activeDay === key;
        const buses = scheduleByDay[key]?.stats?.total_buses || 0;

        return (
          <button
            key={key}
            onClick={() => onDayChange(key)}
            title={`${full}: ${buses} buses`}
            className={`
              flex flex-col items-center px-2 py-1 rounded-sm transition-all duration-150 min-w-[36px] data-mono
              ${isActive
                ? 'bg-[#214a63] text-[#d8edf8] shadow-sm'
                : 'text-slate-500 hover:text-slate-200 hover:bg-[#182432]'
              }
            `}
          >
            <span className="text-[11px] font-semibold leading-none">{label}</span>
            <span className={`text-[9px] data-mono leading-none mt-0.5 ${isActive ? 'text-cyan-200' : 'text-slate-600'}`}>
              {buses}
            </span>
          </button>
        );
      })}
    </div>
  );
};

const ViewTabs = ({ viewMode, setViewMode, hasSchedule }) => {
  const tabs = [
    { id: 'dashboard', label: 'Control', icon: Gauge, requiresSchedule: false },
    { id: 'map', label: 'Mapa', icon: MapIcon, requiresSchedule: false },
    { id: 'workspace', label: 'Workspace', icon: LayoutGrid, requiresSchedule: false },
    { id: 'fleet', label: 'Flota', icon: Bus, requiresSchedule: false },
    { id: 'montecarlo', label: 'Monte Carlo', icon: Box, requiresSchedule: true },
  ];

  return (
    <div className="flex items-center gap-0.5 bg-[#101a26] rounded-md p-0.5 border border-[#2b4056]">
      {tabs.map(({ id, label, icon: Icon, requiresSchedule }) => {
        const disabled = requiresSchedule && !hasSchedule;
        return (
        <button
          key={id}
          onClick={() => !disabled && setViewMode(id)}
          disabled={disabled}
          className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-[11px] font-medium transition-all disabled:cursor-not-allowed
            ${viewMode === id
              ? 'bg-[#214a63] text-[#d8edf8] shadow-sm'
              : disabled
                ? 'text-slate-700'
                : 'text-slate-500 hover:text-slate-200 hover:bg-[#182432]'
            }
          `}
          title={disabled ? 'Disponible al tener un horario optimizado' : label}
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
  setViewMode
}) => {
  const hasSchedule = scheduleByDay && Object.values(scheduleByDay).some(day => day?.schedule?.length > 0);

  return (
    <header className="h-[58px] bg-[#0a111a]/95 backdrop-blur-xl border-b border-[#24374a] flex items-center px-4 flex-shrink-0 z-50">
      <div className="flex items-center gap-2 mr-6">
        <div className="w-8 h-8 rounded-sm bg-[#102435] border border-[#2d4d65] flex items-center justify-center">
          <span className="text-[12px] font-bold text-cyan-200 data-mono">TT</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[12px] font-semibold text-[#dce8f3] tracking-[0.12em] uppercase data-mono">TUTTI</span>
          <span className="text-[9px] text-slate-500 font-medium -mt-0.5 tracking-[0.16em] uppercase">Fleet Control Center</span>
        </div>
      </div>

      <ViewTabs
        viewMode={viewMode}
        setViewMode={setViewMode}
        hasSchedule={hasSchedule}
      />

      {scheduleByDay && (
        <div className="ml-6">
          <DaySelector
            scheduleByDay={scheduleByDay}
            activeDay={activeDay}
            onDayChange={onDayChange}
          />
        </div>
      )}

      <div className="flex-1" />

      {stats && hasSchedule && (
        <div className="flex items-center gap-2">
          {stats.buses > 0 && (
            <MetricBadge
              value={stats.buses}
              label="buses"
              color="text-indigo-400"
              icon={Activity}
            />
          )}
          {stats.total_entries > 0 && (
            <MetricBadge
              value={stats.total_entries}
              label="entradas"
              color="text-indigo-300"
            />
          )}
          {stats.total_exits > 0 && (
            <MetricBadge
              value={stats.total_exits}
              label="salidas"
              color="text-amber-400"
            />
          )}
          {stats.avg_routes_per_bus > 0 && (
            <MetricBadge
              value={stats.avg_routes_per_bus}
              label="media/bus"
              color="text-emerald-400"
            />
          )}
        </div>
      )}
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
  setViewMode
}) => {
  return (
    <div className="flex flex-col h-screen w-screen bg-[#070b10] text-[#d7e4f1] font-sans overflow-hidden">
      <Header
        stats={stats}
        scheduleByDay={scheduleByDay}
        activeDay={activeDay}
        onDayChange={onDayChange}
        viewMode={viewMode}
        setViewMode={setViewMode}
      />
      <main className="flex-1 flex overflow-hidden">
        {children}
      </main>
    </div>
  );
};

export default Layout;
