import React, { useEffect, useState } from 'react';
import { LayoutGrid, Gauge, Bus } from 'lucide-react';
import tuttiSymbol from '../assets/tutti-symbol.svg';

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
  viewMode,
  setViewMode,
  hasStudioAccess,
}) => {
  return (
    <header className="gt-header-gradient gt-border-b relative flex items-center justify-center px-4 py-2.5 flex-shrink-0 z-50">
      <div className="absolute left-4 top-1/2 flex -translate-y-1/2 items-center gap-2.5">
        <div className="w-10 h-10 rounded-[14px] border border-cyan-400/20 bg-[#0a1a29] flex items-center justify-center overflow-hidden shadow-[0_12px_32px_rgba(5,18,30,0.35)]">
          <img src={tuttiSymbol} alt="TUTTI" className="w-full h-full object-cover" />
        </div>
        <span className="text-[12px] font-semibold text-gt-text tracking-[0.12em] uppercase data-mono">TUTTI</span>
      </div>

      <ViewTabs
        viewMode={viewMode}
        setViewMode={setViewMode}
        hasStudioAccess={hasStudioAccess}
      />
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
  const [isHeaderVisible, setIsHeaderVisible] = useState(false);
  const [isHeaderHovered, setIsHeaderHovered] = useState(false);

  useEffect(() => {
    const handleMouseMove = (event) => {
      const y = Number(event?.clientY || 0);
      if (y <= 56) {
        setIsHeaderVisible(true);
        return;
      }
      if (y >= 120 && !isHeaderHovered) {
        setIsHeaderVisible(false);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [isHeaderHovered]);

  return (
    <div className="relative flex flex-col h-screen w-screen gt-bg text-gt-text font-sans overflow-hidden">
      <div
        className="absolute top-0 left-0 right-0 h-5 z-40"
        onMouseEnter={() => setIsHeaderVisible(true)}
      />

      <div
        className={`absolute top-0 left-0 right-0 z-50 transition-transform duration-200 ease-out ${
          isHeaderVisible ? 'translate-y-0' : '-translate-y-[110%]'
        }`}
        onMouseEnter={() => {
          setIsHeaderHovered(true);
          setIsHeaderVisible(true);
        }}
        onMouseLeave={() => {
          setIsHeaderHovered(false);
          setIsHeaderVisible(false);
        }}
      >
        <Header
          viewMode={viewMode}
          setViewMode={setViewMode}
          hasStudioAccess={hasStudioAccess}
        />
      </div>

      <main className="flex-1 flex overflow-hidden px-4 pb-4 pt-4 gap-4">
        {children}
      </main>
    </div>
  );
};

export default Layout;
