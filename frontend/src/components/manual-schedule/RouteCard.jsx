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
      bg: 'bg-gt-card',
      border: 'border-gt-info/30',
      shadow: 'shadow-gt-glow',
      badge: 'bg-gt-info/15 text-gt-info border border-gt-info/30',
      accent: 'bg-gt-info',
    },
    exit: {
      bg: 'bg-gt-card',
      border: 'border-gt-warning/30',
      shadow: 'shadow-[0_10px_26px_rgba(245,158,11,0.15)]',
      badge: 'bg-gt-warning/15 text-gt-warning border border-gt-warning/30',
      accent: 'bg-gt-warning',
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
        relative w-44 min-h-[78px] rounded-xl border px-2.5 py-2 select-none
        ${theme.bg} ${theme.border} ${theme.shadow}
        cursor-grab active:cursor-grabbing transition-all duration-150 ease-out
        ${isDragging ? 'opacity-95 scale-[1.01] border-gt-accent/50 shadow-gt-glow z-50' : 'hover:border-gt-text-muted/30'}
        ${compatibility === 'incompatible' ? 'ring-1 ring-gt-danger/60' : ''}
        ${compatibility === 'compatible' ? 'ring-1 ring-gt-success/60' : ''}
      `}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${theme.accent}`} />

      <div className="flex items-center justify-between gap-2">
        <div className="text-[12px] font-semibold text-gt-text truncate tracking-[0.03em] data-mono">
          {route?.code || 'SIN-CODIGO'}
        </div>
        <span className={`px-1.5 py-0.5 rounded-lg text-[9px] font-semibold uppercase tracking-[0.12em] data-mono ${theme.badge}`}>
          {route?.type === 'entry' ? 'ENT' : 'SAL'}
        </span>
      </div>

      <div className="mt-1.5 text-[11px] text-gt-text-muted truncate">
        {(route?.origin || '?')} {'->'} {(route?.destination || '?')}
      </div>

      <div className="mt-2 pt-1.5 border-t border-gt-border flex items-center justify-between text-[10px] text-gt-text-muted data-mono tabular-nums">
        <span>{route?.startTime || '--:--'} | {route?.endTime || '--:--'}</span>
        <span className="text-gt-text">{duration}m</span>
      </div>
    </div>
  );
}

export function RouteCardSkeleton() {
  return (
    <div className="w-44 min-h-[78px] rounded-xl border border-gt-border bg-gt-card animate-pulse">
      <div className="p-2 space-y-2">
        <div className="h-3 bg-gt-text-muted/20 rounded w-24"></div>
        <div className="h-2 bg-gt-text-muted/20 rounded w-32"></div>
        <div className="h-2 bg-gt-text-muted/20 rounded w-20"></div>
      </div>
    </div>
  );
}

export function RouteCardCompact({ route, className = '' }) {
  return (
    <div className={`
      inline-flex items-center gap-2 px-2 py-1 rounded-lg border
      ${route.type === 'entry'
        ? 'bg-gt-info/10 border-gt-info/30 text-gt-info'
        : 'bg-gt-warning/10 border-gt-warning/30 text-gt-warning'}
      ${className}
    `}>
      <span className="text-[10px] font-medium">{route.code}</span>
      <span className="text-[9px] text-gt-text-muted">{route.startTime}</span>
    </div>
  );
}

export default RouteCard;
