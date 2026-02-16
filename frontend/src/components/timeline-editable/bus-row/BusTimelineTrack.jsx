import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { RouteBlock } from '../route-block/RouteBlock';
import { HourLine } from '../shared/HourLine';
import { generateHours, timeToMinutes } from '../shared/utils';

/**
 * BusTimelineTrack - Track del timeline que muestra las rutas posicionadas por hora
 * 
 * Cada RouteBlock se posiciona según:
 * - left: basado en start_time relativo al hourRange
 * - width: basado en duration_minutes
 */
export function BusTimelineTrack({ bus, hourRange, onRouteClick }) {
  const hours = generateHours({ start: hourRange[0], end: hourRange[1] });
  const totalMinutes = (hourRange[1] - hourRange[0]) * 60;

  // Hacer el track droppable
  const { setNodeRef, isOver } = useDroppable({
    id: `bus-track-${bus.busId}`,
    data: {
      type: 'bus',
      busId: bus.busId,
    },
  });

  /**
   * Calcula la posición left% para una ruta basada en su hora de inicio
   */
  const calculateLeft = (startTime) => {
    const minutes = timeToMinutes(startTime);
    const startMinutes = hourRange[0] * 60;
    return ((minutes - startMinutes) / totalMinutes) * 100;
  };

  /**
   * Calcula el width% para una ruta basada en su duración
   */
  const calculateWidth = (durationMinutes) => {
    return (durationMinutes / totalMinutes) * 100;
  };

  return (
    <div 
      ref={setNodeRef}
      className={`
        relative h-16 rounded-lg overflow-hidden flex-1 min-w-0
        ${isOver ? 'bg-indigo-500/10 ring-2 ring-indigo-500/50' : 'bg-gray-900/50'}
        transition-colors duration-200
      `}
    >
      {/* Líneas de hora (fondo) */}
      {hours.map(hour => (
        <HourLine 
          key={`line-${hour}`} 
          hour={hour} 
          hourRange={{ start: hourRange[0], end: hourRange[1] }} 
        />
      ))}

      {/* RouteBlocks posicionados por tiempo */}
      <div className="absolute inset-0">
        {bus.routes?.map((route, index) => {
          const left = calculateLeft(route.currentStartTime || route.start_time);
          const width = calculateWidth(route.duration_minutes);
          
          return (
            <RouteBlock
              key={route.route_id}
              route={{
                ...route,
                position: { left, width },
                hourRange,
              }}
              busId={bus.busId}
              onClick={onRouteClick}
            />
          );
        })}
      </div>

      {/* Mensaje si no hay rutas */}
      {(!bus.routes || bus.routes.length === 0) && (
        <div className="absolute inset-0 flex items-center justify-center text-gray-600 text-xs">
          <span>Sin rutas asignadas</span>
        </div>
      )}

      {/* Indicador de drop */}
      {isOver && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="px-3 py-1 bg-indigo-500 text-white text-xs rounded-full">
            Soltar aquí
          </div>
        </div>
      )}
    </div>
  );
}

export default BusTimelineTrack;
