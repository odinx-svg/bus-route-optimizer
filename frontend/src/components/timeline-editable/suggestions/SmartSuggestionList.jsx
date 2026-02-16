import { useState, useEffect, useMemo } from 'react';
import { useTimelineValidation } from '../../../hooks/useTimelineValidation';
import { SmartSuggestionCard } from './SmartSuggestionCard';
import { SuggestionsSkeleton } from './SuggestionsSkeleton';
import { AutoSortToggle } from './AutoSortToggle';

/**
 * SmartSuggestionList - Componente de lista de sugerencias con auto-ordenación
 * 
 * Muestra sugerencias ordenadas por score (mejor primero) con:
 * - Visualización de ranking (#1, #2, #3...)
 * - Indicadores de color según puntuación
 * - Todos los factores (buffer, geografía, etc.)
 * - Botón destacado para la mejor opción
 * - Toggle para activar/desactivar auto-ordenación
 * - Skeleton loading mientras carga
 * 
 * @param {Object} props
 * @param {Object} props.route - Ruta liberada para la que se buscan sugerencias
 * @param {Array} props.allBuses - Lista de todos los buses disponibles
 * @param {Function} props.onApply - Callback al aplicar una sugerencia
 * @param {boolean} props.autoSortEnabled - Estado inicial del auto-sort
 */
export function SmartSuggestionList({ 
  route, 
  allBuses = [], 
  onApply,
  autoSortEnabled: initialAutoSort = true 
}) {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoSortEnabled, setAutoSortEnabled] = useState(initialAutoSort);
  const [error, setError] = useState(null);
  const { getSuggestions, isConnected } = useTimelineValidation();

  // Generar sugerencias al montar o cuando cambia la ruta
  useEffect(() => {
    if (route && allBuses.length > 0) {
      generateSmartSuggestions();
    }
  }, [route, allBuses]);

  const generateSmartSuggestions = async () => {
    if (!isConnected) {
      setError('No hay conexión con el servidor de validación');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Llamar al backend para obtener sugerencias
      const response = await getSuggestions(route, allBuses);
      
      if (response.suggestions && Array.isArray(response.suggestions)) {
        // Normalizar y enriquecer las sugerencias
        const enrichedSuggestions = response.suggestions.map(suggestion => ({
          ...suggestion,
          // Asegurar que tenemos todos los campos necesarios
          bus_id: suggestion.bus_id || suggestion.busId,
          position: suggestion.position ?? 0,
          score: suggestion.score ?? 0,
          estimated_start_time: suggestion.estimated_start_time || suggestion.startTime,
          travel_time_from_prev: suggestion.travel_time_from_prev ?? 0,
          buffer_time: suggestion.buffer_time ?? suggestion.buffer_minutes ?? 0,
          factors: suggestion.factors || {
            prev_buffer: suggestion.prev_buffer_score ?? 0,
            next_buffer: suggestion.next_buffer_score ?? 0,
            geographic_proximity: suggestion.geographic_score ?? 0.5
          }
        }));

        setSuggestions(enrichedSuggestions);
      } else {
        setSuggestions([]);
      }
    } catch (err) {
      console.error('[SmartSuggestionList] Error:', err);
      setError(err.message || 'Error al obtener sugerencias');
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  };

  // Ordenar sugerencias según el estado de auto-sort
  const sortedSuggestions = useMemo(() => {
    if (!autoSortEnabled) {
      return suggestions;
    }
    // Ordenar por score descendente (mejor primero)
    return [...suggestions].sort((a, b) => b.score - a.score);
  }, [suggestions, autoSortEnabled]);

  // Manejar el toggle de auto-sort
  const handleToggleAutoSort = (enabled) => {
    setAutoSortEnabled(enabled);
  };

  // Reintentar carga
  const handleRetry = () => {
    generateSmartSuggestions();
  };

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold text-gray-300">
            Mejores opciones para esta ruta
          </h4>
        </div>
        <SuggestionsSkeleton count={3} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-red-500/30">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold text-gray-300">
            Mejores opciones para esta ruta
          </h4>
        </div>
        <div className="text-center py-4">
          <div className="text-red-400 text-sm mb-2">⚠️ {error}</div>
          <button
            onClick={handleRetry}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded transition-colors"
          >
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  if (sortedSuggestions.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold text-gray-300">
            Mejores opciones para esta ruta
          </h4>
        </div>
        <p className="text-xs text-gray-500 text-center py-4">
          No se encontraron sugerencias para esta ruta.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      {/* Header con título y toggle */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-gray-300">
          Mejores opciones para esta ruta
        </h4>
        <span className="text-xs text-gray-500">
          {sortedSuggestions.length} opciones
        </span>
      </div>

      {/* Toggle de auto-ordenación */}
      <div className="mb-4">
        <AutoSortToggle 
          enabled={autoSortEnabled} 
          onToggle={handleToggleAutoSort} 
        />
      </div>

      {/* Lista de sugerencias */}
      <div className="space-y-3">
        {sortedSuggestions.map((suggestion, index) => (
          <SmartSuggestionCard
            key={`${suggestion.bus_id}-${suggestion.position}-${index}`}
            suggestion={suggestion}
            rank={index + 1}
            onApply={() => onApply?.(suggestion)}
          />
        ))}
      </div>
    </div>
  );
}

export default SmartSuggestionList;
