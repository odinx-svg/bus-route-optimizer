import React from 'react';
import { Lock, Trash2, Unlock } from 'lucide-react';

/**
 * Controles para cada fila de bus (bloquear/desbloquear, limpiar)
 */
export function BusControls({ onLockAll, onClear, allLocked = false }) {
  return (
    <div className="flex items-center gap-1 ml-2">
      <button
        onClick={onLockAll}
        className="p-1.5 rounded hover:bg-gray-700/50 transition-colors"
        title={allLocked ? "Desbloquear todas las rutas" : "Bloquear todas las rutas"}
      >
        {allLocked ? (
          <Unlock className="w-4 h-4 text-yellow-400" />
        ) : (
          <Lock className="w-4 h-4 text-gray-400" />
        )}
      </button>
      <button
        onClick={onClear}
        className="p-1.5 rounded hover:bg-red-500/20 transition-colors"
        title="Limpiar todas las rutas"
      >
        <Trash2 className="w-4 h-4 text-red-400" />
      </button>
    </div>
  );
}
