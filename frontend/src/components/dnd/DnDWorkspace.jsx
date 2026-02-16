/**
 * DnDWorkspace - Área de trabajo completa con sistema DnD
 * 
 * Integra:
 * - RoutesPalette: Lista de rutas disponibles para arrastrar
 * - DndProvider: Contexto de drag & drop
 * - BusRow/BusColumn: Zonas de drop para los buses
 * - DragOverlay: Preview visual al arrastrar
 */
import React, { useState, useCallback } from 'react';
import { DndProvider } from './DndProvider';
import { DraggableRouteCard, DraggableRouteCardPreview } from './DraggableRouteCard';
import { BusRow } from './BusRow';
import { DropZone } from './DropZone';
import { useDragAndDrop, useRoutePalette } from '../../hooks/useDragAndDrop';
import { Bus, Route, Search, Filter } from 'lucide-react';

/**
 * RoutesPalette - Panel lateral con rutas disponibles
 */
function RoutesPalette({ 
  routes, 
  filter, 
  setFilter, 
  searchQuery, 
  setSearchQuery,
  title = "Rutas Disponibles" 
}) {
  const filters = [
    { key: 'all', label: 'Todas', color: 'zinc' },
    { key: 'entry', label: 'Entradas', color: 'indigo' },
    { key: 'exit', label: 'Salidas', color: 'amber' },
  ];

  return (
    <div className="flex flex-col h-full w-[300px] bg-zinc-900/50 border-r border-white/[0.04]">
      {/* Header */}
      <div className="p-4 border-b border-white/[0.04]">
        <div className="flex items-center gap-2 mb-3">
          <Route className="w-4 h-4 text-indigo-400" />
          <h3 className="font-medium text-[14px] text-white">{title}</h3>
          <span className="ml-auto text-[11px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-500">
            {routes.length}
          </span>
        </div>

        {/* Search */}
        <div className="relative mb-3">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Buscar rutas..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-zinc-800/50 border border-white/[0.06]
                       text-[12px] text-white placeholder-zinc-600
                       focus:outline-none focus:border-indigo-500/30 focus:ring-1 focus:ring-indigo-500/20"
          />
        </div>

        {/* Filters */}
        <div className="flex gap-1">
          {filters.map(({ key, label, color }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`
                flex-1 py-1.5 px-2 rounded-md text-[11px] font-medium transition-all duration-150
                ${filter === key 
                  ? `bg-${color}-500/10 text-${color}-400 ring-1 ring-${color}-500/20` 
                  : 'bg-transparent text-zinc-500 hover:bg-white/[0.03]'
                }
              `}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Routes list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {routes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-zinc-600">
            <Route className="w-8 h-8 mb-2 opacity-30" />
            <span className="text-[11px]">No hay rutas disponibles</span>
          </div>
        ) : (
          routes.map((route) => (
            <DraggableRouteCard
              key={route.id || route.route_id}
              route={route}
            />
          ))
        )}
      </div>

      {/* Footer tip */}
      <div className="p-3 border-t border-white/[0.04]">
        <p className="text-[10px] text-zinc-600 text-center">
          Arrastra las rutas hacia los buses
        </p>
      </div>
    </div>
  );
}

/**
 * BusesArea - Área con los buses como zonas de drop
 */
function BusesArea({ 
  buses, 
  schedule, 
  onRouteRemove,
  validationErrors 
}) {
  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="max-w-4xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Bus className="w-4 h-4 text-indigo-400" />
            <h3 className="font-medium text-[14px] text-white">Buses Asignados</h3>
          </div>
          <span className="text-[11px] text-zinc-500">
            {buses.length} buses
          </span>
        </div>

        {/* Buses grid */}
        <div className="grid gap-4">
          {buses.map((bus) => {
            const busSchedule = schedule.find(b => (b.bus_id || b.id) === bus.id);
            const assignedRoutes = busSchedule?.items || [];
            const validationStatus = validationErrors[bus.id] 
              ? { isValid: false, message: validationErrors[bus.id] }
              : null;

            return (
              <BusRow
                key={bus.id}
                bus={bus}
                assignedRoutes={assignedRoutes}
                onRouteRemove={(routeId) => onRouteRemove(bus.id, routeId)}
                validationStatus={validationStatus}
              />
            );
          })}
        </div>

        {/* Drop zone for new bus */}
        {buses.length === 0 && (
          <DropZone
            id="new-bus-zone"
            variant="dashed"
            emptyText="Arrastra rutas aquí para crear un nuevo bus"
            overText="Suelta para crear nuevo bus"
            minHeight="200px"
            className="flex items-center justify-center"
          />
        )}
      </div>
    </div>
  );
}

/**
 * Componente principal del workspace DnD
 */
export function DnDWorkspace({
  initialBuses = [],
  initialRoutes = [],
  onScheduleChange,
  onValidationError,
  validateCompatibility,
}) {
  // Estado del palette
  const palette = useRoutePalette(initialRoutes);
  
  // Estado del DnD
  const dnd = useDragAndDrop({
    initialSchedule: initialBuses.map(bus => ({
      ...bus,
      items: bus.items || [],
    })),
    onScheduleChange,
    onValidationError,
    validateCompatibility,
  });

  // Renderizador del overlay
  const renderDragOverlay = useCallback((dragItem) => {
    if (dragItem.type === 'route') {
      return <DraggableRouteCardPreview route={dragItem.route} />;
    }
    return null;
  }, []);

  // Manejar cuando se agrega una ruta a un bus
  const handleRouteAssigned = useCallback((busId, route) => {
    dnd.addRouteToBus(busId, route);
    palette.removeRoute(route.id || route.route_id);
  }, [dnd, palette]);

  // Manejar cuando se remueve una ruta de un bus
  const handleRouteRemoved = useCallback((busId, routeId) => {
    const bus = dnd.schedule.find(b => (b.bus_id || b.id) === busId);
    const route = bus?.items?.find(r => (r.route_id || r.id) === routeId);
    
    if (route) {
      dnd.removeRouteFromBus(busId, routeId);
      palette.restoreRoute(route);
    }
  }, [dnd, palette]);

  return (
    <DndProvider
      onDragStart={dnd.handleDragStart}
      onDragOver={dnd.handleDragOver}
      onDragEnd={(event) => {
        dnd.handleDragEnd(event);
        
        // Lógica adicional para manejar asignación desde palette
        const { active, over } = event;
        if (over && active.data.current?.type === 'route') {
          const overData = over.data.current;
          if (overData?.type === 'bus') {
            handleRouteAssigned(overData.busId, active.data.current.route);
          }
        }
      }}
      dragOverlayRenderer={renderDragOverlay}
    >
      <div className="flex h-full bg-zinc-950">
        {/* Palette de rutas */}
        <RoutesPalette
          routes={palette.filteredRoutes}
          filter={palette.filter}
          setFilter={palette.setFilter}
          searchQuery={palette.searchQuery}
          setSearchQuery={palette.setSearchQuery}
        />

        {/* Área de buses */}
        <BusesArea
          buses={initialBuses}
          schedule={dnd.schedule}
          onRouteRemove={handleRouteRemoved}
          validationErrors={dnd.validationErrors}
        />
      </div>
    </DndProvider>
  );
}

export default DnDWorkspace;
