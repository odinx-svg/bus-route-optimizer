import React from 'react';
import { useDraggable } from '@dnd-kit/core';

/**
 * RouteCard - Tarjeta operacional de ruta.
 */
export function RouteCard({ route, isDragging: externalIsDragging, compatibility, source, busId }) {
  const { attributes, listeners, setNodeRef, isDragging: internalIsDragging } = useDraggable({
    id: route.id,
    data: { type: 'route', route, source, busId },
  });

  const isDragging = externalIsDragging ?? internalIsDragging;

  const colors = {
    entry: {
      bg: 'bg-[#0f1722]',
      border: 'border-[#35506a]',
      shadow: 'shadow-[0_10px_26px_rgba(2,12,24,0.45)]',
      badge: 'bg-cyan-500/12 text-cyan-200 border border-cyan-500/30',
      accent: 'bg-cyan-400/80',
    },
    exit: {
      bg: 'bg-[#16140f]',
      border: 'border-[#5f4b2c]',
      shadow: 'shadow-[0_10px_26px_rgba(26,18,8,0.35)]',
      badge: 'bg-amber-500/12 text-amber-200 border border-amber-500/30',
      accent: 'bg-amber-300/85',
    },
  };

  const theme = colors[route?.type] || colors.entry;

  const calculateDuration = () => {
    if (!route.startTime || !route.endTime) return 0;
    const [startHour, startMin] = (route.startTime || '00:00').split(':').map(Number);
    const [endHour, endMin] = (route.endTime || '00:00').split(':').map(Number);
    const start = (startHour || 0) * 60 + (startMin || 0);
    const end = (endHour || 0) * 60 + (endMin || 0);
    return end >= start ? end - start : (24 * 60 - start) + end;
  };

  const duration = calculateDuration();

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={`
        relative w-44 min-h-[78px] rounded-md border px-2.5 py-2 select-none
        ${theme.bg} ${theme.border} ${theme.shadow}
        cursor-grab active:cursor-grabbing transition-all duration-150 ease-out
        ${isDragging ? 'opacity-95 scale-[1.01] border-cyan-400/55 shadow-[0_18px_42px_rgba(0,15,28,0.55)] z-50' : 'hover:border-slate-400/70'}
        ${compatibility === 'incompatible' ? 'ring-1 ring-red-500/60' : ''}
        ${compatibility === 'compatible' ? 'ring-1 ring-emerald-500/60' : ''}
      `}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${theme.accent}`} />

      <div className="flex items-center justify-between gap-2">
        <div className="text-[12px] font-semibold text-slate-100 truncate tracking-[0.03em] data-mono">
          {route?.code || 'SIN-CODIGO'}
        </div>
        <span className={`px-1.5 py-0.5 rounded-sm text-[9px] font-semibold uppercase tracking-[0.12em] data-mono ${theme.badge}`}>
          {route?.type === 'entry' ? 'ENT' : 'SAL'}
        </span>
      </div>

      <div className="mt-1.5 text-[11px] text-slate-300 truncate">
        {(route?.origin || '?')} {'->'} {(route?.destination || '?')}
      </div>

      <div className="mt-2 pt-1.5 border-t border-slate-600/30 flex items-center justify-between text-[10px] text-slate-400 data-mono tabular-nums">
        <span>{route?.startTime || '--:--'} | {route?.endTime || '--:--'}</span>
        <span className="text-slate-300">{duration}m</span>
      </div>
    </div>
  );
}

export function RouteCardSkeleton() {
  return (
    <div className="w-44 min-h-[78px] rounded-md border border-slate-700 bg-[#111822] animate-pulse">
      <div className="p-2 space-y-2">
        <div className="h-3 bg-slate-700 rounded w-24"></div>
        <div className="h-2 bg-slate-700 rounded w-32"></div>
        <div className="h-2 bg-slate-700 rounded w-20"></div>
      </div>
    </div>
  );
}

export function RouteCardCompact({ route, className = '' }) {
  return (
    <div className={`
      inline-flex items-center gap-2 px-2 py-1 rounded-sm border
      ${route.type === 'entry'
        ? 'bg-[#101a25] border-[#35506a] text-cyan-200'
        : 'bg-[#17130f] border-[#5f4b2c] text-amber-200'}
      ${className}
    `}>
      <span className="text-[10px] font-medium">{route.code}</span>
      <span className="text-[9px] text-slate-400">{route.startTime}</span>
    </div>
  );
}

export default RouteCard;
