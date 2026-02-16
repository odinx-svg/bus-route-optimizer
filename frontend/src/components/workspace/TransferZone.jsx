/**
 * TransferZone - Zona de transferencia "fantasma"
 * 
 * - Vacía + no drag: Caja minimalista de 40px
 * - Vacía + drag: Zona de drop resaltada
 * - Con rutas: Se expande para mostrarlas
 */

import React from 'react';
import { useDroppable, useDraggable } from '@dnd-kit/core';
import { Package, ArrowRightLeft, Trash2 } from 'lucide-react';

/**
 * Tarjeta de ruta en transferencia
 */
function TransferRouteCard({ route }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `transfer-${route.id}`,
    data: { type: 'route', route, source: 'transfer' },
  });

  const colors = {
    entry: 'bg-gradient-to-br from-indigo-500 to-indigo-600',
    exit: 'bg-gradient-to-br from-amber-500 to-amber-600',
  };

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={`
        p-2 rounded-lg cursor-grab active:cursor-grabbing
        ${colors[route.type] || colors.entry}
        shadow-lg transition-all duration-200
        ${isDragging ? 'opacity-50 scale-105' : 'hover:scale-102'}
      `}
    >
      <div className="text-[10px] font-bold text-white truncate">{route.code}</div>
      <div className="text-[9px] text-white/80 mt-0.5">{route.startTime} → {route.endTime}</div>
    </div>
  );
}

/**
 * Zona de Transferencia - Versión Fantasma
 */
export function TransferZone({ routes = [], isDragging = false, onRouteRemove }) {
  const { isOver, setNodeRef } = useDroppable({
    id: 'transfer-zone',
    data: { type: 'transfer-zone' },
  });

  const hasRoutes = routes.length > 0;

  // ESTADO 1: Con rutas - mostrar en modo expandido
  if (hasRoutes) {
    return (
      <div ref={setNodeRef} className="h-full flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-indigo-500/20 flex items-center justify-center">
              <Package className="w-3 h-3 text-indigo-400" />
            </div>
            <span className="text-xs font-medium text-white">Transferencia</span>
            <span className="text-[10px] text-gray-500">({routes.length})</span>
          </div>
          <button
            onClick={() => routes.forEach(r => onRouteRemove?.(r.id))}
            className="p-1 text-gray-600 hover:text-red-400 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className={`
          flex-1 rounded-lg border-2 border-dashed p-2 overflow-y-auto
          ${isOver ? 'border-indigo-500 bg-indigo-500/10' : 'border-gray-700 bg-gray-800/30'}
        `}>
          <div className="grid grid-cols-1 gap-2">
            {routes.map((route, index) => (
              <TransferRouteCard
                key={`transfer-${route.id || index}-${index}`}
                route={route}
              />
            ))}
          </div>
        </div>

        <p className="mt-2 text-[9px] text-gray-500 text-center">
          Arrastra a un bus
        </p>
      </div>
    );
  }

  // ESTADO 2: Vacío + Drag activo - mostrar zona de drop
  if (isDragging) {
    return (
      <div ref={setNodeRef} className="h-full flex flex-col">
        <div className={`
          flex-1 rounded-lg border-2 border-dashed flex flex-col items-center justify-center p-4 transition-all
          ${isOver 
            ? 'border-indigo-500 bg-indigo-500/20 scale-[1.02]' 
            : 'border-indigo-500/50 bg-indigo-500/5'
          }
        `}>
          <ArrowRightLeft className={`
            w-6 h-6 mb-2 transition-colors
            ${isOver ? 'text-indigo-400' : 'text-indigo-500/50'}
          `} />
          <span className={`
            text-xs font-medium transition-colors
            ${isOver ? 'text-indigo-300' : 'text-indigo-400/70'}
          `}>
            {isOver ? 'Suelta aquí' : 'Zona de transferencia'}
          </span>
        </div>
      </div>
    );
  }

  // ESTADO 3: Vacío + sin drag - caja minimalista (modo fantasma)
  return (
    <div className="h-full flex flex-col items-center justify-center">
      <div className="w-10 h-10 rounded-lg bg-gray-800/50 border border-gray-700/50 flex items-center justify-center">
        <Package className="w-4 h-4 text-gray-600" />
      </div>
    </div>
  );
}

export default TransferZone;
