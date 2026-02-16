/**
 * RouteLego - Componente visual tipo "pieza de lego" para rutas
 * 
 * Diseño compacto (timeline):
 * - Solo nombre corto (máx 15 chars) + horas inicio-fin
 * - Color indica tipo: Azul=Entrada, Naranja=Salida, Gris=Bloqueada
 * - Sin iconos, sin código de ruta, sin duración
 * - Tooltip nativo con info completa
 */

import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { Lock } from 'lucide-react';

// Truncar nombre a máximo 15 caracteres
const truncateName = (name, maxLength = 15) => {
  if (!name) return 'Sin nombre';
  if (name.length <= maxLength) return name;
  return name.slice(0, maxLength) + '…';
};

// Formatear hora (HH:MM)
const formatTime = (time) => {
  if (!time) return '--:--';
  // Si ya viene en formato HH:MM, devolverlo
  if (time.length === 5 && time.includes(':')) return time;
  // Si viene con segundos, truncar
  if (time.includes(':')) return time.slice(0, 5);
  return time;
};

export function RouteLego({ 
  route, 
  isDragging: isExternalDragging,
  compact = false,
  onClick,
  onLockToggle,
  isSelected = false
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    isDragging: isInternalDragging
  } = useDraggable({
    id: `route-${route.route_id}`,
    data: { type: 'route', route },
    disabled: route.isLocked
  });

  const isDragging = isExternalDragging || isInternalDragging;
  const isEntry = route.type === 'entry';
  const isLocked = route.isLocked;

  // Colores según estado y tipo
  const getColors = () => {
    if (isLocked) {
      return {
        bg: 'bg-gray-500',
        border: 'border-gray-400',
        hover: ''
      };
    }
    if (isEntry) {
      return {
        bg: 'bg-[#3b82f6]',
        border: 'border-blue-400',
        hover: 'hover:bg-blue-400'
      };
    }
    return {
      bg: 'bg-[#f59e0b]',
      border: 'border-amber-400',
      hover: 'hover:bg-amber-400'
    };
  };

  const colors = getColors();

  const style = transform ? {
    transform: CSS.Transform.toString(transform),
  } : undefined;

  const handleClick = (e) => {
    if (onClick && !isDragging) {
      onClick(route);
    }
  };

  // Construir tooltip con info completa
  const buildTooltip = () => {
    const schoolName = route.school || route.route_name || 'Sin nombre';
    const routeCode = route.route_code || route.route_id;
    const typeLabel = isEntry ? 'Entrada' : 'Salida';
    const startTime = formatTime(route.currentStartTime || route.start_time);
    const endTime = formatTime(route.currentEndTime || route.end_time);
    
    return `${schoolName} | ${routeCode} | ${typeLabel} | ${startTime} - ${endTime}`;
  };

  if (compact) {
    const startTime = formatTime(route.currentStartTime || route.start_time);
    const endTime = formatTime(route.currentEndTime || route.end_time);
    
    return (
      <div
        ref={setNodeRef}
        {...listeners}
        {...attributes}
        style={style}
        onClick={handleClick}
        title={buildTooltip()}
        className={`
          group relative h-7 rounded border ${colors.bg} ${colors.border}
          flex items-center justify-between px-1.5 cursor-grab select-none
          ${isLocked ? 'opacity-70 cursor-not-allowed' : `${colors.hover} cursor-grab`}
          ${isDragging ? 'opacity-50 scale-105 z-50' : ''}
          ${isSelected ? 'ring-1 ring-white' : ''}
          transition-all duration-150
        `}
      >
        {/* Nombre corto */}
        <span className="text-white text-[11px] font-medium truncate max-w-[90px]">
          {truncateName(route.school || route.route_name)}
        </span>
        
        {/* Horas */}
        <span className="text-white/90 text-[10px] font-mono ml-1 whitespace-nowrap">
          {startTime}→{endTime}
        </span>
        
        {/* Indicador de bloqueado (solo icono pequeño) */}
        {isLocked && (
          <Lock className="w-2.5 h-2.5 text-white/70 ml-1 flex-shrink-0" />
        )}
      </div>
    );
  }

  // Versión completa (panel de rutas disponibles)
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      style={style}
      onClick={handleClick}
      className={`
        group relative rounded-lg border-2 ${colors.bg} ${colors.border}
        p-3 cursor-grab select-none
        ${isLocked ? 'opacity-60 cursor-not-allowed' : `${colors.hover} cursor-grab`}
        ${isDragging ? 'opacity-50 scale-105 z-50 shadow-2xl' : 'shadow-lg'}
        ${isSelected ? 'ring-2 ring-white ring-offset-2 ring-offset-[#0f0f14]' : ''}
        transition-all duration-150
      `}
    >
      {/* Nombre del colegio */}
      <div className="text-white font-semibold text-sm leading-tight mb-0.5 truncate">
        {route.school || route.route_name || 'Sin nombre'}
      </div>

      {/* Código de ruta */}
      <div className="text-white/60 text-xs truncate font-mono">
        {route.route_code || route.route_id}
      </div>

      {/* Footer con hora y tipo */}
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/20">
        <span className="text-white/80 text-xs font-mono">
          {formatTime(route.currentStartTime || route.start_time)} - {formatTime(route.currentEndTime || route.end_time)}
        </span>
        <span className="text-white/60 text-[10px] uppercase">
          {isEntry ? 'ENT' : 'SAL'}
        </span>
      </div>

      {/* Indicador de bloqueado */}
      {isLocked && (
        <div className="absolute top-1 right-1">
          <Lock className="w-3 h-3 text-white/60" />
        </div>
      )}
    </div>
  );
}

export default RouteLego;
