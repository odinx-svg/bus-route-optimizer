/**
 * BusRow - Fila de bus que actúa como zona de drop
 * 
 * Permite:
 * - Arrastrar rutas desde el palette al bus
 * - Reordenar rutas dentro del bus
 * - Indicadores visuales de drop válido/inválido
 */
import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { 
  SortableContext, 
  verticalListSortingStrategy,
  useSortable 
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { 
  Bus, 
  AlertCircle, 
  CheckCircle2,
  Clock,
  Route
} from 'lucide-react';

const BUS_COLORS = [
  '#6366F1', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899',
  '#06B6D4', '#F97316', '#84CC16', '#14B8A6', '#EF4444',
  '#818CF8', '#22D3EE', '#A3E635', '#FB923C', '#E879F9',
];

const getBusColor = (id) => {
  const num = parseInt(id.replace(/\D/g, ''), 10) || 0;
  return BUS_COLORS[num % BUS_COLORS.length];
};

/**
 * Componente para cada ruta asignada dentro del bus (sortable)
 */
function AssignedRouteBlock({ route, busId, onRemove }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: `${busId}-route-${route.id}`,
    data: {
      type: 'assigned-route',
      route,
      busId,
    },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const isEntry = route.type === 'entry' || route.route_type === 'entry';

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`
        group flex items-center gap-2 px-3 py-2 rounded-lg
        bg-white/[0.03] border border-white/[0.06]
        hover:bg-white/[0.05] hover:border-white/[0.1]
        transition-all duration-150 cursor-grab active:cursor-grabbing
        ${isDragging ? 'ring-2 ring-indigo-500/50' : ''}
      `}
    >
      {/* Route indicator */}
      <div 
        className={`
          w-2 h-2 rounded-full flex-shrink-0
          ${isEntry ? 'bg-indigo-400' : 'bg-amber-400'}
        `}
      />
      
      {/* Route info */}
      <span className="text-[11px] text-zinc-300 truncate max-w-[120px]">
        {route.id}
      </span>
      
      <span className="text-[10px] text-zinc-500 tabular-nums ml-auto">
        {route.start_time || route.time_window_start}
      </span>

      {/* Remove button (visible on hover) */}
      {onRemove && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove(route.id);
          }}
          className="
            opacity-0 group-hover:opacity-100
            p-1 rounded hover:bg-red-500/10 hover:text-red-400
            transition-all duration-150
          "
        >
          <AlertCircle className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}

/**
 * Indicador visual de zona de drop
 */
function DropZoneIndicator({ isOver, isValid, message }) {
  return (
    <div 
      className={`
        flex items-center justify-center gap-2 py-3 rounded-lg
        border-2 border-dashed transition-all duration-200
        ${isOver 
          ? isValid 
            ? 'border-emerald-500/50 bg-emerald-500/5' 
            : 'border-red-500/50 bg-red-500/5'
          : 'border-white/[0.04] bg-transparent'
        }
      `}
    >
      {isOver ? (
        <>
          {isValid ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : (
            <AlertCircle className="w-4 h-4 text-red-400" />
          )}
          <span className={`text-[11px] ${isValid ? 'text-emerald-400' : 'text-red-400'}`}>
            {message || (isValid ? 'Soltar aquí' : 'No válido')}
          </span>
        </>
      ) : (
        <>
          <Route className="w-4 h-4 text-zinc-600" />
          <span className="text-[11px] text-zinc-600">
            Arrastra rutas aquí
          </span>
        </>
      )}
    </div>
  );
}

export function BusRow({ 
  bus, 
  assignedRoutes = [],
  onRouteRemove,
  onRouteReorder,
  validationStatus = null, // { isValid: boolean, message: string }
  className = '',
}) {
  const busColor = getBusColor(bus.id);
  
  const { setNodeRef, isOver } = useDroppable({
    id: `bus-${bus.id}`,
    data: { 
      type: 'bus',
      busId: bus.id,
      bus,
    },
  });

  const routeIds = assignedRoutes.map(route => `${bus.id}-route-${route.id}`);

  // Calcular estadísticas
  const totalDuration = assignedRoutes.reduce((acc, r) => acc + (r.duration_minutes || 0), 0);
  const entryCount = assignedRoutes.filter(r => 
    (r.type === 'entry' || r.route_type === 'entry')
  ).length;
  const exitCount = assignedRoutes.length - entryCount;

  return (
    <div
      className={`
        group relative flex flex-col gap-3 p-4 rounded-[14px] border
        transition-all duration-200
        ${isOver 
          ? validationStatus?.isValid !== false
            ? 'bg-emerald-500/[0.03] border-emerald-500/30 ring-1 ring-emerald-500/20' 
            : 'bg-red-500/[0.03] border-red-500/30 ring-1 ring-red-500/20'
          : 'bg-zinc-900/30 border-white/[0.04] hover:border-white/[0.08]'
        }
        ${className}
      `}
    >
      {/* Header del Bus */}
      <div className="flex items-center gap-3">
        {/* Bus icon with color indicator */}
        <div 
          className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: `${busColor}15` }}
        >
          <Bus 
            className="w-5 h-5" 
            style={{ color: busColor }}
          />
        </div>

        {/* Bus info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-[14px] text-white">
              {bus.id}
            </h3>
            {bus.capacity && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500">
                Cap: {bus.capacity}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5">
            <span className="text-[11px] text-zinc-500">
              {assignedRoutes.length} rutas
            </span>
            {totalDuration > 0 && (
              <span className="text-[11px] text-zinc-500 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {totalDuration} min
              </span>
            )}
          </div>
        </div>

        {/* Type counts */}
        <div className="flex items-center gap-1.5">
          {entryCount > 0 && (
            <span className="text-[10px] px-2 py-1 rounded-md bg-indigo-500/10 text-indigo-400">
              {entryCount} E
            </span>
          )}
          {exitCount > 0 && (
            <span className="text-[10px] px-2 py-1 rounded-md bg-amber-500/10 text-amber-400">
              {exitCount} X
            </span>
          )}
        </div>
      </div>

      {/* Rutas asignadas */}
      <div 
        ref={setNodeRef}
        className="min-h-[80px]"
      >
        {assignedRoutes.length > 0 ? (
          <SortableContext 
            items={routeIds} 
            strategy={verticalListSortingStrategy}
          >
            <div className="flex flex-wrap gap-2">
              {assignedRoutes.map((route) => (
                <AssignedRouteBlock
                  key={`${bus.id}-route-${route.id}`}
                  route={route}
                  busId={bus.id}
                  onRemove={onRouteRemove}
                />
              ))}
            </div>
          </SortableContext>
        ) : (
          <DropZoneIndicator 
            isOver={isOver} 
            isValid={validationStatus?.isValid !== false}
            message={validationStatus?.message}
          />
        )}
      </div>

      {/* Footer con tiempo total */}
      {assignedRoutes.length > 0 && (
        <div className="flex items-center justify-between pt-2 border-t border-white/[0.04]">
          <span className="text-[10px] text-zinc-600">
            Tiempo total estimado
          </span>
          <span className="text-[11px] font-medium text-zinc-400 tabular-nums">
            {Math.floor(totalDuration / 60)}h {totalDuration % 60}m
          </span>
        </div>
      )}
    </div>
  );
}

export default BusRow;
