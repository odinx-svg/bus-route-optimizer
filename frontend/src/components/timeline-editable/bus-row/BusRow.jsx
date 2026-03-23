import React, { useState } from 'react';
import { BusTimelineTrack } from './BusTimelineTrack';
import { BusLabel } from '../shared/BusLabel';
import { BusControls } from '../shared/BusControls';
import { DeadheadGap } from './DeadheadGap';
import ConfirmDialog from '../../ui/ConfirmDialog';

/**
 * BusRow - Fila completa de un bus en el timeline
 * 
 * Contiene:
 * - Label del bus (ID y conteo de rutas)
 * - Track del timeline con RouteBlocks posicionados
 * - DeadheadGaps entre rutas consecutivas
 * - Controles (bloquear todo, limpiar)
 */
export function BusRow({ 
  bus, 
  hourRange, 
  isActive,
  onLockAllRoutes, 
  onClearBus,
  onRouteClick 
}) {
  const [allLocked, setAllLocked] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const handleLockAll = () => {
    const newLockedState = !allLocked;
    setAllLocked(newLockedState);
    onLockAllRoutes?.(bus.busId, newLockedState);
  };

  const handleClear = () => {
    setShowClearConfirm(true);
  };

  const lockedCount = bus.routes.filter((route) => route.isLocked).length;

  return (
    <div 
      className={`
        flex items-center gap-3 py-2 px-2 rounded-lg transition-colors
        ${isActive ? 'bg-indigo-500/10 ring-1 ring-indigo-500/30' : 'hover:bg-gray-800/30'}
      `}
    >
      {/* Label del bus */}
      <BusLabel 
        busId={bus.busId}
        busName={bus.busName}
        routeCount={bus.routes?.length || 0} 
        color={bus.color}
        isCollapsed={bus.isCollapsed}
      />

      {/* Track del timeline con RouteBlocks */}
      {!bus.isCollapsed && (
        <BusTimelineTrack 
          bus={bus} 
          hourRange={hourRange}
          onRouteClick={onRouteClick}
        />
      )}

      {/* Controles del bus */}
      <BusControls
        onLockAll={handleLockAll}
        onClear={handleClear}
        allLocked={allLocked}
        routeCount={bus.routes?.length || 0}
      />
      <ConfirmDialog
        open={showClearConfirm}
        title={`Vaciar ${bus.busName || bus.busId}`}
        description={lockedCount > 0
          ? `Se eliminaran las rutas desbloqueadas de ${bus.busName || bus.busId}. ${lockedCount} bloqueadas se mantendran.`
          : `Se eliminaran todas las rutas de ${bus.busName || bus.busId}.`}
        tone="warning"
        confirmLabel="Vaciar unidad"
        cancelLabel="Cancelar"
        onConfirm={() => {
          setShowClearConfirm(false);
          onClearBus?.(bus.busId);
        }}
        onCancel={() => setShowClearConfirm(false)}
      />
    </div>
  );
}

export default BusRow;
