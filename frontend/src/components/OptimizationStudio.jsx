import React, { useMemo, useState } from 'react';
import MapView from './MapView';
import { UnifiedWorkspace } from './workspace';

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
}) {
  const [splitPercent, setSplitPercent] = useState(40);
  const [isDraggingSplit, setIsDraggingSplit] = useState(false);
  const [liveSchedule, setLiveSchedule] = useState(null);

  const currentDaySchedule = useMemo(
    () => scheduleByDay?.[activeDay]?.schedule || [],
    [scheduleByDay, activeDay],
  );

  const mapSchedule = liveSchedule || currentDaySchedule;

  const onDividerMouseDown = () => {
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
    <div className="h-full w-full min-h-0 grid" style={{ gridTemplateRows: `${splitPercent}% 8px calc(${100 - splitPercent}% - 8px)` }}>
      <div className="min-h-0 rounded-[12px] border border-[#2f465d] overflow-hidden">
        <MapView
          routes={routes}
          schedule={mapSchedule}
          selectedBusId={selectedBusId}
          selectedRouteId={selectedRouteId}
          onBusSelect={onBusSelect}
        />
      </div>

      <button
        onMouseDown={onDividerMouseDown}
        className="w-full bg-[#1a2a3a] hover:bg-[#21405c] transition-colors border-y border-[#2f465d] cursor-row-resize"
        title="Redimensionar mapa/workspace"
      />

      <div className="min-h-0 overflow-hidden">
        <UnifiedWorkspace
          mode={workspaceMode}
          routes={routes}
          initialSchedule={Array.isArray(currentDaySchedule) && currentDaySchedule.length > 0 ? currentDaySchedule : null}
          scheduleByDay={scheduleByDay}
          activeDay={activeDay}
          validationReport={validationReport}
          onValidationReportChange={onValidationReportChange}
          onSave={onSave}
          onPublish={onPublish}
          onLiveScheduleChange={setLiveSchedule}
        />
      </div>
    </div>
  );
}
