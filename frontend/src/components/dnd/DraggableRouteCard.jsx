/**
 * DraggableRouteCard - Tarjeta de ruta arrastrable desde el palette
 * 
 * Uso: Arrastrar desde la lista de rutas disponibles hacia los buses
 */
import React from 'react';
import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { 
  MapPin, 
  Clock, 
  Users, 
  ArrowUpRight, 
  ArrowDownRight,
  GripVertical 
} from 'lucide-react';

export function DraggableRouteCard({ 
  route, 
  disabled = false,
  onClick,
  className = '',
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    isDragging,
  } = useDraggable({
    id: `route-${route.id}`,
    data: { 
      type: 'route',
      route,
      source: 'palette'
    },
    disabled,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
    cursor: disabled ? 'not-allowed' : 'grab',
  };

  const isEntry = route.type === 'entry' || route.route_type === 'entry';
  const routeColor = isEntry ? 'indigo' : 'amber';

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      onClick={onClick}
      className={`
        group relative flex flex-col gap-2 p-3 rounded-[12px] border
        transition-all duration-200 select-none
        ${isDragging 
          ? 'bg-zinc-800/80 border-indigo-500/50 shadow-xl scale-105 z-50' 
          : 'bg-zinc-900/50 border-white/[0.06] hover:bg-zinc-800/60 hover:border-white/[0.1]'
        }
        ${disabled ? 'opacity-50 pointer-events-none' : ''}
        ${className}
      `}
    >
      {/* Drag handle indicator */}
      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <GripVertical className="w-4 h-4 text-zinc-500" />
      </div>

      {/* Header: Route ID and Type */}
      <div className="flex items-center gap-2">
        <div 
          className={`
            w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0
            bg-${routeColor}-500/10 text-${routeColor}-400
          `}
        >
          {isEntry ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
        </div>
        <span className="font-medium text-[13px] text-zinc-200 truncate">
          {route.id}
        </span>
        <span 
          className={`
            ml-auto text-[9px] px-1.5 py-0.5 rounded font-medium
            bg-${routeColor}-500/10 text-${routeColor}-400
          `}
        >
          {isEntry ? 'Entrada' : 'Salida'}
        </span>
      </div>

      {/* Route details */}
      <div className="space-y-1.5">
        {/* School/Destination */}
        <div className="flex items-center gap-1.5 text-zinc-400">
          <MapPin className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="text-[11px] truncate">
            {route.school_name || route.destination || 'Sin destino'}
          </span>
        </div>

        {/* Time range */}
        <div className="flex items-center gap-1.5 text-zinc-500">
          <Clock className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="text-[11px] tabular-nums">
            {route.start_time || route.time_window_start} - {route.end_time || route.time_window_end}
          </span>
        </div>

        {/* Passengers count (if available) */}
        {route.passengers_count !== undefined && (
          <div className="flex items-center gap-1.5 text-zinc-500">
            <Users className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="text-[11px]">
              {route.passengers_count} pasajeros
            </span>
          </div>
        )}
      </div>

      {/* Duration badge */}
      {route.duration_minutes && (
        <div className="mt-1 pt-2 border-t border-white/[0.04]">
          <span className="text-[10px] text-zinc-500">
            Duración: {route.duration_minutes} min
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * DraggableRouteCard.Preview - Versión compacta para DragOverlay
 */
export function DraggableRouteCardPreview({ route }) {
  const isEntry = route.type === 'entry' || route.route_type === 'entry';
  const routeColor = isEntry ? 'indigo' : 'amber';

  return (
    <div 
      className={`
        flex items-center gap-3 p-3 rounded-[10px] border shadow-2xl
        bg-zinc-800 border-${routeColor}-500/30 scale-105
        pointer-events-none
      `}
    >
      <div 
        className={`
          w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0
          bg-${routeColor}-500/20 text-${routeColor}-400
        `}
      >
        {isEntry ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
      </div>
      <div className="flex-1 min-w-0">
        <span className="font-medium text-[13px] text-white block truncate">
          {route.id}
        </span>
        <span className="text-[11px] text-zinc-400 block truncate">
          {route.school_name || route.destination}
        </span>
      </div>
    </div>
  );
}

export default DraggableRouteCard;
