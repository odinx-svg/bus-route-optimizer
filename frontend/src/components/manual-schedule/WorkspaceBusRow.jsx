import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { RouteCard } from './RouteCard';
import { RouteConnection } from './RouteConnection';
import { DropZoneIndicator } from './DropZoneIndicator';
import { getBusMinSeats } from '../../utils/capacity';

/**
 * AssignedRoute - Ruta asignada en la timeline del bus
 */
function AssignedRoute({ route, index, onRemove, busId }) {
  return (
    <div className="relative group">
      <RouteCard
        route={route}
        className="w-28 h-16"
        source="bus"
        busId={busId}
      />

      <button
        onClick={() => onRemove?.(route.id)}
        className="
          absolute -top-1 -right-1 w-4 h-4 rounded-sm border border-rose-500/40 bg-[#1b1f2a] text-rose-300
          opacity-0 group-hover:opacity-100 transition-opacity duration-150
          flex items-center justify-center hover:bg-rose-500/20 active:scale-90
        "
        title="Eliminar ruta"
      >
        <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 text-[9px] text-slate-500 tabular-nums data-mono">
        #{index + 1}
      </div>
    </div>
  );
}

/**
 * calcularCompatibilidadDetallada - Verifica compatibilidad con detalles
 */
function calcularCompatibilidadDetallada(routeA, routeB) {
  const [endHourA, endMinA] = routeA.endTime.split(':').map(Number);
  const [startHourB, startMinB] = routeB.startTime.split(':').map(Number);

  const endA = endHourA * 60 + endMinA;
  const startB = startHourB * 60 + startMinB;

  const bufferMinutes = startB - endA;
  const travelTime = 15;
  const compatible = bufferMinutes >= travelTime;

  return {
    compatible,
    buffer_minutes: bufferMinutes - travelTime,
    travel_time: travelTime
  };
}

/**
 * calcularTiempoTotal - Calcula el tiempo total de las rutas
 */
function calcularTiempoTotal(routes) {
  if (routes.length === 0) return 0;

  let totalMinutes = 0;
  routes.forEach(route => {
    const [startHour, startMin] = route.startTime.split(':').map(Number);
    const [endHour, endMin] = route.endTime.split(':').map(Number);
    const start = startHour * 60 + startMin;
    const end = endHour * 60 + endMin;
    totalMinutes += end >= start ? end - start : (24 * 60 - start) + end;
  });

  return totalMinutes;
}

/**
 * formatDuration - Formatea minutos a formato legible
 */
function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0) {
    return `${hours}h ${mins}m`;
  }
  return `${mins}m`;
}

/**
 * WorkspaceBusRow - Fila de bus en el workspace
 */
export function WorkspaceBusRow({ bus, routes = [], onDrop, onRemoveRoute, isActive }) {
  const { isOver, setNodeRef } = useDroppable({
    id: `bus-${bus.id}`,
    data: { busId: bus.id },
  });

  const tiempoTotal = calcularTiempoTotal(routes);
  const minSeatsNeeded = getBusMinSeats(routes);
  const isEmpty = routes.length === 0;

  return (
    <div
      ref={setNodeRef}
      className={`
        flex items-stretch gap-3 p-3 rounded-md transition-all duration-200 control-card
        ${isOver || isActive
          ? 'ring-1 ring-cyan-400/40 shadow-lg shadow-cyan-900/30'
          : 'hover:border-cyan-500/30'
        }
      `}
    >
      <div className="flex flex-col justify-center w-16 shrink-0">
        <div className="flex items-center justify-center w-14 h-14 rounded-md bg-[#0f1c2a] border border-[#2a4157]">
          <span className="text-lg font-bold text-white data-mono">{bus.id}</span>
        </div>
        {bus.type && (
          <span className="mt-1.5 text-[9px] text-center text-slate-500 uppercase tracking-[0.12em]">
            {bus.type}
          </span>
        )}
      </div>

      <div className={`
        flex-1 flex items-center gap-1 min-h-[88px] rounded-md p-3 relative
        ${isEmpty
          ? 'bg-[#0c141f] border-2 border-dashed border-[#2a4056]'
          : 'bg-[#09131d]'
        }
        ${isOver ? 'border-cyan-400 bg-cyan-500/10' : ''}
        transition-all duration-200
      `}>
        {isOver && (
          <div className="absolute inset-0 border-2 border-dashed border-cyan-400 rounded-md bg-cyan-500/10 flex items-center justify-center z-10">
            <span className="text-sm font-medium text-cyan-300 uppercase tracking-[0.1em] data-mono">Asignar ruta</span>
          </div>
        )}
        {isEmpty ? (
          <div className="flex items-center justify-center w-full text-slate-500 text-sm gap-2 data-mono">
            <svg className="w-4 h-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <span>Arrastra rutas aqui</span>
          </div>
        ) : (
          <>
            {routes.map((route, index) => {
              const nextRoute = routes[index + 1];
              const validation = nextRoute
                ? calcularCompatibilidadDetallada(route, nextRoute)
                : null;

              return (
                <React.Fragment key={route.id}>
                  <AssignedRoute
                    route={route}
                    index={index}
                    onRemove={onRemoveRoute}
                    busId={bus.id}
                  />
                  {nextRoute && (
                    <RouteConnection
                      routeA={route}
                      routeB={nextRoute}
                      validation={validation}
                    />
                  )}
                </React.Fragment>
              );
            })}
            <DropZoneIndicator
              isOver={isOver}
              canDrop={true}
              size="normal"
            />
          </>
        )}
      </div>

      <div className="flex flex-col justify-center w-20 shrink-0 text-right space-y-1 data-mono">
        <div className="text-xs text-slate-400">
          <span className="text-lg font-semibold text-white">{routes.length}</span>
          <span className="ml-1">rutas</span>
        </div>
        {minSeatsNeeded > 0 && (
          <div className="text-[10px] text-cyan-300 tabular-nums">
            Min {minSeatsNeeded} plazas
          </div>
        )}
        <div className="text-xs text-slate-400">
          <span className="text-sm font-medium text-cyan-300 tabular-nums">
            {formatDuration(tiempoTotal)}
          </span>
        </div>
        {routes.length > 0 && (
          <div className="text-[10px] text-slate-500">
            {routes[0]?.startTime} - {routes[routes.length - 1]?.endTime}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * WorkspaceBusRowSkeleton - Estado de carga
 */
export function WorkspaceBusRowSkeleton() {
  return (
    <div className="flex items-stretch gap-3 p-3 rounded-md bg-[#0f1b28]/70 animate-pulse">
      <div className="w-16 h-14 rounded-md bg-[#1a2b3d]"></div>
      <div className="flex-1 min-h-[88px] rounded-md bg-[#0a131d]"></div>
      <div className="w-20 h-14 rounded-md bg-[#1a2b3d]"></div>
    </div>
  );
}

export default WorkspaceBusRow;
