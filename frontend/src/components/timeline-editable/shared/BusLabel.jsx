import React from 'react';
import { Bus } from 'lucide-react';

/**
 * Etiqueta del bus con ID y conteo de rutas
 */
export function BusLabel({ busId, routeCount }) {
  return (
    <div className="flex items-center gap-2 min-w-[120px] px-3 py-2 bg-gray-800/50 rounded-lg">
      <Bus className="w-4 h-4 text-blue-400" />
      <div className="flex flex-col">
        <span className="text-sm font-medium text-gray-200">Bus {busId}</span>
        <span className="text-[10px] text-gray-500">
          {routeCount} {routeCount === 1 ? 'ruta' : 'rutas'}
        </span>
      </div>
    </div>
  );
}
