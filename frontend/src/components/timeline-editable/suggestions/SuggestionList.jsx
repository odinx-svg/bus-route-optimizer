import { useTimelineEditableStore } from '../../../stores/timelineEditableStore';
import { SuggestionCard } from './SuggestionCard';

export function SuggestionList({ routeId }) {
  const { activeSuggestions, applySuggestion } = useTimelineEditableStore();
  
  const suggestions = activeSuggestions
    .filter(s => s.routeId === routeId)
    .sort((a, b) => b.score - a.score);
  
  if (suggestions.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-300 mb-2">
          Mejores opciones para esta ruta:
        </h4>
        <p className="text-xs text-gray-500 text-center py-2">
          Generando sugerencias...
        </p>
      </div>
    );
  }
  
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-300 mb-2">
        Mejores opciones para esta ruta:
      </h4>
      
      <div className="space-y-2">
        {suggestions.map((suggestion, index) => (
          <SuggestionCard 
            key={index}
            suggestion={suggestion}
            rank={index + 1}
            onApply={() => applySuggestion(suggestion)}
          />
        ))}
      </div>
    </div>
  );
}
