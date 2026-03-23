import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Map } from 'lucide-react';

import BusListPanel from './BusListPanel';
import MapView from './MapView';
import PlanningOverviewBar, { PlanningDetailPanel } from './PlanningOverviewBar';
import { UnifiedWorkspace } from './workspace';

const STUDIO_TABS = [
  { id: 'map', label: 'Mapa operativo', shortLabel: 'Mapa', icon: Map },
  { id: 'mixed', label: 'Vista mixta', shortLabel: 'Mixto', icon: null },
  { id: 'workspace', label: 'Timeline operativo', shortLabel: 'Timeline', icon: null },
];

const INSPECTOR_WIDTH = 336;

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
  workspace = null,
  stats = null,
  onOpenRules = null,
  onPublishWeek = null,
  publishDisabled = false,
  optimizationOptions = null,
  workspaceCompanies = [],
}) {
  const [studioTab, setStudioTab] = useState('map');
  const [drawerPercent, setDrawerPercent] = useState(34);
  const [isDraggingSplit, setIsDraggingSplit] = useState(false);
  const [liveScheduleByDay, setLiveScheduleByDay] = useState({});
  const [inspectorOpen, setInspectorOpen] = useState(() => (
    typeof window === 'undefined' ? true : window.innerWidth >= 1440
  ));
  const [detailOpen, setDetailOpen] = useState(false);
  const [timelineDrawerOpen, setTimelineDrawerOpen] = useState(true);

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
    if (pinnedBusIdSet.size === 0) return Array.isArray(mapSchedule) ? mapSchedule : [];
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

  const handleStudioTabChange = useCallback((nextTab) => {
    setStudioTab(nextTab);
    if (nextTab === 'mixed') {
      setTimelineDrawerOpen(true);
    }
    if (nextTab === 'workspace') {
      setDetailOpen(false);
      setInspectorOpen(false);
    } else if (typeof window !== 'undefined' && window.innerWidth >= 1200) {
      setInspectorOpen(true);
    }
  }, []);

  const onDividerMouseDown = () => {
    if (studioTab !== 'mixed' || !timelineDrawerOpen) return;
    setIsDraggingSplit(true);
  };

  const onMouseMove = useCallback((event) => {
    if (!isDraggingSplit) return;
    const viewportHeight = window.innerHeight || 1;
    const next = Math.max(22, Math.min(48, ((viewportHeight - event.clientY) / viewportHeight) * 100));
    setDrawerPercent(next);
  }, [isDraggingSplit]);

  const onMouseUp = useCallback(() => {
    if (isDraggingSplit) {
      setIsDraggingSplit(false);
    }
  }, [isDraggingSplit]);

  useEffect(() => {
    if (!isDraggingSplit) return undefined;
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [isDraggingSplit, onMouseMove, onMouseUp]);

  const renderMapCanvas = (schedule) => (
    <div className="h-full min-h-0 overflow-hidden rounded-[18px] border border-[#24384e] bg-[#07111b]">
      <MapView
        routes={routes}
        schedule={schedule}
        selectedBusId={selectedBusId}
        selectedRouteId={selectedRouteId}
        onBusSelect={onBusSelect}
        pinnedBusIds={effectivePinnedBusIds}
        onTogglePinBus={onTogglePinBus}
      />
    </div>
  );

  const renderInspector = () => {
    if (studioTab === 'workspace') return null;

    if (!inspectorOpen) {
      return (
        <button
          type="button"
          onClick={() => setInspectorOpen(true)}
          className="flex h-full w-11 flex-col items-center justify-center gap-3 rounded-[16px] border border-[#2a4057] bg-[#0b1521]/92 text-slate-300 hover:bg-white/[0.04]"
          title="Abrir inspector"
        >
          <ChevronLeft className="h-4 w-4" />
          <span className="[writing-mode:vertical-rl] rotate-180 text-[10px] font-semibold uppercase tracking-[0.12em]">
            {detailOpen ? 'Detalle' : 'Inspector'}
          </span>
        </button>
      );
    }

    return (
      <div
        className="min-h-0 rounded-[18px] border border-[#2a4057] bg-[#0b1521]/92 shadow-[0_14px_34px_rgba(2,6,23,0.22)]"
        style={{ width: INSPECTOR_WIDTH }}
      >
        {detailOpen ? (
          <PlanningDetailPanel
            workspace={workspace}
            activeDay={activeDay}
            stats={stats}
            scheduleByDay={scheduleByDay}
            optimizationOptions={optimizationOptions}
            workspaceCompanies={workspaceCompanies}
            onOpenReconciliation={() => onOpenReconciliation?.()}
            onOpenRules={onOpenRules}
            onClose={() => setDetailOpen(false)}
          />
        ) : (
          <BusListPanel
            schedule={mapSchedule}
            routes={routes}
            selectedBusId={selectedBusId}
            selectedRouteId={selectedRouteId}
            onBusSelect={onBusSelect}
            onRouteSelect={onRouteSelect}
            onExport={() => handleExportCurrentDay({ schedule: mapSchedule, source: studioTab })}
            activeDay={activeDay}
            onOpenReconciliation={onOpenReconciliation}
            allowBoardView={false}
            compact
          />
        )}
      </div>
    );
  };

  return (
    <div className="h-full w-full min-h-0 flex flex-col gap-2">
      <PlanningOverviewBar
        workspace={workspace}
        activeDay={activeDay}
        stats={stats}
        scheduleByDay={scheduleByDay}
        onOpenReconciliation={() => onOpenReconciliation?.()}
        onOpenRules={onOpenRules}
        onPublishWeek={onPublishWeek}
        publishDisabled={publishDisabled}
        optimizationOptions={optimizationOptions}
        studioTab={studioTab}
        inspectorOpen={inspectorOpen}
        detailOpen={detailOpen}
        onToggleInspector={() => setInspectorOpen((prev) => !prev)}
        onToggleDetail={() => {
          setDetailOpen((prev) => {
            const next = !prev;
            if (next) setInspectorOpen(true);
            return next;
          });
        }}
      />

      <div className="grid min-h-0 flex-1 grid-cols-[52px_minmax(0,1fr)] gap-2">
        <aside className="rounded-[16px] border border-[#2a4057] bg-[#0b1521]/92 px-1.5 py-2 shadow-[0_14px_34px_rgba(2,6,23,0.22)]">
          <div className="flex h-full flex-col items-center gap-2">
            {STUDIO_TABS.map((tab) => {
              const active = studioTab === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => handleStudioTabChange(tab.id)}
                  title={tab.label}
                  className={`flex w-full flex-col items-center gap-1 rounded-2xl border px-1 py-2 transition-all ${
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
                  <span className="text-[8px] font-semibold uppercase tracking-[0.08em]">
                    {tab.shortLabel}
                  </span>
                </button>
              );
            })}

            {studioTab === 'mixed' ? (
              <button
                type="button"
                onClick={() => setTimelineDrawerOpen((prev) => !prev)}
                className="mt-2 flex w-full flex-col items-center gap-1 rounded-2xl border border-white/8 bg-white/[0.02] px-1 py-2 text-slate-400 hover:border-white/15 hover:bg-white/[0.04] hover:text-slate-200"
                title={timelineDrawerOpen ? 'Ocultar drawer timeline' : 'Abrir drawer timeline'}
              >
                <span className="flex h-4 w-4 items-center justify-center text-[10px] font-bold leading-none">
                  {timelineDrawerOpen ? '−' : '+'}
                </span>
                <span className="text-[8px] font-semibold uppercase tracking-[0.08em]">Drawer</span>
              </button>
            ) : null}

            <div className="mt-auto w-full rounded-2xl border border-white/8 bg-white/[0.02] px-1 py-2 text-center">
              <p className="text-[8px] uppercase tracking-[0.12em] text-slate-500">Dia</p>
              <p className="mt-1 text-[12px] font-semibold text-slate-200">{activeDay}</p>
            </div>
          </div>
        </aside>

        <div className="min-h-0 flex gap-2">
          <div className="min-h-0 min-w-0 flex-1 rounded-[18px] border border-[#24384e] bg-[#08121d]/92 p-2 shadow-[0_18px_42px_rgba(2,6,23,0.24)]">
            {studioTab === 'map' && (
              <div className="h-full min-h-0">
                {renderMapCanvas(mapSchedule)}
              </div>
            )}

            {studioTab === 'mixed' && (
              <div
                className="grid h-full min-h-0 gap-2"
                style={{
                  gridTemplateRows: timelineDrawerOpen
                    ? `minmax(0, calc(100% - ${drawerPercent}% - 8px)) 8px minmax(0, ${drawerPercent}%)`
                    : 'minmax(0, 1fr)',
                }}
              >
                <div className="min-h-0">
                  {renderMapCanvas(mixedMapSchedule)}
                </div>

                {timelineDrawerOpen ? (
                  <>
                    <div
                      onMouseDown={onDividerMouseDown}
                      className="w-full cursor-row-resize rounded-full border border-white/10 bg-white/[0.06] transition-colors hover:bg-cyan-400/20"
                      title="Redimensionar timeline"
                      role="separator"
                      aria-orientation="horizontal"
                    />

                    <div className="min-h-0 overflow-hidden rounded-[18px] border border-[#24384e] bg-[#09131f]">
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
                  </>
                ) : null}
              </div>
            )}

            {studioTab === 'workspace' && (
              <div className="h-full min-h-0 overflow-hidden rounded-[18px] border border-[#24384e] bg-[#09131f]">
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

          {renderInspector()}
        </div>
      </div>
    </div>
  );
}
