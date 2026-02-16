import React from 'react';

/**
 * Componente simple que muestra una ruta dentro de una zona de hora.
 * 
 * NOTA: Este es un componente de visualización simple. Para bloques de ruta
 * arrastrables con todas las funcionalidades, usar el componente RouteBlock
 * desde '../route-block/RouteBlock' que incluye:
 * - Drag & drop con @dnd-kit
 * - Botón de bloqueo
 * - Badge de compatibilidad
 * - Indicador de tiempo modificado
 */
export function RouteBlock({ route }) {
  if (!route) return null;

  // Determinar si es entrada o salida para el color
  const isEntry = route.type === 'entry';
  const bgColor = isEntry ? 'bg-indigo-500/80 hover:bg-indigo-400' : 'bg-amber-500/80 hover:bg-amber-400';

  return (
    <div
      className={`
        absolute inset-x-0 mx-0.5 ${bgColor}
        rounded text-[10px] text-white px-1 py-0.5 
        cursor-pointer transition-colors overflow-hidden
        flex items-center justify-between
      `}
      style={{
        top: '16px',
        bottom: '2px'
      }}
      title={`${route.route_code || route.route_id} (${route.currentStartTime || route.start_time} - ${route.currentEndTime || route.end_time})`}
    >
      <span className="truncate font-medium">{route.route_code || route.route_id}</span>
      <span className="text-[8px] opacity-80">
        {route.currentStartTime || route.start_time}
      </span>
    </div>
  );
}
