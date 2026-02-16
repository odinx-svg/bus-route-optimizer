import React from 'react';

/**
 * DragPreviewOverlay - Overlay flotante que muestra feedback de compatibilidad
 * Se posiciona cerca del cursor mientras se arrastra una ruta
 */
export function DragPreviewOverlay({ draggedRoute, targetRoute, compatibility, position }) {
  if (!compatibility) return null;

  const { compatible, buffer_minutes, travel_time, fallback } = compatibility;

  // Posicionar cerca del cursor pero evitar que salga de pantalla
  const style = position ? {
    left: position.x + 20,
    top: position.y - 20,
  } : {};

  return (
    <div 
      className={`
        fixed pointer-events-none z-50 p-3 rounded-lg shadow-2xl min-w-[180px]
        ${compatible 
          ? 'bg-green-900/95 border-green-500' 
          : 'bg-red-900/95 border-red-500'}
        border-2 backdrop-blur-sm
        transition-all duration-150 ease-out
      `}
      style={style}
    >
      {/* Header con estado */}
      <div className="flex items-center gap-2 text-white font-bold text-sm">
        <span className={`
          w-5 h-5 rounded-full flex items-center justify-center text-xs
          ${compatible ? 'bg-green-500' : 'bg-red-500'}
        `}>
          {compatible ? '✓' : '✗'}
        </span>
        <span>{compatible ? 'Compatible' : 'Incompatible'}</span>
        {fallback && (
          <span className="text-[10px] bg-yellow-500/30 text-yellow-200 px-1.5 py-0.5 rounded ml-auto">
            Est.
          </span>
        )}
      </div>

      {/* Detalles de tiempos */}
      <div className="text-xs text-white/80 mt-2 space-y-0.5">
        <div className="flex justify-between">
          <span className="text-white/60">Viaje OSRM:</span>
          <span className="font-mono">{travel_time?.toFixed(1) ?? '--'} min</span>
        </div>
        <div className="flex justify-between">
          <span className="text-white/60">Buffer:</span>
          <span className={`
            font-mono font-medium
            ${buffer_minutes >= 0 ? 'text-green-300' : 'text-red-300'}
          `}>
            {buffer_minutes > 0 ? '+' : ''}{buffer_minutes?.toFixed(1) ?? '--'} min
          </span>
        </div>
      </div>

      {/* Mensaje de advertencia si no es compatible */}
      {!compatible && (
        <div className="mt-2 text-xs text-red-200 bg-red-950/50 p-2 rounded border border-red-700/50">
          <div className="flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>Faltan {Math.abs(buffer_minutes).toFixed(0)} min</span>
          </div>
        </div>
      )}

      {/* Indicador si el buffer es justo */}
      {compatible && buffer_minutes < 5 && buffer_minutes >= 0 && (
        <div className="mt-2 text-xs text-yellow-200 bg-yellow-900/30 p-2 rounded border border-yellow-700/50">
          <div className="flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Buffer justo</span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * DragPreviewOverlaySkeleton - Estado de carga
 */
export function DragPreviewOverlaySkeleton({ position }) {
  const style = position ? {
    left: position.x + 20,
    top: position.y - 20,
  } : {};

  return (
    <div 
      className="fixed pointer-events-none z-50 p-3 rounded-lg bg-gray-800/95 border border-gray-600 min-w-[180px]"
      style={style}
    >
      <div className="flex items-center gap-2">
        <div className="w-5 h-5 rounded-full bg-gray-700 animate-pulse"></div>
        <div className="h-4 bg-gray-700 rounded w-24 animate-pulse"></div>
      </div>
      <div className="mt-2 space-y-1">
        <div className="h-3 bg-gray-700 rounded w-full animate-pulse"></div>
        <div className="h-3 bg-gray-700 rounded w-20 animate-pulse"></div>
      </div>
    </div>
  );
}

export default DragPreviewOverlay;
