/**
 * UnassignedPanel - Panel de rutas libres estilo "palette"
 * 
 * Similar al ManualSchedule, muestra las rutas no asignadas
 * como piezas que se pueden arrastrar al timeline.
 */

import { useDroppable } from '@dnd-kit/core';
import { RouteLego } from './RouteLego';
import { PackageOpen, Filter, Search, X } from 'lucide-react';
import { useTimelineEditableStore } from '../../stores/timelineEditableStore';
import { useState, useMemo } from 'react';

export function UnassignedPanel() {
  const { 
    unassignedRoutes, 
    selectedRouteIds,
    selectRoute,
    clearSelection 
  } = useTimelineEditableStore();

  const { isOver, setNodeRef } = useDroppable({
    id: 'unassigned-panel',
    data: { type: 'unassigned' }
  });

  const [filter, setFilter] = useState('all'); // 'all' | 'entry' | 'exit'
  const [searchTerm, setSearchTerm] = useState('');

  const hasRoutes = unassignedRoutes.length > 0;

  // Filtrar rutas
  const filteredRoutes = useMemo(() => {
    return unassignedRoutes.filter(route => {
      // Filtro por tipo
      if (filter !== 'all' && route.type !== filter) return false;
      
      // Filtro por búsqueda
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        const schoolMatch = (route.school || '').toLowerCase().includes(term);
        const codeMatch = (route.route_code || '').toLowerCase().includes(term);
        return schoolMatch || codeMatch;
      }
      
      return true;
    });
  }, [unassignedRoutes, filter, searchTerm]);

  // Estadísticas
  const entryCount = unassignedRoutes.filter(r => r.type === 'entry').length;
  const exitCount = unassignedRoutes.filter(r => r.type === 'exit').length;

  const handleRouteClick = (route) => {
    selectRoute(route.route_id);
  };

  return (
    <div 
      ref={setNodeRef}
      className={`
        w-80 bg-[#13131a] border-r border-gray-800 flex flex-col
        ${isOver ? 'bg-indigo-500/5' : ''}
        transition-colors duration-150
      `}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <PackageOpen className="w-4 h-4 text-gray-400" />
            Rutas Libres
          </h3>
          <span className={`
            text-xs px-2 py-0.5 rounded-full font-medium
            ${unassignedRoutes.length > 0 ? 'bg-amber-500/20 text-amber-400' : 'bg-green-500/20 text-green-400'}
          `}>
            {unassignedRoutes.length}
          </span>
        </div>
        
        <p className="text-gray-500 text-xs">
          Arrastra las rutas al timeline para asignarlas
        </p>
      </div>

      {/* Búsqueda */}
      {hasRoutes && (
        <div className="px-4 py-3 border-b border-gray-800">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Buscar ruta..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[#0a0a0f] border border-gray-800 rounded-lg pl-9 pr-8 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-gray-700"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-400"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Filtros rápidos */}
      {hasRoutes && (
        <div className="px-4 py-2 border-b border-gray-800 flex gap-2">
          <button
            onClick={() => setFilter('all')}
            className={`
              text-xs px-3 py-1.5 rounded-lg font-medium transition-colors
              ${filter === 'all' 
                ? 'bg-gray-700 text-white' 
                : 'bg-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800'}
            `}
          >
            Todas
          </button>
          <button
            onClick={() => setFilter('entry')}
            className={`
              text-xs px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1
              ${filter === 'entry' 
                ? 'bg-blue-500/20 text-blue-400' 
                : 'bg-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800'}
            `}
          >
            Entradas
            {entryCount > 0 && (
              <span className="bg-blue-500/30 text-blue-300 px-1.5 rounded-full text-[10px]">
                {entryCount}
              </span>
            )}
          </button>
          <button
            onClick={() => setFilter('exit')}
            className={`
              text-xs px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1
              ${filter === 'exit' 
                ? 'bg-amber-500/20 text-amber-400' 
                : 'bg-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800'}
            `}
          >
            Salidas
            {exitCount > 0 && (
              <span className="bg-amber-500/30 text-amber-300 px-1.5 rounded-full text-[10px]">
                {exitCount}
              </span>
            )}
          </button>
        </div>
      )}

      {/* Lista de rutas */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {!hasRoutes ? (
          <div className="text-center py-12">
            <div className="w-14 h-14 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <PackageOpen className="w-7 h-7 text-green-500" />
            </div>
            <p className="text-gray-400 text-sm font-medium">Todas las rutas están asignadas</p>
            <p className="text-gray-600 text-xs mt-1">
              Excelente trabajo organizando el horario
            </p>
          </div>
        ) : filteredRoutes.length === 0 ? (
          <div className="text-center py-8">
            <Filter className="w-8 h-8 text-gray-600 mx-auto mb-2" />
            <p className="text-gray-500 text-sm">No hay rutas que coincidan</p>
            <button
              onClick={() => { setFilter('all'); setSearchTerm(''); }}
              className="text-indigo-400 text-xs mt-2 hover:text-indigo-300"
            >
              Limpiar filtros
            </button>
          </div>
        ) : (
          filteredRoutes.map(route => (
            <RouteLego
              key={route.route_id}
              route={route}
              isSelected={selectedRouteIds.includes(route.route_id)}
              onClick={handleRouteClick}
            />
          ))
        )}
      </div>

      {/* Footer con estadísticas */}
      {hasRoutes && (
        <div className="p-3 border-t border-gray-800 bg-[#0f0f14]">
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-500">
              {filteredRoutes.length} de {unassignedRoutes.length} mostradas
            </span>
            {selectedRouteIds.length > 0 && (
              <button
                onClick={clearSelection}
                className="text-indigo-400 hover:text-indigo-300"
              >
                Limpiar selección
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default UnassignedPanel;
