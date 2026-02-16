/**
 * RouteDetailsPanel - Panel de detalles de ruta seleccionada
 * 
 * Muestra:
 * - Información detallada de la ruta seleccionada
 * - Sugerencias de asignación
 * - Controles de bloqueo/edición
 * - Validaciones y advertencias
 */

import { 
  Clock, 
  MapPin, 
  Bus, 
  Lock, 
  Unlock, 
  AlertCircle, 
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Lightbulb,
  X
} from 'lucide-react';
import { useTimelineEditableStore } from '../../stores/timelineEditableStore';
import { useMemo } from 'react';

export function RouteDetailsPanel({ route }) {
  const { 
    selectRoute,
    clearSelection,
    toggleRouteLock,
    moveRoute,
    generateSuggestionsForRoute
  } = useTimelineEditableStore();

  // Generar sugerencias si hay una ruta seleccionada
  const suggestions = useMemo(() => {
    if (!route) return [];
    // Aquí se podría llamar a generateSuggestionsForRoute
    // Por ahora retornamos sugerencias simuladas basadas en la ruta
    return generateMockSuggestions(route);
  }, [route]);

  if (!route) {
    return (
      <div className="w-80 bg-[#13131a] border-l border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <MapPin className="w-4 h-4 text-gray-400" />
            Detalles
          </h3>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center">
            <div className="w-16 h-16 bg-gray-800/50 rounded-full flex items-center justify-center mx-auto mb-4">
              <MapPin className="w-8 h-8 text-gray-600" />
            </div>
            <p className="text-gray-500 text-sm">Selecciona una ruta</p>
            <p className="text-gray-600 text-xs mt-1">
              Haz clic en cualquier ruta para ver sus detalles y sugerencias
            </p>
          </div>
        </div>
      </div>
    );
  }

  const isEntry = route.type === 'entry';
  const typeColor = isEntry ? 'text-blue-400' : 'text-amber-400';
  const typeBg = isEntry ? 'bg-blue-500/10' : 'bg-amber-500/10';
  const typeBorder = isEntry ? 'border-blue-500/20' : 'border-amber-500/20';

  return (
    <div className="w-80 bg-[#13131a] border-l border-gray-800 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <MapPin className="w-4 h-4 text-gray-400" />
            Detalles de Ruta
          </h3>
          <button
            onClick={() => clearSelection()}
            className="p-1.5 hover:bg-gray-800 rounded-lg text-gray-500 hover:text-gray-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tipo de ruta */}
        <div className={`
          inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium
          ${typeBg} ${typeColor} border ${typeBorder}
        `}>
          {isEntry ? (
            <>
              <ArrowRight className="w-3.5 h-3.5" />
              Ruta de Entrada
            </>
          ) : (
            <>
              <ArrowLeft className="w-3.5 h-3.5" />
              Ruta de Salida
            </>
          )}
        </div>
      </div>

      {/* Contenido scrollable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Información principal */}
        <div className="bg-[#0a0a0f] rounded-xl p-4 border border-gray-800">
          <h4 className="text-white font-medium text-sm mb-1">
            {route.school || route.route_name || 'Sin nombre'}
          </h4>
          <p className="text-gray-500 text-xs font-mono">
            {route.route_code || route.route_id}
          </p>
        </div>

        {/* Timeline de horarios */}
        <div className="bg-[#0a0a0f] rounded-xl p-4 border border-gray-800">
          <h5 className="text-gray-400 text-xs uppercase tracking-wide font-medium mb-3 flex items-center gap-2">
            <Clock className="w-3.5 h-3.5" />
            Horario
          </h5>
          <div className="flex items-center gap-3">
            <div className="flex-1 text-center p-2 bg-gray-800/50 rounded-lg">
              <p className="text-gray-500 text-xs mb-0.5">Inicio</p>
              <p className="text-white font-mono text-sm">
                {route.currentStartTime || route.start_time}
              </p>
            </div>
            <div className="text-gray-600">
              <ArrowRight className="w-4 h-4" />
            </div>
            <div className="flex-1 text-center p-2 bg-gray-800/50 rounded-lg">
              <p className="text-gray-500 text-xs mb-0.5">Fin</p>
              <p className="text-white font-mono text-sm">
                {route.currentEndTime || route.end_time}
              </p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-gray-800 flex items-center justify-between">
            <span className="text-gray-500 text-xs">Duración</span>
            <span className="text-white text-sm font-medium">
              {route.duration_minutes} minutos
            </span>
          </div>
        </div>

        {/* Ubicación */}
        <div className="bg-[#0a0a0f] rounded-xl p-4 border border-gray-800">
          <h5 className="text-gray-400 text-xs uppercase tracking-wide font-medium mb-3 flex items-center gap-2">
            <MapPin className="w-3.5 h-3.5" />
            Ubicación
          </h5>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-gray-500 text-xs">Origen</span>
              <span className="text-white text-xs truncate max-w-[140px]">
                {route.origin || 'No especificado'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500 text-xs">Destino</span>
              <span className="text-white text-xs truncate max-w-[140px]">
                {route.destination || 'No especificado'}
              </span>
            </div>
          </div>
        </div>

        {/* Controles */}
        <div className="bg-[#0a0a0f] rounded-xl p-4 border border-gray-800">
          <h5 className="text-gray-400 text-xs uppercase tracking-wide font-medium mb-3">
            Controles
          </h5>
          <div className="space-y-2">
            <button
              onClick={() => toggleRouteLock(route.route_id)}
              className={`
                w-full flex items-center gap-2 px-3 py-2.5 rounded-lg transition-colors
                ${route.isLocked 
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' 
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700'}
              `}
            >
              {route.isLocked ? (
                <>
                  <Unlock className="w-4 h-4" />
                  <span className="text-sm">Desbloquear ruta</span>
                </>
              ) : (
                <>
                  <Lock className="w-4 h-4" />
                  <span className="text-sm">Bloquear ruta</span>
                </>
              )}
            </button>

            {route.assignedBusId && (
              <button
                onClick={() => moveRoute(route.route_id, null)}
                disabled={route.isLocked}
                className="
                  w-full flex items-center gap-2 px-3 py-2.5 rounded-lg 
                  bg-gray-800 text-gray-300 hover:bg-gray-700
                  disabled:opacity-50 disabled:cursor-not-allowed
                  transition-colors
                "
              >
                <Bus className="w-4 h-4" />
                <span className="text-sm">Liberar del bus</span>
              </button>
            )}
          </div>
        </div>

        {/* Sugerencias */}
        {suggestions.length > 0 && (
          <div className="bg-[#0a0a0f] rounded-xl p-4 border border-gray-800">
            <h5 className="text-gray-400 text-xs uppercase tracking-wide font-medium mb-3 flex items-center gap-2">
              <Lightbulb className="w-3.5 h-3.5" />
              Sugerencias
            </h5>
            <div className="space-y-2">
              {suggestions.map((suggestion, index) => (
                <div
                  key={index}
                  className="p-3 bg-indigo-500/5 border border-indigo-500/20 rounded-lg"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Bus className="w-3.5 h-3.5 text-indigo-400" />
                    <span className="text-indigo-300 text-xs font-medium">
                      {suggestion.busName}
                    </span>
                  </div>
                  <p className="text-gray-500 text-xs">
                    {suggestion.reason}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Estado de validación */}
        {route.hasConflict && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <h5 className="text-red-400 text-sm font-medium mb-1">
                  Conflicto detectado
                </h5>
                <p className="text-red-300/80 text-xs">
                  Esta ruta tiene un conflicto de horario con otra ruta en el mismo bus.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Generar sugerencias simuladas
function generateMockSuggestions(route) {
  // En una implementación real, esto vendría del store
  return [];
}

export default RouteDetailsPanel;
