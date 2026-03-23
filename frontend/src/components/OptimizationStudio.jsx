import React, { useCallback, useMemo, useState } from 'react';
import { Map } from 'lucide-react';
import MapView from './MapView';
import BusListPanel from './BusListPanel';
import { UnifiedWorkspace } from './workspace';

const STUDIO_TABS = [
  { id: 'map', label: 'Mapa operativo', description: 'Lectura geografica y foco por vehiculo', shortLabel: 'Mapa', icon: Map },
  { id: 'mixed', label: 'Vista mixta', description: 'Mapa y timeline coordinados', shortLabel: 'Mixto', icon: null },
  { id: 'workspace', label: 'Timeline operativo', description: 'Edicion detallada por bus y dia', shortLabel: 'Timeline', icon: null },
];

export default function OptimizationStudio({
  workspaceMode = 'create',
  routes = [],
  scheduleByDay = null,
  activeDay = 'L',
  onDayChange = null,
  validationReport = null,
  onValidationReportChange,
  onSave,
  selectedBusId = null,
  selectedRouteId = null,
  onBusSelect,
  onRouteSelect,
  onExport,
  pinnedBusIds = [],
  onTogglePinBus = null,
  onOpenReconciliation = null,
  onStudioLiveScheduleChange = null,
}) {
  const [studioTab, setStudioTab] = useState('map');
  const [splitPercent, setSplitPercent] = useState(40);
  const [isDraggingSplit, setIsDraggingSplit] = useState(false);
  const [liveScheduleByDay, setLiveScheduleByDay] = useState({});
  const activeStudioTab = STUDIO_TABS.find((tab) => tab.id === studioTab) || STUDIO_TABS[0];
  const isMapFocusedTab = studioTab === 'map' || studioTab === 'mixed';

  const currentDaySchedule = useMemo(
    () => scheduleByDay?.[activeDay]?.schedule || [],
    [scheduleByDay, activeDay],
  );

  const mapSchedule = liveScheduleByDay?.[activeDay] || currentDaySchedule;
  const workspaceInitialSchedule = Array.isArray(currentDaySchedule) ? currentDaySchedule : [];
  const effectivePinnedBusIds = useMemo(() => (
    (Array.isArray(pinnedBusIds) ? pinnedBusIds : [])
      .map((id) => String(id || '').trim())
      .filter((id) => id.length > 0)
  ), [pinnedBusIds]);
  const pinnedBusIdSet = useMemo(() => new Set(effectivePinnedBusIds), [effectivePinnedBusIds]);
  const mixedMapSchedule = useMemo(() => {
    if (pinnedBusIdSet.size === 0) return [];
    return (Array.isArray(mapSchedule) ? mapSchedule : []).filter((bus) => (
      pinnedBusIdSet.has(String(bus?.bus_id || bus?.id || ''))
    ));
  }, [mapSchedule, pinnedBusIdSet]);

  const handleLiveScheduleChange = useCallback((nextBuses) => {
    const safeBuses = Array.isArray(nextBuses) ? nextBuses : [];
    setLiveScheduleByDay((prev) => ({
      ...prev,
      [activeDay]: safeBuses,
    }));
    if (typeof onStudioLiveScheduleChange === 'function') {
      onStudioLiveScheduleChange(activeDay, safeBuses);
    }
  }, [activeDay, onStudioLiveScheduleChange]);

  const handleExportCurrentDay = useCallback((payload = {}) => {
    if (typeof onExport !== 'function') return;
    const schedulePayload = Array.isArray(payload?.schedule)
      ? payload.schedule
      : (Array.isArray(mapSchedule) ? mapSchedule : []);
    onExport({
      schedule: schedulePayload,
      day: activeDay,
      source: payload?.source || studioTab,
    });
  }, [activeDay, mapSchedule, onExport, studioTab]);

  const onDividerMouseDown = () => {
    if (studioTab !== 'mixed') return;
    setIsDraggingSplit(true);
  };

  const onMouseMove = (event) => {
    if (!isDraggingSplit) return;
    const viewportHeight = window.innerHeight || 1;
    const next = Math.max(25, Math.min(70, (event.clientY / viewportHeight) * 100));
    setSplitPercent(next);
  };

  const onMouseUp = () => {
    if (isDraggingSplit) {
      setIsDraggingSplit(false);
    }
  };

  React.useEffect(() => {
    if (!isDraggingSplit) return undefined;
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [isDraggingSplit]);

  return (
    <div className="h-full w-full min-h-0 flex flex-col gap-2">
      <div className="grid min-h-0 flex-1 grid-cols-[60px_minmax(0,1fr)] gap-2">
        <aside className="gt-panel rounded-[18px] border border-[#2a4057] bg-[#0b1521]/92 px-2 py-3 shadow-[0_16px_40px_rgba(2,6,23,0.24)]">
          <div className="flex h-full flex-col items-center gap-2">
            <div className="mb-1 rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-200 data-mono">
              Studio
            </div>
            {STUDIO_TABS.map((tab) => {
              const active = studioTab === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setStudioTab(tab.id)}
                  title={tab.label}
                  className={`flex w-full flex-col items-center gap-1 rounded-2xl border px-2 py-2 transition-all ${
                    active
                      ? 'border-cyan-400/35 bg-cyan-400/12 text-white shadow-[0_0_18px_rgba(34,211,238,0.14)]'
                      : 'border-white/8 bg-white/[0.02] text-slate-400 hover:border-white/15 hover:bg-white/[0.04] hover:text-slate-200'
                  }`}
                >
                  {Icon ? (
                    <Icon size={16} strokeWidth={2} />
                  ) : (
                    <span className="flex h-4 w-4 items-center justify-center text-[10px] font-bold leading-none">
                      {tab.shortLabel.slice(0, 1)}
                    </span>
                  )}
                  <span className="text-[9px] font-semibold uppercase tracking-[0.08em]">
                    {tab.shortLabel}
                  </span>
                </button>
              );
            })}
            <div className="mt-auto w-full rounded-2xl border border-white/8 bg-white/[0.02] px-2 py-2 text-center">
              <p className="text-[9px] uppercase tracking-[0.12em] text-slate-500">Dia</p>
              <p className="mt-1 text-[12px] font-semibold text-slate-200">{activeDay}</p>
            </div>
          </div>
        </aside>

        <div className="min-h-0 flex flex-col gap-2">
          <div className="rounded-[18px] border border-[#2a4057] bg-[#0b1521]/92 px-3 py-2 shadow-[0_16px_40px_rgba(2,6,23,0.24)]">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-cyan-300/90 data-mono">
                    Vista operativa
                  </p>
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-slate-300">
                    {activeStudioTab.label}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-slate-300">
                    {Array.isArray(mapSchedule) ? mapSchedule.length : 0} buses
                  </span>
                </div>
                <p className="mt-1 truncate text-[11px] text-slate-400">
                  {activeStudioTab.description}
                </p>
              </div>

              <div className="inline-flex w-fit flex-wrap items-center gap-1 rounded-xl border border-white/10 bg-white/[0.03] p-1">
                {STUDIO_TABS.map((tab) => {
                  const active = studioTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setStudioTab(tab.id)}
                      className={`rounded-lg px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] transition-all ${
                        active
                          ? 'bg-gt-accent text-white shadow-gt-glow'
                          : 'text-gt-text-muted hover:text-gt-text hover:bg-white/5'
                      }`}
                    >
                      {tab.shortLabel}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="flex-1 min-h-0">
            {studioTab === 'mixed' && (
              <div className="h-full w-full min-h-0 grid gap-3" style={{ gridTemplateRows: `${splitPercent}% 8px calc(${100 - splitPercent}% - 8px)` }}>
                <div className="min-h-0 rounded-xl gt-panel overflow-hidden">
                  <MapView
                    routes={routes}
                    schedule={mixedMapSchedule}
                    selectedBusId={selectedBusId}
                    selectedRouteId={selectedRouteId}
                    onBusSelect={onBusSelect}
                    pinnedBusIds={effectivePinnedBusIds}
                    onTogglePinBus={onTogglePinBus}
                  />
                </div>

                <div
                  onMouseDown={onDividerMouseDown}
                  className="w-full gt-glass rounded-full cursor-row-resize hover:bg-gt-accent/20 transition-colors"
                  title="Redimensionar mapa/workspace"
                  role="separator"
                  aria-orientation="horizontal"
                />

                <div className="min-h-0 overflow-hidden">
                  <UnifiedWorkspace
                    mode={workspaceMode}
                    routes={routes}
                    initialSchedule={workspaceInitialSchedule}
                    scheduleByDay={scheduleByDay}
                    activeDay={activeDay}
                    onDayChange={onDayChange}
                    validationReport={validationReport}
                    onValidationReportChange={onValidationReportChange}
                    onSave={onSave}
                    onLiveScheduleChange={handleLiveScheduleChange}
                    selectedBusIdExternal={selectedBusId}
                    selectedRouteIdExternal={selectedRouteId}
                    onBusSelect={onBusSelect}
                    onRouteSelect={onRouteSelect}
                    visibleBusIds={effectivePinnedBusIds}
                    pinnedBusIds={effectivePinnedBusIds}
                    onTogglePinBus={onTogglePinBus}
                    onExport={handleExportCurrentDay}
                  />
                </div>
              </div>
            )}

            {studioTab === 'map' && (
              <div className="h-full min-h-0 flex gap-3">
                <div className="flex-1 min-w-0 rounded-xl gt-panel overflow-hidden">
                  <MapView
                    routes={routes}
                    schedule={mapSchedule}
                    selectedBusId={selectedBusId}
                    selectedRouteId={selectedRouteId}
                    onBusSelect={onBusSelect}
                    pinnedBusIds={effectivePinnedBusIds}
                    onTogglePinBus={onTogglePinBus}
                  />
                </div>
                <div className="w-[300px] min-h-0 gt-sidebar rounded-xl overflow-hidden">
                  <BusListPanel
                    schedule={mapSchedule}
                    routes={routes}
                    selectedBusId={selectedBusId}
                    selectedRouteId={selectedRouteId}
                    onBusSelect={onBusSelect}
                    onRouteSelect={onRouteSelect}
                    onExport={() => handleExportCurrentDay({ schedule: mapSchedule, source: 'map' })}
                    activeDay={activeDay}
                    onOpenReconciliation={onOpenReconciliation}
                  />
                </div>
              </div>
            )}

            {studioTab === 'workspace' && (
              <div className="h-full min-h-0 overflow-hidden">
                <UnifiedWorkspace
                  mode={workspaceMode}
                  routes={routes}
                  initialSchedule={workspaceInitialSchedule}
                  scheduleByDay={scheduleByDay}
                  activeDay={activeDay}
                  onDayChange={onDayChange}
                  validationReport={validationReport}
                  onValidationReportChange={onValidationReportChange}
                  onSave={onSave}
                  onLiveScheduleChange={handleLiveScheduleChange}
                  selectedBusIdExternal={selectedBusId}
                  selectedRouteIdExternal={selectedRouteId}
                  onBusSelect={onBusSelect}
                  onRouteSelect={onRouteSelect}
                  pinnedBusIds={effectivePinnedBusIds}
                  onTogglePinBus={onTogglePinBus}
                  onExport={handleExportCurrentDay}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
