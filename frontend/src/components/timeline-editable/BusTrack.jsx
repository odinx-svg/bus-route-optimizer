/**
 * BusTrack - Fila de un bus en el timeline
 * 
 * Muestra:
 * - Label del bus (izquierda, sticky)
 * - Track con las rutas posicionadas
 * - Drop zones para añadir rutas
 * - Indicadores de conflicto
 */

import { useDroppable } from '@dnd-kit/core';
import { RouteLego } from './RouteLego';
import { Bus, AlertCircle, MoreHorizontal, Lock, Unlock, Trash2 } from 'lucide-react';
import { useState, useCallback } from 'react';
import { useTimelineEditableStore } from '../../stores/timelineEditableStore';

export function BusTrack({ bus, index, timeRange, pixelsPerMinute, viewMode, onRouteClick }) {
  const { isOver, setNodeRef } = useDroppable({
    id: `bus-${bus.busId}`,
    data: { type: 'bus', busId: bus.busId }
  });

  const { 
    toggleRouteLock, 
    moveRoute,
    removeBus,
    lockAllRoutesInBus,
    unlockAllRoutesInBus 
  } = useTimelineEditableStore();

  const [showControls, setShowControls] = useState(false);
  const startMinutes = timeRange.start * 60;

  const handleLockToggle = useCallback((routeId) => {
    toggleRouteLock(routeId);
  }, [toggleRouteLock]);

  const handleClearBus = useCallback(() => {
    const lockedCount = bus.routes.filter(r => r.isLocked).length;
    const msg = lockedCount > 0 
      ? `¿Eliminar las rutas no bloqueadas del Bus ${bus.busName || bus.busId}? (${lockedCount} bloqueadas se mantendrán)`
      : `¿Eliminar todas las rutas del Bus ${bus.busName || bus.busId}?`;
    
    if (window.confirm(msg)) {
      bus.routes.forEach(route => {
        if (!route.isLocked) {
          moveRoute(route.route_id, null);
        }
      });
    }
  }, [bus, moveRoute]);

  const handleLockAll = useCallback(() => {
    const allLocked = bus.routes.every(r => r.isLocked);
    if (allLocked) {
      unlockAllRoutesInBus(bus.busId);
    } else {
      lockAllRoutesInBus(bus.busId, 'Bloqueado manualmente');
    }
  }, [bus.busId, bus.routes, lockAllRoutesInBus, unlockAllRoutesInBus]);

  const allLocked = bus.routes.length > 0 && bus.routes.every(r => r.isLocked);
  const hasConflicts = bus.routes.some(r => r.hasConflict);

  return (
    <div 
      className="flex items-stretch gap-3 group"
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(false)}
    >
      {/* Label del bus (sticky) */}
      <div className="w-36 flex-shrink-0 bg-[#13131a] rounded-lg p-3 flex items-center gap-3 border border-gray-800 sticky left-0 z-10 shadow-xl">
        <div 
          className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold flex-shrink-0"
          style={{ backgroundColor: bus.color + '20', color: bus.color }}
        >
          <Bus className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-white font-semibold text-sm truncate">
            {bus.busName || bus.busId}
          </div>
          <div className="text-gray-500 text-xs flex items-center gap-1">
            {bus.routes.length} rutas
            {hasConflicts && (
              <AlertCircle className="w-3 h-3 text-red-400" />
            )}
          </div>
        </div>
      </div>

      {/* Track con las rutas */}
      <div
        ref={setNodeRef}
        className={`
          flex-1 relative min-h-[80px] bg-[#0f0f14] rounded-lg border
          ${isOver ? 'border-indigo-500 bg-indigo-500/10' : 'border-gray-800'}
          transition-colors duration-150 overflow-hidden
        `}
      >
        {/* Grid vertical de horas (sutil) */}
        <HourGrid 
          startHour={timeRange.start}
          endHour={timeRange.end}
          pixelsPerMinute={pixelsPerMinute}
        />

        {/* Rutas posicionadas */}
        <div className="relative h-full py-2">
          {bus.routes.map((route) => {
            const routeStartMinutes = timeToMinutes(route.currentStartTime || route.start_time);
            const left = (routeStartMinutes - startMinutes) * pixelsPerMinute;
            const width = route.duration_minutes * pixelsPerMinute;

            return (
              <div
                key={route.route_id}
                className="absolute top-1/2 -translate-y-1/2"
                style={{
                  left: `${left}px`,
                  width: `${Math.max(width, 80)}px`
                }}
              >
                <RouteLego
                  route={route}
                  compact={viewMode === 'compact' || width < 120}
                  onLockToggle={handleLockToggle}
                  onClick={onRouteClick}
                />
              </div>
            );
          })}
        </div>

        {/* Controles flotantes del bus */}
        <div className={`
          absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1
          transition-opacity duration-150
          ${showControls ? 'opacity-100' : 'opacity-0'}
        `}>
          <button
            onClick={handleLockAll}
            className={`
              p-1.5 rounded-md transition-colors
              ${allLocked 
                ? 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30' 
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'}
            `}
            title={allLocked ? 'Desbloquear todas' : 'Bloquear todas'}
          >
            {allLocked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={handleClearBus}
            className="p-1.5 rounded-md bg-gray-800 text-gray-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
            title="Limpiar bus"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

function HourGrid({ startHour, endHour, pixelsPerMinute }) {
  const hours = [];
  for (let h = startHour; h <= endHour; h++) {
    hours.push(h);
  }

  return (
    <div className="absolute inset-0 flex pointer-events-none">
      {hours.map(hour => (
        <div
          key={hour}
          className="h-full border-r border-gray-800/30 first:border-l-0"
          style={{ width: 60 * pixelsPerMinute }}
        />
      ))}
    </div>
  );
}

function timeToMinutes(time) {
  if (!time) return 0;
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
}

export default BusTrack;
