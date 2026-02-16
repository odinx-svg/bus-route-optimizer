/**
 * TimelineBusRow - Timeline profesional y minimalista
 * 
 * Diseno tecnico: lineas, puntos, numeros. Sin dibujos infantiles.
 * El autobus es un pequeno indicador verde que viaja por la linea temporal.
 */

import React, { useMemo } from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { 
  Clock, 
  AlertCircle, 
  ZoomIn, 
  ZoomOut,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  MoreHorizontal,
  Timer
} from 'lucide-react';
import { notifications } from '../../services/notifications';

// ============================================================================
// CONFIGURACIIN
// ============================================================================

const CONFIG = {
  MIN_ZOOM: 40,
  MAX_ZOOM: 800,
  DEFAULT_ZOOM: 140,
  ROW_HEIGHT: 74,
  BUS_SIZE: 14,
  GAP_THRESHOLD: 15, // minutos
  GAP_WIDTH: 16, // px
};

// ============================================================================
// HELPERS
// ============================================================================

const timeToMinutes = (time) => {
  if (!time) return 0;
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
};

const minutesToTime = (minutes) => {
  const h = Math.floor(minutes / 60);
  const m = Math.floor(minutes % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

const durationMin = (start, end) => {
  if (!start || !end) return 0;
  return timeToMinutes(end) - timeToMinutes(start);
};

const getPositioningMinutes = (route) => {
  const raw = (
    route?.positioningMinutes ??
    route?.positioning_minutes ??
    route?.deadheadMinutes ??
    route?.deadhead_minutes ??
    route?.deadhead ??
    route?.rawRoute?.positioning_minutes ??
    route?.rawRoute?.deadhead_minutes ??
    route?.rawRoute?.deadhead ??
    0
  );
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? Math.max(0, Math.round(parsed)) : 0;
};

const getRouteCapacityNeeded = (route) => {
  const direct = Number(
    route?.capacityNeeded ??
    route?.capacity_needed ??
    route?.rawRoute?.capacity_needed ??
    route?.rawRoute?.capacityNeeded ??
    0
  );
  if (Number.isFinite(direct) && direct > 0) return Math.round(direct);
  const stops = Array.isArray(route?.stops) ? route.stops : [];
  const byStops = stops.reduce((peak, stop) => {
    const passengers = Number(stop?.passengers ?? 0);
    const safePassengers = Number.isFinite(passengers) && passengers > 0 ? Math.round(passengers) : 0;
    return safePassengers > peak ? safePassengers : peak;
  }, 0);
  if (byStops > 0) return byStops;

  const vehicleFallback = Number(
    route?.vehicle_capacity_max ??
    route?.vehicleCapacityMax ??
    route?.rawRoute?.vehicle_capacity_max ??
    route?.rawRoute?.vehicleCapacityMax ??
    0
  );
  if (Number.isFinite(vehicleFallback) && vehicleFallback > 0) return Math.round(vehicleFallback);
  return 0;
};

const getRouteCapacityRangeLabel = (route) => {
  const directRange = String(
    route?.vehicle_capacity_range ??
    route?.vehicleCapacityRange ??
    route?.rawRoute?.vehicle_capacity_range ??
    route?.rawRoute?.vehicleCapacityRange ??
    ''
  ).trim();
  if (directRange) return `${directRange}P`;

  const low = Number(
    route?.vehicle_capacity_min ??
    route?.vehicleCapacityMin ??
    route?.rawRoute?.vehicle_capacity_min ??
    route?.rawRoute?.vehicleCapacityMin ??
    0
  );
  const high = Number(
    route?.vehicle_capacity_max ??
    route?.vehicleCapacityMax ??
    route?.rawRoute?.vehicle_capacity_max ??
    route?.rawRoute?.vehicleCapacityMax ??
    0
  );
  if (Number.isFinite(low) && Number.isFinite(high) && low > 0 && high > 0) {
    const minVal = Math.min(low, high);
    const maxVal = Math.max(low, high);
    return `${minVal}-${maxVal}P`;
  }
  return '';
};

const formatHour = (h) => `${String(h).padStart(2, '0')}:00`;

// ============================================================================
// COMPRESIIN DE TIMELINE
// ============================================================================

export function calculateTimelineCompression(allRoutes, minHour, maxHour) {
  if (!allRoutes || allRoutes.length === 0) {
    return { segments: [], compressedWidth: (maxHour - minHour) * 60 };
  }

  const minTime = minHour * 60;
  const maxTime = maxHour * 60;
  
  // Obtener rangos de tiempo ocupados
  const timeRanges = allRoutes.map(r => ({
    start: timeToMinutes(r.startTime),
    end: timeToMinutes(r.endTime),
  })).sort((a, b) => a.start - b.start);

  // Merge rangos superpuestos
  const mergedRanges = [];
  for (const range of timeRanges) {
    if (mergedRanges.length === 0) {
      mergedRanges.push({ ...range });
    } else {
      const last = mergedRanges[mergedRanges.length - 1];
      if (range.start <= last.end + 2) {
        last.end = Math.max(last.end, range.end);
      } else {
        mergedRanges.push({ ...range });
      }
    }
  }

  const segments = [];
  let currentPos = 0;
  let lastEnd = minTime;

  for (const range of mergedRanges) {
    // Gap antes del rango
    if (range.start > lastEnd) {
      const gapSize = range.start - lastEnd;
      if (gapSize > CONFIG.GAP_THRESHOLD) {
        segments.push({
          type: 'gap',
          realStart: lastEnd,
          realEnd: range.start,
          start: currentPos,
          end: currentPos + CONFIG.GAP_WIDTH,
          width: CONFIG.GAP_WIDTH,
          duration: gapSize
        });
        currentPos += CONFIG.GAP_WIDTH;
      } else {
        const w = gapSize * 0.5;
        segments.push({
          type: 'normal',
          realStart: lastEnd,
          realEnd: range.start,
          start: currentPos,
          end: currentPos + w,
          width: w
        });
        currentPos += w;
      }
    }

    // Rango activo (expandido para mejor visibilidad)
    const activeWidth = (range.end - range.start) * 1.2;
    segments.push({
      type: 'active',
      realStart: range.start,
      realEnd: range.end,
      start: currentPos,
      end: currentPos + activeWidth,
      width: activeWidth
    });
    currentPos += activeWidth;
    lastEnd = range.end;
  }

  // Gap final
  if (lastEnd < maxTime) {
    const gapSize = maxTime - lastEnd;
    if (gapSize > CONFIG.GAP_THRESHOLD) {
      segments.push({
        type: 'gap',
        realStart: lastEnd,
        realEnd: maxTime,
        start: currentPos,
        end: currentPos + CONFIG.GAP_WIDTH,
        width: CONFIG.GAP_WIDTH,
        duration: gapSize
      });
      currentPos += CONFIG.GAP_WIDTH;
    }
  }

  return { segments, compressedWidth: currentPos };
}

function timeToCompressedPx(time, segments, pixelsPerHour) {
  const minutes = timeToMinutes(time);
  
  // Buscar el segmento correspondiente
  for (const seg of segments) {
    if (minutes >= seg.realStart && minutes <= seg.realEnd) {
      const ratio = (minutes - seg.realStart) / (seg.realEnd - seg.realStart);
      const pos = seg.start + (ratio * seg.width);
      return (pos / 60) * pixelsPerHour;
    }
  }
  
  // Si no se encuentra (tiempo fuera de rango), calcular extrapolacion
  if (segments.length > 0) {
    const firstSeg = segments[0];
    const lastSeg = segments[segments.length - 1];
    
    // Si es antes del primer segmento
    if (minutes < firstSeg.realStart) {
      const ratio = (minutes - firstSeg.realStart) / (firstSeg.realEnd - firstSeg.realStart);
      const pos = firstSeg.start + (ratio * firstSeg.width);
      return (pos / 60) * pixelsPerHour;
    }
    
    // Si es despues del ultimo segmento
    if (minutes > lastSeg.realEnd) {
      const ratio = (minutes - lastSeg.realStart) / (lastSeg.realEnd - lastSeg.realStart);
      const pos = lastSeg.start + (ratio * lastSeg.width);
      return (pos / 60) * pixelsPerHour;
    }
  }
  
  return 0;
}

// ============================================================================
// CONTROLES
// ============================================================================

export function TimelineControls({ zoom, onZoomChange, onReset }) {
  return (
    <div className="flex items-center justify-between px-4 py-2 bg-[#09111a] border-b border-[#2a4056] data-mono">
      <div className="flex items-center gap-3">
        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.16em]">Zoom</span>
        <div className="flex items-center bg-[#101a26] rounded-md border border-[#2b4056]">
          <button onClick={() => onZoomChange(Math.max(CONFIG.MIN_ZOOM, zoom - 60))}
            className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800/70 rounded-l-md transition-all">
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="px-3 py-1.5 text-[11px] font-semibold text-slate-200 tabular-nums border-x border-slate-700/60 min-w-[56px] text-center">
            {zoom}
          </span>
          <button onClick={() => onZoomChange(Math.min(CONFIG.MAX_ZOOM, zoom + 60))}
            className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800/70 rounded-r-md transition-all">
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <button onClick={onReset}
        className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400 hover:text-cyan-200 transition-colors px-3 py-1.5 hover:bg-[#152332] rounded-md">
        Reset
      </button>
    </div>
  );
}

// ============================================================================
// ESCALA DE TIEMPO
// ============================================================================

export function TimelineScale({ minHour, maxHour, pixelsPerHour, segments, leftOffset = 0 }) {
  // Keep axis mapping aligned with route positioning.
  const timeToPx = (timeStr) => {
    if (segments && segments.length > 0) {
      return timeToCompressedPx(timeStr, segments, pixelsPerHour);
    }
    const minutes = timeToMinutes(timeStr) - minHour * 60;
    return (minutes / 60) * pixelsPerHour;
  };

  const totalWidth = segments && segments.length > 0
    ? segments[segments.length - 1].end * (pixelsPerHour / 60)
    : (maxHour - minHour) * pixelsPerHour;
  const renderedWidth = totalWidth + leftOffset;

  const marks = [];

  let minuteInterval = 60;
  let labelInterval = 60;

  if (pixelsPerHour >= 600) {
    minuteInterval = 5;
    labelInterval = 15;
  } else if (pixelsPerHour >= 400) {
    minuteInterval = 5;
    labelInterval = 30;
  } else if (pixelsPerHour >= 200) {
    minuteInterval = 15;
    labelInterval = 60;
  } else if (pixelsPerHour >= 100) {
    minuteInterval = 30;
    labelInterval = 60;
  } else if (pixelsPerHour >= 60) {
    minuteInterval = 30;
    labelInterval = 120;
  }

  const getSegmentForMinute = (minute) => {
    if (!segments || segments.length === 0) return null;
    return segments.find(seg => minute >= seg.realStart && minute <= seg.realEnd) || null;
  };

  const startMin = minHour * 60;
  const endMin = maxHour * 60;
  const rawMarks = [];

  for (let m = startMin; m <= endMin; m += minuteInterval) {
    const h = Math.floor(m / 60);
    const min = m % 60;
    const timeStr = `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
    const pos = timeToPx(timeStr) + leftOffset;

    const isHour = min === 0;
    const isHalfHour = min === 30;
    const isQuarter = min === 15 || min === 45;

    const segment = getSegmentForMinute(m);
    const isGapSegment = segment?.type === 'gap';

    // In collapsed gaps, keep only boundary ticks to avoid stacked labels.
    if (isGapSegment) {
      const isGapBoundary = m === segment.realStart || m === segment.realEnd;
      if (!isGapBoundary) {
        continue;
      }
    }

    const minutesSinceStart = m - startMin;
    let showLabel = false;

    if (!isGapSegment && minutesSinceStart % labelInterval === 0) {
      showLabel = true;
    }
    if (isGapSegment && isHour) {
      showLabel = true;
    }
    if (m === startMin || m === endMin) {
      showLabel = true;
    }

    rawMarks.push({
      h,
      min,
      pos,
      isHour,
      isHalfHour,
      isQuarter,
      showLabel,
      label: pixelsPerHour >= 150
        ? `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`
        : formatHour(h)
    });
  }

  // Pixel-based collision and dedup filter for label readability.
  const hasCompression = !!(segments && segments.some(seg => seg.type === 'gap'));
  const minLabelSpacingPx =
    pixelsPerHour >= 500 ? 20 :
    pixelsPerHour >= 300 ? 28 :
    pixelsPerHour >= 180 ? 36 :
    pixelsPerHour >= 120 ? 44 : 54;
  const duplicateLabelMinSpacingPx = hasCompression ? 42 : 28;

  let lastLabelPos = -Infinity;
  const lastPosByLabel = new Map();

  rawMarks.forEach((mark) => {
    if (!mark.showLabel) return;

    const minute = mark.h * 60 + mark.min;
    const isBoundary = minute === startMin || minute === endMin;

    if (!isBoundary && Math.abs(mark.pos - lastLabelPos) < minLabelSpacingPx) {
      mark.showLabel = false;
      return;
    }

    const prevSameLabelPos = lastPosByLabel.get(mark.label);
    if (!isBoundary && prevSameLabelPos !== undefined && Math.abs(mark.pos - prevSameLabelPos) < duplicateLabelMinSpacingPx) {
      mark.showLabel = false;
      return;
    }

    lastLabelPos = mark.pos;
    lastPosByLabel.set(mark.label, mark.pos);
  });

  marks.push(...rawMarks);

  return (
    <div className="relative h-9 bg-[#0a0f16] select-none border-b border-[#2a4056]/70" style={{ width: renderedWidth }}>
      {/* Base line */}
      <div className="absolute bottom-3 right-0 h-[2px] bg-cyan-900/50" style={{ left: leftOffset }} />
      {leftOffset > 0 && (
        <div className="absolute top-0 bottom-0 w-px bg-slate-700/50" style={{ left: leftOffset }} />
      )}

      {/* Visual gaps (compressed mode only) */}
      {segments && segments.map((seg, idx) => {
        if (seg.type !== 'gap') return null;
        const left = seg.start * (pixelsPerHour / 60) + leftOffset;
        const width = seg.width * (pixelsPerHour / 60);
        const hours = Math.floor(seg.duration / 60);
        const label = hours > 0 ? `+${hours}h` : `+${Math.round(seg.duration)}m`;
        return (
          <div key={`gap-${idx}`} className="absolute bottom-0 h-full flex items-end justify-center"
            style={{ left, width: Math.max(width, 12) }}>
            <span className="text-[7px] text-gray-600 font-mono leading-none">{label}</span>
            <div className="absolute left-1/2 bottom-0 w-px h-1 bg-gray-700 -translate-x-1/2" />
          </div>
        );
      })}

      {/* Time marks */}
      {marks.map(m => {
        let markHeight = 'h-1';
        let markColor = 'bg-gray-700';

        if (m.isHour) {
          markHeight = 'h-3';
          markColor = 'bg-gray-300';
        } else if (m.isHalfHour) {
          markHeight = 'h-2';
          markColor = 'bg-gray-500';
        } else if (m.isQuarter) {
          markHeight = 'h-1.5';
          markColor = 'bg-gray-600';
        }

        const markMinute = (m.h * 60) + m.min;
        const isStartBoundary = markMinute === startMin;
        const isEndBoundary = markMinute === endMin;
        const labelStyle = isStartBoundary
          ? { left: 0, transform: 'translateX(0)' }
          : isEndBoundary
            ? { left: 0, transform: 'translateX(-100%)' }
            : { left: 0, transform: 'translateX(-50%)' };

        return (
          <div key={`${m.h}-${m.min}`} className="absolute bottom-0 h-full" style={{ left: m.pos }}>
            <div className={`absolute bottom-0.5 w-[2px] ${markHeight} ${markColor}`} />
            {m.showLabel && (
              <span
                className={`absolute bottom-2 font-medium text-gray-300 tabular-nums ${m.isHour ? 'text-[10px]' : 'text-[9px]'}`}
                style={labelStyle}
              >
                {m.label}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
// PUNTO DE LUZ ANIMADO
// ============================================================================

function AnimatedLight({ routes, selectedRouteId, minHour, pixelsPerHour, segments, hasError, isValidating }) {
  const [position, setPosition] = React.useState(0);
  const [currentRouteIndex, setCurrentRouteIndex] = React.useState(0);
  const animationRef = React.useRef();
  const startTimeRef = React.useRef(Date.now());

  // Configuracion de animacion
  const SPEED_MS_PER_PIXEL = isValidating ? 8 : 20; // Mas rapido durante validacion
  const LOOP_PAUSE_MS = isValidating ? 100 : 500; // Menos pausa durante validacion

  React.useEffect(() => {
    const animate = () => {
      if (!routes || routes.length === 0) return;

      const now = Date.now();
      const elapsed = now - startTimeRef.current;

      // Determinar que rutas animar
      let routesToAnimate = routes;
      let routeIndexOffset = 0;

      if (selectedRouteId) {
        const selectedIdx = routes.findIndex(r => r.id === selectedRouteId);
        if (selectedIdx !== -1) {
          routesToAnimate = [routes[selectedIdx]];
          routeIndexOffset = selectedIdx;
        }
      }

      if (routesToAnimate.length === 0) return;

      // Calcular posicion total recorrida
      let totalDistance = 0;
      const routePositions = routesToAnimate.map(route => {
        let startX, endX, width;
        if (segments && segments.length > 0) {
          startX = timeToCompressedPx(route.startTime, segments, pixelsPerHour);
          endX = timeToCompressedPx(route.endTime, segments, pixelsPerHour);
        } else {
          const startMin = timeToMinutes(route.startTime) - minHour * 60;
          const endMin = timeToMinutes(route.endTime) - minHour * 60;
          startX = (startMin / 60) * pixelsPerHour;
          endX = (endMin / 60) * pixelsPerHour;
        }
        width = Math.max(endX - startX, 4);
        const pos = { startX, endX, width };
        totalDistance += width + LOOP_PAUSE_MS / SPEED_MS_PER_PIXEL;
        return pos;
      });

      // Calcular posicion en el ciclo actual
      const cycleLength = totalDistance;
      const currentPos = (elapsed * SPEED_MS_PER_PIXEL / 1000) % cycleLength;

      // Encontrar en que ruta estamos
      let accumulated = 0;
      let found = false;
      for (let i = 0; i < routePositions.length; i++) {
        const { startX, width } = routePositions[i];
        const segmentLength = width + LOOP_PAUSE_MS / SPEED_MS_PER_PIXEL;
        
        if (currentPos >= accumulated && currentPos < accumulated + segmentLength) {
          const posInSegment = currentPos - accumulated;
          if (posInSegment < width) {
            // Dentro de la ruta
            setPosition(startX + posInSegment);
            setCurrentRouteIndex(i + routeIndexOffset);
          }
          // Si esta en la pausa, se queda al final
          found = true;
          break;
        }
        accumulated += segmentLength;
      }

      if (!found) {
        // Al final, reiniciar ciclo
        startTimeRef.current = now;
      }

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationRef.current);
  }, [routes, selectedRouteId, minHour, pixelsPerHour, segments, isValidating, SPEED_MS_PER_PIXEL, LOOP_PAUSE_MS]);

  // Determinar si estamos en la ruta seleccionada
  const isOnSelectedRoute = selectedRouteId 
    ? routes[currentRouteIndex]?.id === selectedRouteId 
    : true;

  // Color de la luz segun estado
  const lightColor = hasError ? 'bg-red-400' : 
                     isValidating ? 'bg-cyan-300' :
                     isOnSelectedRoute ? 'bg-emerald-300' : 'bg-emerald-500';
  
  const glowColor = hasError ? 'rgba(239, 68, 68, 0.8)' :
                    isValidating ? 'rgba(34, 211, 238, 0.9)' :
                    'rgba(16, 185, 129, 0.8)';
  
  return (
    <div 
      className="absolute top-1/2 -translate-y-1/2 z-30 pointer-events-none"
      style={{ left: position - 3 }}
    >
      {/* Punto de luz con glow */}
      <div className={`
        w-1.5 h-1.5 rounded-full
        ${lightColor}
        ${(selectedRouteId && isOnSelectedRoute) || isValidating ? 'animate-pulse' : ''}
      `}
        style={{
          boxShadow: `0 0 ${isValidating ? '12px 4px' : '8px 2px'} ${glowColor}, 0 0 ${isValidating ? '24px 8px' : '16px 4px'} ${glowColor.replace('0.8', '0.4').replace('0.9', '0.5')}`,
          filter: (selectedRouteId && isOnSelectedRoute) || isValidating ? 'brightness(1.8)' : 'brightness(1)'
        }}
      />
      
      {/* Indicador de validacion - solo durante validacion */}
      {isValidating && (
        <div className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap">
          <span className="text-[8px] font-bold text-cyan-200 bg-cyan-500/20 px-1.5 py-0.5 rounded-sm border border-cyan-500/30">
            OSRM
          </span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// RUTA EN TIMELINE - ARRASTRABLE
// ============================================================================

function TimelineRoute({ route, busId, onRemove, onSelect, validation, minHour, pixelsPerHour, segments, isSelected }) {
  const [isHovered, setIsHovered] = React.useState(false);
  
  // Generar ID unico para el draggable
  const draggableId = React.useMemo(() => `route-${busId}-${route.id}`, [busId, route.id]);
  
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: draggableId,
    data: {
      type: 'route',
      route,
      busId,
      source: 'bus'
    }
  });
  
  const duration = durationMin(route.startTime, route.endTime);
  
  let startX, width;
  if (segments && segments.length > 0) {
    startX = timeToCompressedPx(route.startTime, segments, pixelsPerHour);
    const endX = timeToCompressedPx(route.endTime, segments, pixelsPerHour);
    width = Math.max(endX - startX, 4);
  } else {
    startX = ((timeToMinutes(route.startTime) - minHour * 60) / 60) * pixelsPerHour;
    width = Math.max((duration / 60) * pixelsPerHour, 4);
  }

  const hasError = validation?.errors?.length > 0;
  const isEntry = route.type === 'entry';
  const seatsNeeded = getRouteCapacityNeeded(route);
  const seatsRangeLabel = getRouteCapacityRangeLabel(route);

  // Prevenir click si estamos arrastrando
  const handleClick = (e) => {
    if (isDragging) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    e.stopPropagation();
    onSelect?.();
  };

  return (
    <div 
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      data-no-timeline-pan
      className={`absolute top-0 h-full ${(isHovered || isDragging) ? 'z-[70]' : (isSelected ? 'z-30' : 'z-10')} ${isDragging ? 'opacity-40' : ''}`}
      style={{ 
        left: startX, 
        width,
        cursor: isDragging ? 'grabbing' : 'grab'
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={handleClick}
    >
      {/* Linea de tiempo (la "carretera") */}
      <div className={`
        absolute top-1/2 left-0 right-0 h-[2px] -translate-y-1/2
        ${hasError 
          ? 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.65)]' 
          : isSelected 
            ? 'bg-cyan-300/95 shadow-[0_0_8px_rgba(34,211,238,0.55)]' 
            : 'bg-cyan-300/70'}
        ${isHovered && !hasError ? 'bg-cyan-200/95 shadow-[0_0_10px_rgba(34,211,238,0.7)]' : ''}
        ${isHovered && hasError ? 'bg-red-400 shadow-[0_0_14px_rgba(239,68,68,0.85)]' : ''}
        transition-all duration-150
      `}>
        {/* Puntos de tiempo */}
        <div className={`absolute left-0 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full ${hasError ? 'bg-red-300' : 'bg-cyan-100'}`} />
        <div className={`absolute right-0 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full ${hasError ? 'bg-red-300' : 'bg-cyan-100'}`} />
      </div>

      {/* Handle de arrastre - estilo tecnico */}
      <div className={`
        absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
        w-4 h-4 rounded-sm border flex items-center justify-center
        transition-all duration-150
        ${isHovered || isDragging ? 'opacity-100 scale-100' : 'opacity-0 scale-75'}
        ${hasError 
          ? 'bg-red-500/80 border-red-300/60 shadow-lg shadow-red-500/30' 
          : 'bg-[#0f1c28] border-cyan-400/45 shadow-[0_0_16px_rgba(34,211,238,0.25)]'}
        z-30
      `}>
        <div className="w-2 h-px bg-cyan-200/90" />
      </div>

      {/* INFO DEBAJO DE LA LINEA - siempre visible si hay espacio */}
      {width > 60 && (
        <div className="absolute top-[58%] left-0 right-0 pt-1">
          {/* Nombre del colegio: entra a / sale de */}
          <div className="flex items-center gap-1">
            <span className={`text-[11px] font-semibold truncate leading-tight ${hasError ? 'text-red-200' : 'text-gray-200'}`}>
              {isEntry ? (route.destination || route.school || route.school_name || 'Colegio') : (route.origin || route.school || route.school_name || 'Colegio')}
            </span>
            <span className={`
              text-[9px] px-1 py-0.5 rounded font-bold uppercase
              ${hasError 
                  ? 'bg-red-500/20 text-red-400' 
                  : isEntry 
                  ? 'bg-cyan-500/18 text-cyan-300 border border-cyan-500/25' 
                  : 'bg-amber-500/18 text-amber-300 border border-amber-500/25'}
            `}>
              {isEntry ? 'ENT' : 'SAL'}
            </span>
            {(seatsRangeLabel || seatsNeeded > 0) && (
              <span className={`
                text-[9px] px-1 py-0.5 rounded font-bold tabular-nums
                ${hasError
                    ? 'bg-red-500/20 text-red-300'
                    : isEntry
                    ? 'bg-cyan-500/18 text-cyan-300 border border-cyan-500/25'
                    : 'bg-amber-500/18 text-amber-300 border border-amber-500/25'}
              `}>
                {seatsNeeded > 0 ? `${seatsNeeded}P` : seatsRangeLabel}
              </span>
            )}
          </div>
          {/* Horario compacto */}
          <div className={`text-[10px] font-mono leading-tight mt-0.5 ${hasError ? 'text-red-300' : 'text-gray-400'}`}>
            {route.startTime} {'->'} {route.endTime}
          </div>
        </div>
      )}

      {/* Tooltip/Card con informacion detallada (aparece en hover) */}
      <div className={`
        absolute top-full left-0 mt-1 z-30
        bg-[#0a121b] border ${isSelected ? 'border-cyan-300/65' : 'border-slate-500/65'} rounded-md px-3 py-2
        shadow-[0_18px_40px_rgba(2,10,18,0.85)] min-w-[200px]
        transition-all duration-150
        ${isHovered ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-1 pointer-events-none'}
      `}>
        {/* Codigo y tipo */}
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-[11px] font-medium text-gray-400 tracking-tight">
            {route.code}
          </span>
          <span className={`
            px-1.5 py-0.5 rounded text-[9px] font-bold uppercase
            ${isEntry ? 'bg-cyan-500/18 text-cyan-300 border border-cyan-500/25' : 'bg-amber-500/18 text-amber-300 border border-amber-500/25'}
          `}>
            {isEntry ? 'ENTRADA' : 'SALIDA'}
          </span>
          {hasError && <AlertCircle className="w-3 h-3 text-red-500" />}
        </div>

        {/* Colegio principal */}
        <div className="text-[13px] font-semibold text-white mb-1">
          {isEntry 
            ? (route.destination || route.school || route.school_name || 'Destino')
            : (route.origin || route.school || route.school_name || 'Origen')
          }
        </div>

        {/* Horarios */}
        <div className="flex items-center gap-1.5 text-[12px] font-mono text-gray-300">
          <span>{route.startTime}</span>
          <span className="text-gray-600">{'->'}</span>
          <span>{route.endTime}</span>
          <span className="text-gray-500 text-[10px]">({duration}m)</span>
        </div>

        {(seatsRangeLabel || seatsNeeded > 0) && (
          <div className="mt-1 text-[10px] text-cyan-300 uppercase tracking-[0.08em]">
            Plazas requeridas: <span className="font-semibold tabular-nums">{seatsNeeded > 0 ? `${seatsNeeded}P` : seatsRangeLabel}</span>
            {seatsRangeLabel && seatsNeeded > 0 && (
              <span className="text-gray-500 normal-case ml-2">Rango vehículo {seatsRangeLabel}</span>
            )}
          </div>
        )}

        {/* Origen/Destino completo */}
        {(route.origin || route.destination) && (
          <div className="mt-1.5 pt-1.5 border-t border-gray-800 text-[10px] text-gray-500">
            {route.origin && <span className="text-gray-400">{route.origin}</span>}
            {route.origin && route.destination && <span className="mx-1 text-gray-600">{'->'}</span>}
            {route.destination && <span className="text-gray-400">{route.destination}</span>}
          </div>
        )}
      </div>

      {/* Click area para eliminar */}
      <button
        onClick={(e) => { e.stopPropagation(); onRemove?.(); }}
        data-no-timeline-pan
        className={`
          absolute -top-1 left-0 w-4 h-4 rounded-sm bg-[#1b1f2a] text-red-300 
          border border-red-500/30 flex items-center justify-center text-[10px] font-bold
          transition-all duration-150 z-40
          ${isHovered ? 'opacity-100 scale-100' : 'opacity-0 scale-75'}
          hover:bg-red-500/20
        `}
        style={{ left: startX - 8 }}
      >
        -
      </button>

      {/* Etiqueta de duracion visible si hay espacio */}
      {width > 60 && (
        <div className={`
          absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
          px-1.5 py-0.5 rounded bg-[#0a0a0b]/90
          text-[10px] font-mono text-gray-400 whitespace-nowrap
          pointer-events-none
          ${isHovered ? 'opacity-0' : 'opacity-100'}
          transition-opacity duration-150
        `}>
          {duration}m
        </div>
      )}
    </div>
  );
}

// ============================================================================
// CONECTOR ENTRE RUTAS
// ============================================================================

function RouteConnector({ from, to, minHour, pixelsPerHour, segments }) {
  let endX, startX;
  
  if (segments && segments.length > 0) {
    endX = timeToCompressedPx(from.endTime, segments, pixelsPerHour);
    startX = timeToCompressedPx(to.startTime, segments, pixelsPerHour);
  } else {
    endX = ((timeToMinutes(from.endTime) - minHour * 60) / 60) * pixelsPerHour;
    startX = ((timeToMinutes(to.startTime) - minHour * 60) / 60) * pixelsPerHour;
  }

  const gap = startX - endX;
  if (gap <= 4) return null;

  const windowMinutes = Math.max(0, durationMin(from.endTime, to.startTime));
  const realMinutes = getPositioningMinutes(to);
  const hasRealMeasure = Number.isFinite(realMinutes);
  const isTight = windowMinutes < 10;
  const isInfeasible = realMinutes > windowMinutes;

  // La linea de "tiempo real" usa el mismo eje temporal del gap.
  const realRatio = windowMinutes > 0 ? Math.min(realMinutes / windowMinutes, 1) : 0;
  const realWidth = hasRealMeasure
    ? Math.max(realMinutes > 0 ? 8 : 0, Math.min(gap, gap * realRatio))
    : 0;

  return (
    <div className="absolute top-1/2 -translate-y-1/2 pointer-events-none" style={{ left: endX, width: gap }}>
      {/* Ventana entre rutas (linea actual) */}
      <div className={`absolute left-0 right-0 top-[-5px] border-t-2 border-dashed ${isTight ? 'border-red-400/75' : 'border-slate-400/70'}`} />

      {/* Tiempo real de posicionamiento (nueva linea debajo) */}
      <div className="absolute left-0 right-0 top-[5px] border-t border-slate-600/55" />
      {realWidth > 0 && (
        <div
          className={`absolute left-0 top-[5px] border-t-2 ${isInfeasible ? 'border-rose-300/95' : 'border-cyan-300/95'}`}
          style={{ width: realWidth }}
        />
      )}

      {gap > 26 && (
        <div className={`absolute left-1/2 -translate-x-1/2 top-[-14px] px-1.5 py-0.5 rounded text-[9px] font-mono tabular-nums ${isTight ? 'bg-red-500/20 text-red-300' : 'bg-slate-800 text-slate-400'}`}>
          V {windowMinutes}m
        </div>
      )}
      {gap > 40 && (
        <div className={`absolute left-1/2 -translate-x-1/2 top-[7px] px-1.5 py-0.5 rounded text-[9px] font-mono tabular-nums ${isInfeasible ? 'bg-rose-500/20 text-rose-300' : 'bg-cyan-500/20 text-cyan-300'}`}>
          R {realMinutes}m
        </div>
      )}
    </div>
  );
}

// ============================================================================
// FILA DE BUS
// ============================================================================

export function TimelineBusRow({ bus, routes, validations, onRemoveRoute, onSelectRoute, isActive, minHour, maxHour, pixelsPerHour, segments, selectedRouteId, onValidateBus }) {
  const { isOver, setNodeRef } = useDroppable({ 
    id: `bus-${bus.id}`,
    data: { type: 'bus', busId: bus.id }
  });
  
  // Estado para controlar la validacion OSRM en progreso
  const [isValidating, setIsValidating] = React.useState(false);
  const [validationProgress, setValidationProgress] = React.useState(0);
  const [osrmIssues, setOsrmIssues] = React.useState([]);
  const [osrmSummary, setOsrmSummary] = React.useState('');
  const [showOsrmDetails, setShowOsrmDetails] = React.useState(false);

  const stats = useMemo(() => {
    if (!routes.length) return null;
    const first = routes.reduce((a, b) => a.startTime < b.startTime ? a : b);
    const last = routes.reduce((a, b) => a.endTime > b.endTime ? a : b);
    const workMinutes = routes.reduce((sum, r) => sum + durationMin(r.startTime, r.endTime), 0);
    const totalMinutes = durationMin(first.startTime, last.endTime);
    const efficiency = totalMinutes > 0 ? Math.round((workMinutes / totalMinutes) * 100) : 0;
    const minSeats = routes.reduce((maxSeats, route) => {
      const needed = getRouteCapacityNeeded(route);
      return needed > maxSeats ? needed : maxSeats;
    }, 0);
    return {
      first: first.startTime,
      last: last.endTime,
      count: routes.length,
      efficiency: Math.max(0, Math.min(100, efficiency)),
      minSeats,
    };
  }, [routes]);

  const totalWidth = segments && segments.length > 0
    ? segments[segments.length - 1].end * (pixelsPerHour / 60)
    : (maxHour - minHour) * pixelsPerHour;

  // Verificar si hay errores en alguna ruta
  const hasAnyError = validations && Object.values(validations).some(v => v?.errors?.length > 0);

  const routeCodeById = useMemo(() => {
    const map = new Map();
    routes.forEach((route) => {
      if (route?.id) map.set(String(route.id), route.code || route.id);
      if (route?.route_id) map.set(String(route.route_id), route.code || route.route_id);
    });
    return map;
  }, [routes]);

  const osrmIssueRows = useMemo(() => {
    return (Array.isArray(osrmIssues) ? osrmIssues : []).map((issue, idx) => {
      const rawA = issue?.route_a ?? '?';
      const rawB = issue?.route_b ?? '?';
      const routeA = routeCodeById.get(String(rawA)) || rawA;
      const routeB = routeCodeById.get(String(rawB)) || rawB;
      const reason = issue?.message || issue?.issue_type || 'Incidencia sin detalle';
      const suggestion = issue?.suggestion || 'Revisa horas o reasigna esta conexión a otro bus';
      return {
        id: `${routeA}-${routeB}-${idx}`,
        pair: `${routeA} -> ${routeB}`,
        reason,
        suggestion,
        severity: issue?.severity || 'error',
      };
    });
  }, [osrmIssues, routeCodeById]);

  return (
    <>
    <div 
      ref={setNodeRef}
      className={`
        flex items-stretch border-b border-slate-700/30 transition-all duration-150
        ${isActive ? 'bg-[#11141b]' : 'bg-transparent'}
        ${isOver ? 'bg-cyan-500/5' : ''}
      `}
    >
      {/* Info del Bus - cabecero grande sin icono */}
      <div className={`
        w-[118px] flex-shrink-0 flex flex-col justify-center px-2 py-2
        border-r border-slate-700/40
        ${isActive ? 'bg-[#102030]/65' : ''}
      `}>
        {/* ID del bus - grande y prominente */}
        <div className="flex items-center gap-2">
          <div className={`
            text-[29px] font-semibold tracking-tight leading-none tabular-nums data-mono
            ${isActive ? 'text-cyan-300' : 'text-slate-100'}
          `}>
            {bus.id}
          </div>
          
          {/* Boton de comprobacion OSRM */}
          {routes.length > 0 && (
            <button
              onClick={async (e) => {
                e.stopPropagation();
                if (!onValidateBus || isValidating) return;
                
                setIsValidating(true);
                setValidationProgress(0);
                
                try {
                  // Simular progreso durante la validacion
                  const progressInterval = setInterval(() => {
                    setValidationProgress(prev => Math.min(prev + 10, 90));
                  }, 300);
                  
                  // Llamar a la validacion OSRM
                  const result = await onValidateBus(bus);
                  
                  clearInterval(progressInterval);
                  setValidationProgress(100);
                  
                  // Mostrar resultado
                  if (result.feasible) {
                    setOsrmIssues([]);
                    setOsrmSummary(result.message || `Bus ${bus.id} viable`);
                    setShowOsrmDetails(false);
                    notifications?.success?.('Validacion completada', `El bus ${bus.id} tiene un horario viable`);
                  } else {
                    const issues = Array.isArray(result?.issues) ? result.issues : [];
                    const totalIssues = result?.issues_count || issues.length;
                    setOsrmIssues(issues);
                    setOsrmSummary(result.message || `Bus ${bus.id} con ${totalIssues} incidencias`);
                    setShowOsrmDetails(true);
                    const topIssues = issues.slice(0, 3).map((issue) => {
                      const routeA = issue?.route_a || '?';
                      const routeB = issue?.route_b || '?';
                      const reason = issue?.message || issue?.issue_type || 'Incidencia sin detalle';
                      return `${routeA} -> ${routeB}: ${reason}`;
                    });

                    const details = topIssues.length > 0
                      ? topIssues.join(' | ')
                      : (result.message || `El bus ${bus.id} tiene tiempos inviables`);

                    notifications?.error?.(
                      'Problema detectado',
                      `${result.message || `Bus ${bus.id} con ${totalIssues} incidencias`} | ${details}`
                    );

                    if (issues.length > 0) {
                      console.groupCollapsed(`[ValidationWS][${bus.id}] ${totalIssues} incidencias`);
                      console.table(issues.map((issue, idx) => ({
                        idx: idx + 1,
                        route_a: issue?.route_a ?? '',
                        route_b: issue?.route_b ?? '',
                        type: issue?.issue_type ?? '',
                        severity: issue?.severity ?? '',
                        message: issue?.message ?? '',
                        suggestion: issue?.suggestion ?? ''
                      })));
                      console.groupEnd();
                    }
                  }
                } catch (error) {
                  console.error('Validation error:', error);
                  notifications?.error?.('Error de validacion', 'No se pudo completar la verificacion OSRM');
                } finally {
                  setTimeout(() => {
                    setIsValidating(false);
                    setValidationProgress(0);
                  }, 2000);
                }
              }}
              data-no-timeline-pan
              disabled={isValidating}
              className={`
                px-1.5 py-1 rounded-sm border text-[9px] font-semibold tracking-[0.14em] uppercase transition-colors
                ${isValidating 
                  ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-200' 
                  : 'bg-[#151b25] border-slate-600/60 hover:border-cyan-400/50 text-slate-300 hover:text-cyan-200'
                }
              `}
              title={isValidating ? 'Validando...' : 'Comprobar viabilidad con OSRM'}
            >
              {isValidating ? (
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              ) : (
                <span>OSRM</span>
              )}
            </button>
          )}
        </div>
        
        {/* Stats */}
        <div className="mt-1.5 flex items-center gap-2">
          {stats ? (
            <>
              <span className="text-[11px] text-slate-400 uppercase tracking-wide">{stats.count} rutas</span>
              <span className={`
                text-[11px] font-semibold tabular-nums
                ${stats.efficiency > 75 ? 'text-cyan-300' : stats.efficiency > 50 ? 'text-amber-300' : 'text-rose-300'}
              `}>
                {stats.efficiency}%
              </span>
              {stats.minSeats > 0 && (
                <span className="text-[10px] text-cyan-300 tabular-nums uppercase tracking-wide">
                  {stats.minSeats} plazas
                </span>
              )}
            </>
          ) : (
            <span className="text-[11px] text-slate-500 uppercase tracking-wide">Sin rutas</span>
          )}
        </div>

        {osrmSummary && (
          <div className={`mt-1 text-[10px] leading-tight uppercase tracking-[0.08em] data-mono ${osrmIssueRows.length > 0 ? 'text-rose-300' : 'text-cyan-300'}`}>
            {osrmSummary}
          </div>
        )}

        {osrmIssueRows.length > 0 && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowOsrmDetails((prev) => !prev);
            }}
            className="mt-1 px-1.5 py-0.5 rounded-sm border border-rose-500/30 bg-rose-500/10 text-rose-200 text-[10px] uppercase tracking-[0.08em] data-mono hover:bg-rose-500/20 transition-colors text-left"
            title="Mostrar detalle de incidencias OSRM"
          >
            {showOsrmDetails ? 'Ocultar detalle' : `Detalle ${osrmIssueRows.length}`}
          </button>
        )}
      </div>

      {/* Timeline */}
      <div 
        className={`
          relative overflow-visible
          ${isOver ? 'bg-cyan-500/5' : ''}
        `}
        style={{ height: CONFIG.ROW_HEIGHT, width: totalWidth }}
      >
        {/* Linea base del tiempo */}
        <div className="absolute top-1/2 left-0 right-0 h-[2px] bg-slate-700/65" />

        {/* Punto de luz animado - solo si hay rutas */}
        {routes.length > 0 && (
          <AnimatedLight 
            routes={routes}
            selectedRouteId={selectedRouteId}
            minHour={minHour}
            pixelsPerHour={pixelsPerHour}
            segments={segments}
            hasError={hasAnyError}
            isValidating={isValidating}
          />
        )}

        {/* Zona de drop - feedback visual mejorado */}
        {isOver && (
          <div className="absolute inset-0 border border-dashed border-cyan-400/60 bg-cyan-500/10 z-50 flex items-center justify-center">
            <div className="bg-[#10131a] px-3 py-1 rounded-sm border border-cyan-400/40">
              <span className="text-[10px] font-semibold text-cyan-300 uppercase tracking-[0.14em] data-mono">Asignar</span>
            </div>
          </div>
        )}

        {/* Rutas */}
        <div className="relative h-full">
          {routes.map((route, i) => (
            <React.Fragment key={route.id}>
              {i > 0 && (
                <RouteConnector 
                  from={routes[i-1]} 
                  to={route}
                  minHour={minHour}
                  pixelsPerHour={pixelsPerHour}
                  segments={segments}
                />
              )}
              <TimelineRoute
                route={route}
                busId={bus.id}
                onRemove={() => onRemoveRoute?.(route.id)}
                onSelect={() => onSelectRoute?.(route.id)}
                validation={validations?.[route.id]}
                minHour={minHour}
                pixelsPerHour={pixelsPerHour}
                segments={segments}
                isSelected={selectedRouteId === route.id}
              />
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
    {showOsrmDetails && osrmIssueRows.length > 0 && (
      <div className="ml-[118px] border-b border-[#2a4056] bg-[#0d1621]">
        <div className="text-[10px] text-rose-200 font-semibold px-2 py-1 border-b border-rose-500/20 uppercase tracking-[0.12em] data-mono">
          Incidencias de viabilidad | {bus.id}
        </div>
        <div>
          {osrmIssueRows.map((row, idx) => (
            <div key={row.id} className="border-b border-slate-700/30 last:border-b-0 px-2 py-1">
              <div className="flex items-start gap-1.5">
                <span className="text-[10px] text-rose-300 font-mono shrink-0">{idx + 1}.</span>
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] text-slate-100 font-semibold truncate">
                    {row.pair}
                  </div>
                  <div className="text-[9px] text-slate-300 leading-tight">
                    Motivo: {row.reason}
                  </div>
                  <div className="text-[9px] text-slate-400 leading-tight">
                    Acción: {row.suggestion}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )}
    </>
  );
}

export default TimelineBusRow;


