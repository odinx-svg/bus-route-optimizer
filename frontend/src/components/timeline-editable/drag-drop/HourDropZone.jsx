import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { RouteBlock } from '../shared/RouteBlock';
import { getTotalHours, formatHour } from '../shared/utils';

/**
 * Zona de drop para una hora específica en el timeline
 * Cada hora es una zona de drop independiente donde se pueden soltar rutas
 */
export function HourDropZone({ hour, busId, routesInHour, hourRange }) {
  const { isOver, canDrop, setNodeRef } = useDroppable({
    id: `drop-${busId}-${hour}`,
    data: { hour, busId, type: 'hour-zone' }
  });

  const totalHours = getTotalHours(hourRange);

  return (
    <div
      ref={setNodeRef}
      className={`
        absolute h-full border-r border-gray-700/30
        ${isOver && canDrop ? 'bg-green-500/20' : ''}
        ${isOver && !canDrop ? 'bg-red-500/20' : ''}
        transition-colors duration-150
      `}
      style={{
        left: `${((hour - hourRange.start) / totalHours) * 100}%`,
        width: `${(1 / totalHours) * 100}%`
      }}
    >
      {/* Indicador de hora en la esquina superior */}
      <div className="absolute top-0 left-1 text-[9px] text-gray-500 select-none">
        {formatHour(hour)}
      </div>

      {/* Mostrar rutas que caen en esta hora */}
      {routesInHour.map((route, index) => (
        <div
          key={`${route.route_id}-${index}`}
          className="absolute inset-x-0.5"
          style={{ top: `${16 + index * 14}px` }}
        >
          <RouteBlock route={route} />
        </div>
      ))}
    </div>
  );
}
