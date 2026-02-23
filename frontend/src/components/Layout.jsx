import React from 'react';
import { LayoutGrid, Activity, Gauge } from 'lucide-react';
import tuttiSymbol from '../assets/tutti-symbol.svg';

const DAY_CONFIG = [
  { key: 'L', label: 'L', full: 'Lunes' },
  { key: 'M', label: 'M', full: 'Martes' },
  { key: 'Mc', label: 'Mc', full: 'Miercoles' },
  { key: 'X', label: 'X', full: 'Jueves' },
  { key: 'V', label: 'V', full: 'Viernes' },
];

const MetricBadge = ({ value, label, color = 'text-white', icon: Icon }) => (
  <div className="gt-glass flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg">
    {Icon && <Icon className="w-3 h-3 text-gt-text-muted" />}
    <span className={`text-[12px] font-semibold data-mono ${color}`}>{value}</span>
    <span className="text-[10px] text-gt-text-muted uppercase tracking-[0.12em]">{label}</span>
  </div>
);

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
    { id: 'dashboard', label: 'Control', icon: Gauge, requiresSchedule: false },
    { id: 'studio', label: 'Studio', icon: LayoutGrid, requiresSchedule: false },
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
    <header className="h-[62px] gt-header-gradient gt-border-b flex items-center px-5 flex-shrink-0 z-50">
      <div className="flex items-center gap-3 mr-8">
        <div className="w-9 h-9 rounded-lg gt-glass flex items-center justify-center overflow-hidden">
          <img src={tuttiSymbol} alt="TUTTI" className="w-full h-full object-cover" />
        </div>
        <div className="flex flex-col">
          <span className="text-[12px] font-semibold text-gt-text tracking-[0.12em] uppercase data-mono">TUTTI</span>
          <span className="text-[9px] text-gt-text-muted font-medium -mt-0.5 tracking-[0.16em] uppercase">Fleet Control Center</span>
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
          {stats.median_routes_per_bus > 0 && (
            <MetricBadge
              value={stats.median_routes_per_bus}
              label="mediana"
              color="text-cyan-300"
            />
          )}
          {(stats.max_routes_per_bus || 0) > 0 && (
            <MetricBadge
              value={`${stats.min_routes_per_bus || 0}-${stats.max_routes_per_bus || 0}`}
              label="carga min/max"
              color="text-slate-200"
            />
          )}
          {(stats.load_spread_routes || 0) > 0 && (
            <MetricBadge
              value={stats.load_spread_routes}
              label="diferencia"
              color={stats.load_spread_routes > 2 ? 'text-rose-300' : 'text-emerald-300'}
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
    <div className="flex flex-col h-screen w-screen gt-bg text-gt-text font-sans overflow-hidden">
      <Header
        stats={stats}
        scheduleByDay={scheduleByDay}
        activeDay={activeDay}
        onDayChange={onDayChange}
        viewMode={viewMode}
        setViewMode={setViewMode}
        hasStudioAccess={hasStudioAccess}
      />
      <main className="flex-1 flex overflow-hidden p-4 gap-4">
        {children}
      </main>
    </div>
  );
};

export default Layout;
