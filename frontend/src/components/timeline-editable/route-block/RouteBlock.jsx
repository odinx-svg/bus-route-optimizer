import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { ArrowUpRight, ArrowDownRight, Lock } from 'lucide-react';
import { LockButton } from './LockButton';
import { TimeDisplay } from './TimeDisplay';
import { CompatibilityBadge } from './CompatibilityBadge';

/**
 * RouteBlock - Componente visual para una ruta en el timeline
 * 
 * Muestra información de la ruta posicionada según su horario:
 * - Nombre del colegio (principal)
 * - Duración en minutos
 * - Horario de inicio/fin
 * - Tipo de ruta (entrada/salida)
 * - Indicador de bloqueo
 */
export function RouteBlock({ 
  route, 
  busId, 
  isDragging: isExternalDragging,
  isOverlay = false,
  onLockToggle,
  onClick,
  className = ''
}) {
  const { 
    attributes, 
    listeners, 
    setNodeRef, 
    transform,
    isDragging: isInternalDragging
  } = useDraggable({
    id: `route-${route.route_id}`,
    data: { 
      route, 
      busId, 
      type: 'route' 
    },
    disabled: route.isLocked || !route.isEditable
  });

  const isDragging = isExternalDragging || isInternalDragging;
  const isEntry = route.type === 'entry';

  // Calcular posición left/width basado en tiempo si no viene pre-calculado
  let left = route.position?.left ?? 0;
  let width = route.position?.width ?? 10;
  
  // Si tenemos hourRange en el contexto, recalcular posición
  if (route.currentStartTime && route.currentEndTime && route.hourRange) {
    const [hourRangeStart, hourRangeEnd] = route.hourRange;
    const totalMinutes = (hourRangeEnd - hourRangeStart) * 60;
    const startMinutes = timeToMinutes(route.currentStartTime);
    const endMinutes = timeToMinutes(route.currentEndTime);
    
    left = ((startMinutes - hourRangeStart * 60) / totalMinutes) * 100;
    width = ((endMinutes - startMinutes) / totalMinutes) * 100;
  }

  const handleLockClick = (e) => {
    e.stopPropagation();
    if (onLockToggle) {
      onLockToggle(route.route_id);
    }
  };

  const handleClick = (e) => {
    if (onClick && !route.isLocked) {
      onClick(route);
    }
  };

  // Color basado en tipo de ruta
  const bgColorClass = isEntry 
    ? 'bg-indigo-500 border-indigo-400' 
    : 'bg-amber-500 border-amber-400';

  return (
    <div 
      ref={setNodeRef}
      {...listeners} 
      {...attributes}
      onClick={handleClick}
      style={{ 
        transform: CSS.Transform.toString(transform),
        left: `${left}%`,
        width: `${width}%`,
      }}
      className={`
        group absolute h-14 rounded-md border-2 overflow-hidden
        ${bgColorClass}
        ${route.isLocked 
          ? 'opacity-80 cursor-not-allowed' 
          : 'cursor-grab hover:brightness-110'}
        ${isDragging 
          ? 'opacity-50 scale-105 z-50 shadow-xl' 
          : 'z-10'}
        ${isOverlay ? 'shadow-2xl ring-2 ring-white/50' : ''}
        transition-all duration-200
        ${className}
      `}
    >
      {/* Candado - solo visible si es editable y está bloqueada */}
      {route.isLocked && (
        <div className="absolute top-0.5 right-0.5 z-20">
          <Lock className="w-3 h-3 text-white/80" />
        </div>
      )}
      
      {/* Contenido principal */}
      <div className="flex flex-col justify-center px-2 h-full overflow-hidden">
        {/* Fila superior: Icono + Colegio */}
        <div className="flex items-center gap-1.5 min-w-0">
          <div className={`
            w-4 h-4 rounded flex items-center justify-center flex-shrink-0
            ${isEntry ? 'bg-indigo-600' : 'bg-amber-600'}
          `}>
            {isEntry 
              ? <ArrowUpRight size={10} className="text-white" />
              : <ArrowDownRight size={10} className="text-white" />
            }
          </div>
          <span className="text-xs font-semibold text-white truncate">
            {route.school || 'Sin colegio'}
          </span>
        </div>
        
        {/* Fila inferior: Código de ruta + Duración */}
        <div className="flex items-center justify-between mt-0.5">
          <span className="text-[10px] text-white/80 truncate">
            {route.route_code || route.route_id}
          </span>
          <span className="text-[10px] font-medium text-white/90 bg-black/20 px-1 rounded">
            {route.duration_minutes} min
          </span>
        </div>
        
        {/* Indicador de horario (opcional, compacto) */}
        <div className="text-[9px] text-white/60 mt-0.5">
          {route.currentStartTime || route.start_time} - {route.currentEndTime || route.end_time}
        </div>
      </div>
      
      {/* Badge de compatibilidad (si existe) */}
      {route.compatibility?.overallStatus && route.compatibility.overallStatus !== 'compatible' && (
        <CompatibilityBadge compatibility={route.compatibility} />
      )}
      
      {/* Indicador de tiempo modificado */}
      {(route.currentStartTime && route.currentStartTime !== route.start_time) && (
        <div className="absolute -top-1 left-1/2 -translate-x-1/2 px-1 py-0.5 bg-white/20 rounded text-[8px] text-white font-medium">
          Mod
        </div>
      )}
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

export default RouteBlock;
