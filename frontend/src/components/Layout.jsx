import React from 'react';
import { LayoutGrid, Activity, Gauge } from 'lucide-react';

const DAY_CONFIG = [
  { key: 'L', label: 'L', full: 'Lunes' },
  { key: 'M', label: 'M', full: 'Martes' },
  { key: 'Mc', label: 'Mc', full: 'Miercoles' },
  { key: 'X', label: 'X', full: 'Jueves' },
  { key: 'V', label: 'V', full: 'Viernes' },
];

const MetricBadge = ({ value, label, color = 'text-white', icon: Icon }) => (
  <div className="control-card flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg">
    {Icon && <Icon className="w-3 h-3 text-slate-400" />}
    <span className={`text-[12px] font-semibold data-mono ${color}`}>{value}</span>
    <span className="text-[10px] text-slate-400 uppercase tracking-[0.12em]">{label}</span>
  </div>
);

const DaySelector = ({ scheduleByDay, activeDay, onDayChange }) => {
  if (!scheduleByDay) return null;

  return (
    <div className="flex items-center gap-0.5 bg-[#0f1824]/95 rounded-lg p-0.5 border border-[#2b4259] shadow-[inset_0_1px_0_rgba(180,220,240,0.08)]">
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
                    ? 'bg-[#24556f] text-[#e8f5fd] shadow-[inset_0_1px_0_rgba(210,241,255,0.2)]'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-[#172433]'
              }
            `}
          >
            <span className="text-[11px] font-semibold leading-none">{label}</span>
            <span className={`text-[9px] data-mono leading-none mt-0.5 ${isActive ? 'text-cyan-200' : 'text-slate-500'}`}>
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
    { id: 'dashboard', label: 'Control', icon: Gauge, requiresSchedule: false },
    { id: 'studio', label: 'Studio', icon: LayoutGrid, requiresSchedule: false },
  ];

  return (
    <div className="flex items-center gap-0.5 bg-[#0f1824]/95 rounded-lg p-0.5 border border-[#2b4259] shadow-[inset_0_1px_0_rgba(180,220,240,0.08)]">
      {tabs.map(({ id, label, icon: Icon, requiresSchedule }) => {
        const disabled = id === 'studio' ? !hasStudioAccess : (requiresSchedule && !hasStudioAccess);
        return (
        <button
          key={id}
          onClick={() => !disabled && setViewMode(id)}
          disabled={disabled}
          className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-[11px] font-medium transition-all disabled:cursor-not-allowed
            ${viewMode === id
              ? 'bg-[#24556f] text-[#e8f5fd] shadow-[inset_0_1px_0_rgba(210,241,255,0.2)]'
              : disabled
                ? 'text-slate-700'
                : 'text-slate-400 hover:text-slate-100 hover:bg-[#172433]'
            }
          `}
          title={disabled ? 'Abre una optimizacion desde Control para entrar al Studio' : label}
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
  hasStudioAccess
}) => {
  const hasSchedule = scheduleByDay && Object.values(scheduleByDay).some(day => day?.schedule?.length > 0);
  const showOperationalHeader = viewMode === 'studio';

  return (
    <header className="h-[62px] bg-[#08111b]/92 backdrop-blur-xl border-b border-[#243a4f] flex items-center px-5 flex-shrink-0 z-50 shadow-[0_10px_28px_rgba(2,8,14,0.34)]">
      <div className="flex items-center gap-2 mr-6">
        <div className="w-9 h-9 rounded-md bg-[#0f2435] border border-[#32546e] flex items-center justify-center shadow-[inset_0_1px_0_rgba(181,225,245,0.14)]">
          <span className="text-[12px] font-bold text-cyan-200 data-mono">TT</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[12px] font-semibold text-[#e5eff8] tracking-[0.12em] uppercase data-mono">TUTTI</span>
          <span className="text-[9px] text-slate-400 font-medium -mt-0.5 tracking-[0.16em] uppercase">Fleet Control Center</span>
        </div>
      </div>

      <ViewTabs
        viewMode={viewMode}
        setViewMode={setViewMode}
        hasStudioAccess={hasStudioAccess}
      />

      {showOperationalHeader && scheduleByDay && (
        <div className="ml-6">
          <DaySelector
            scheduleByDay={scheduleByDay}
            activeDay={activeDay}
            onDayChange={onDayChange}
          />
        </div>
      )}

      <div className="flex-1" />

      {showOperationalHeader && stats && hasSchedule && (
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
  setViewMode,
  hasStudioAccess = false,
}) => {
  return (
    <div className="flex flex-col h-screen w-screen bg-[var(--bg)] text-[#d7e4f1] font-sans overflow-hidden">
      <Header
        stats={stats}
        scheduleByDay={scheduleByDay}
        activeDay={activeDay}
        onDayChange={onDayChange}
        viewMode={viewMode}
        setViewMode={setViewMode}
        hasStudioAccess={hasStudioAccess}
      />
      <main className="flex-1 flex overflow-hidden">
        {children}
      </main>
    </div>
  );
};

export default Layout;
