import React, { useCallback, useMemo, useState } from 'react';
import MapView from './MapView';
import BusListPanel from './BusListPanel';
import { UnifiedWorkspace } from './workspace';

const STUDIO_TABS = [
  { id: 'mixed', label: 'Mixto' },
  { id: 'map', label: 'Mapa' },
  { id: 'workspace', label: 'Workspace' },
];

export default function OptimizationStudio({
  workspaceMode = 'create',
  routes = [],
  scheduleByDay = null,
  activeDay = 'L',
  validationReport = null,
  onValidationReportChange,
  onSave,
  onPublish,
  selectedBusId = null,
  selectedRouteId = null,
  onBusSelect,
  onRouteSelect,
  onExport,
  pinnedBusIds = [],
  onTogglePinBus = null,
}) {
  const [studioTab, setStudioTab] = useState('mixed');
  const [splitPercent, setSplitPercent] = useState(40);
  const [isDraggingSplit, setIsDraggingSplit] = useState(false);
  const [liveScheduleByDay, setLiveScheduleByDay] = useState({});

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
  }, [activeDay]);

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
      <div className="control-card rounded-[10px] border border-[#2f465d] p-2 flex items-center gap-2">
        {STUDIO_TABS.map((tab) => {
          const active = studioTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setStudioTab(tab.id)}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-[0.08em] transition-colors ${
                active
                  ? 'bg-[#214a63] text-[#d8edf8] border border-cyan-500/30'
                  : 'text-slate-400 border border-[#2f465d] hover:text-slate-200 hover:bg-[#182432]'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="flex-1 min-h-0">
        {studioTab === 'mixed' && (
          <div className="h-full w-full min-h-0 grid" style={{ gridTemplateRows: `${splitPercent}% 8px calc(${100 - splitPercent}% - 8px)` }}>
            <div className="min-h-0 rounded-[12px] border border-[#2f465d] overflow-hidden">
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
              className="w-full bg-[#1a2a3a] hover:bg-[#21405c] transition-colors border-y border-[#2f465d] cursor-row-resize"
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
                validationReport={validationReport}
                onValidationReportChange={onValidationReportChange}
                onSave={onSave}
                onPublish={onPublish}
                onLiveScheduleChange={handleLiveScheduleChange}
                selectedBusIdExternal={selectedBusId}
                selectedRouteIdExternal={selectedRouteId}
                onBusSelect={onBusSelect}
                onRouteSelect={onRouteSelect}
                visibleBusIds={effectivePinnedBusIds}
                pinnedBusIds={effectivePinnedBusIds}
                onTogglePinBus={onTogglePinBus}
              />
            </div>
          </div>
        )}

        {studioTab === 'map' && (
          <div className="h-full min-h-0 flex gap-3">
            <div className="flex-1 min-w-0 rounded-[12px] border border-[#2f465d] overflow-hidden">
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
            <div className="w-[320px] min-h-0">
              <BusListPanel
                schedule={mapSchedule}
                routes={routes}
                selectedBusId={selectedBusId}
                selectedRouteId={selectedRouteId}
                onBusSelect={onBusSelect}
                onRouteSelect={onRouteSelect}
                onExport={onExport}
                activeDay={activeDay}
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
              validationReport={validationReport}
              onValidationReportChange={onValidationReportChange}
              onSave={onSave}
              onPublish={onPublish}
              onLiveScheduleChange={handleLiveScheduleChange}
              selectedBusIdExternal={selectedBusId}
              selectedRouteIdExternal={selectedRouteId}
              onBusSelect={onBusSelect}
              onRouteSelect={onRouteSelect}
              pinnedBusIds={effectivePinnedBusIds}
              onTogglePinBus={onTogglePinBus}
            />
          </div>
        )}
      </div>
    </div>
  );
}
