import React from 'react';
import { ArrowRight } from 'lucide-react';

/**
 * DeadheadGap - Muestra el tiempo de viaje entre dos rutas consecutivas
 * 
 * Visualiza:
 * - Tiempo de deadhead (tiempo de viaje entre rutas)
 * - Indicador visual de si hay suficiente tiempo
 * - Tooltip con información detallada
 */
export function DeadheadGap({ 
  previousRoute, 
  nextRoute, 
  hourRange,
  travelTimeMinutes = 0,
  className = '' 
}) {
  // Si no hay datos suficientes, no mostrar
  if (!previousRoute || !nextRoute) return null;

  // Calcular tiempo disponible entre rutas
  const prevEnd = timeToMinutes(previousRoute.currentEndTime || previousRoute.end_time);
  const nextStart = timeToMinutes(nextRoute.currentStartTime || nextRoute.start_time);
  const availableTime = nextStart - prevEnd;

  // Determinar estado
  const MIN_BUFFER = 10; // minutos mínimos de margen
  const isSufficient = availableTime >= (travelTimeMinutes + MIN_BUFFER);
  const isTight = availableTime > 0 && availableTime < (travelTimeMinutes + MIN_BUFFER);
  const isOverlap = availableTime < 0;

  // Calcular posición en el timeline
  const totalMinutes = (hourRange[1] - hourRange[0]) * 60;
  const gapStart = ((prevEnd - hourRange[0] * 60) / totalMinutes) * 100;
  const gapWidth = ((availableTime > 0 ? availableTime : 5) / totalMinutes) * 100;

  // Clases de color según estado
  let statusClass = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
  let statusIcon = null;
  
  if (isOverlap) {
    statusClass = 'bg-red-500/20 text-red-400 border-red-500/30';
  } else if (isTight) {
    statusClass = 'bg-amber-500/20 text-amber-400 border-amber-500/30';
  }

  return (
    <div
      className={`
        absolute h-6 top-1/2 -translate-y-1/2 z-0
        flex items-center justify-center
        rounded border ${statusClass}
        text-[9px] font-medium
        ${className}
      `}
      style={{
        left: `${gapStart + 2}%`,
        width: `calc(${Math.max(gapWidth - 4, 2)}% - 4px)`,
        minWidth: '40px',
      }}
      title={`Tiempo disponible: ${availableTime}min | Viaje estimado: ${travelTimeMinutes}min | Buffer mínimo: ${MIN_BUFFER}min`}
    >
      {isOverlap ? (
        <span className="flex items-center gap-0.5">
          <span className="text-red-300">!</span>
          Solapado
        </span>
      ) : (
        <span className="flex items-center gap-0.5">
          <ArrowRight className="w-2.5 h-2.5" />
          {availableTime}min
        </span>
      )}
    </div>
  );
}

/**
 * Versión simplificada que solo muestra el gap sin interacción
 */
export function DeadheadGapSimple({ minutes, className = '' }) {
  if (!minutes || minutes <= 0) return null;

  return (
    <div 
      className={`
        inline-flex items-center gap-1 px-1.5 py-0.5 
        bg-gray-700/50 rounded text-[10px] text-gray-400
        ${className}
      `}
    >
      <ArrowRight className="w-3 h-3" />
      {minutes}min
    </div>
  );
}

/**
 * Helper para convertir tiempo a minutos
 */
function timeToMinutes(time) {
  if (!time) return 0;
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
}

export default DeadheadGap;
