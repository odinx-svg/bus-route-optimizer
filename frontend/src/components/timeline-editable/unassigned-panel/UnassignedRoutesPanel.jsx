import { useState, useEffect } from 'react';
import { useTimelineEditableStore } from '../../../stores/timelineEditableStore';
import { DraggableUnassignedRoute } from './DraggableUnassignedRoute';
import { SuggestionList } from '../suggestions/SuggestionList';

export function UnassignedRoutesPanel() {
  const { unassignedRoutes, generateSuggestions } = useTimelineEditableStore();
  const [selectedRoute, setSelectedRoute] = useState(null);
  
  // Generar sugerencias al seleccionar una ruta
  useEffect(() => {
    if (selectedRoute) {
      generateSuggestions(selectedRoute.route_id);
    }
  }, [selectedRoute, generateSuggestions]);
  
  if (unassignedRoutes.length === 0 && !selectedRoute) {
    return (
      <div className="w-64 p-4 bg-gray-800 rounded-lg text-gray-500 text-center">
        <p className="text-sm">Arrastra rutas aquí para liberarlas</p>
      </div>
    );
  }
  
  return (
    <div className="w-80 flex flex-col gap-4">
      {/* Lista de rutas libres */}
      <div className="bg-gray-800 rounded-lg p-3">
        <h3 className="text-sm font-semibold text-white mb-3">
          Rutas Libres ({unassignedRoutes.length})
        </h3>
        
        <div className="space-y-2 max-h-60 overflow-y-auto">
          {unassignedRoutes.map(route => (
            <DraggableUnassignedRoute 
              key={route.route_id}
              route={route}
              isSelected={selectedRoute?.route_id === route.route_id}
              onClick={() => setSelectedRoute(route)}
            />
          ))}
        </div>
      </div>
      
      {/* Sugerencias para la ruta seleccionada */}
      {selectedRoute && (
        <SuggestionList routeId={selectedRoute.route_id} />
      )}
    </div>
  );
}
