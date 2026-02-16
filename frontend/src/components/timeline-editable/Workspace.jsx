/**
 * Workspace - Vista principal del editor de horarios
 * 
 * Layout:
 * - Header: Título, contadores, controles de zoom/filtros, botones de acción
 * - Sidebar izquierda: Rutas libres (estilo piezas de lego arrastrables)
 * - Canvas central: Timeline con buses como filas
 * - Sidebar derecha: Detalles de ruta seleccionada + sugerencias
 * 
 * Inspirado en: Figma, N8N, Linear, Notion
 */

import { useState, useRef, useCallback, useMemo } from 'react';
import { DndContext, PointerSensor, TouchSensor, useSensor, useSensors, DragOverlay } from '@dnd-kit/core';
import { useTimelineEditableStore } from '../../stores/timelineEditableStore';
import { RouteLego } from './RouteLego';
import { BusTrack } from './BusTrack';
import { WorkspaceToolbar } from './WorkspaceToolbar';
import { UnassignedPanel } from './UnassignedPanel';
import { RouteDetailsPanel } from './RouteDetailsPanel';
import { RouteEditorDrawer } from './RouteEditorDrawer';

export function Workspace({ onSave }) {
  const { 
    buses, 
    unassignedRoutes, 
    selectedRouteIds,
    moveRoute,
    selectRoute,
    addBus
  } = useTimelineEditableStore();
  
  const [zoom, setZoom] = useState(1);
  const [viewMode, setViewMode] = useState('timeline'); // 'timeline' | 'compact'
  const [activeDragId, setActiveDragId] = useState(null);
  const [selectedRouteForEdit, setSelectedRouteForEdit] = useState(null);
  const containerRef = useRef(null);

  // Calcular rango de horas basado en las rutas
  const timeRange = useMemo(() => calculateTimeRange(buses), [buses]);

  // Sensores para drag & drop
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 }
    }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 250, tolerance: 5 }
    })
  );

  // Handlers de drag & drop
  const handleDragStart = useCallback((event) => {
    setActiveDragId(event.active.id);
  }, []);

  const handleDragEnd = useCallback((event) => {
    const { active, over } = event;
    setActiveDragId(null);
    
    if (!over) return;
    
    const activeData = active.data.current;
    const overData = over.data.current;
    
    if (!activeData || !overData) return;
    
    if (activeData.type === 'route') {
      const routeId = activeData.route.route_id || activeData.route.id;
      
      if (overData.type === 'bus') {
        moveRoute(routeId, overData.busId);
      } else if (overData.type === 'unassigned') {
        moveRoute(routeId, null);
      } else if (overData.type === 'hour-zone' && overData.busId) {
        // Drop en zona horaria específica
        const targetTime = minutesToTime(overData.hour * 60);
        moveRoute(routeId, overData.busId, undefined, targetTime);
      }
    }
  }, [moveRoute]);

  // Encontrar ruta activa para DragOverlay
  const activeRoute = useMemo(() => {
    if (!activeDragId) return null;
    const routeId = activeDragId.replace('route-', '');
    return buses.flatMap(b => b.routes).find(r => r.route_id === routeId) ||
           unassignedRoutes.find(r => r.route_id === routeId);
  }, [activeDragId, buses, unassignedRoutes]);

  const selectedRoute = selectedRouteIds.length > 0 
    ? buses.flatMap(b => b.routes).find(r => r.route_id === selectedRouteIds[0]) ||
      unassignedRoutes.find(r => r.route_id === selectedRouteIds[0])
    : null;

  const handleAddBus = useCallback(() => {
    addBus();
  }, [addBus]);

  const handleSave = useCallback(() => {
    onSave?.({
      buses,
      unassignedRoutes,
      timestamp: new Date().toISOString()
    });
  }, [buses, unassignedRoutes, onSave]);

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="h-full flex flex-col bg-[#0a0a0f]">
        {/* Header con toolbar */}
        <WorkspaceToolbar 
          buses={buses}
          unassignedRoutes={unassignedRoutes}
          zoom={zoom}
          onZoomChange={setZoom}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          onAddBus={handleAddBus}
          onSave={handleSave}
          timeRange={timeRange}
        />

        {/* Área principal */}
        <div className="flex-1 flex overflow-hidden">
          {/* Panel izquierdo: Rutas libres */}
          <UnassignedPanel />

          {/* Canvas central */}
          <div 
            ref={containerRef}
            className="flex-1 overflow-auto bg-[#0a0a0f] relative"
          >
            <TimelineCanvas
              buses={buses}
              timeRange={timeRange}
              zoom={zoom}
              viewMode={viewMode}
              onRouteClick={setSelectedRouteForEdit}
            />
          </div>

          {/* Panel derecho: Detalles */}
          <RouteDetailsPanel 
            route={selectedRoute}
          />
        </div>
      </div>

      {/* Drag Overlay para mostrar el item arrastrado */}
      <DragOverlay>
        {activeRoute ? (
          <div className="opacity-90 scale-105">
            <RouteLego
              route={activeRoute}
              isDragging={true}
            />
          </div>
        ) : null}
      </DragOverlay>

      {/* Drawer de edición de ruta */}
      <RouteEditorDrawer
        route={selectedRouteForEdit}
        isOpen={!!selectedRouteForEdit}
        onClose={() => setSelectedRouteForEdit(null)}
      />
    </DndContext>
  );
}

// Componente TimelineCanvas con las filas de buses
function TimelineCanvas({ buses, timeRange, zoom, viewMode, onRouteClick }) {
  const pixelsPerMinute = 2 * zoom; // 2px por minuto por defecto
  const totalMinutes = (timeRange.end - timeRange.start) * 60;
  const canvasWidth = totalMinutes * pixelsPerMinute;

  return (
    <div 
      className="relative min-h-full"
      style={{ width: Math.max(canvasWidth, 800) }}
    >
      {/* Grid de horas */}
      <TimeGrid 
        startHour={timeRange.start}
        endHour={timeRange.end}
        pixelsPerMinute={pixelsPerMinute}
      />

      {/* Filas de buses */}
      <div className="space-y-2 p-4">
        {buses.map((bus, index) => (
          <BusTrack
            key={bus.busId}
            bus={bus}
            index={index}
            timeRange={timeRange}
            pixelsPerMinute={pixelsPerMinute}
            viewMode={viewMode}
            onRouteClick={onRouteClick}
          />
        ))}

        {buses.length === 0 && (
          <div className="text-center py-12 text-gray-500 border border-dashed border-gray-700 rounded-lg">
            <p>No hay buses en el horario</p>
            <p className="text-sm mt-1">Haz clic en "+ Bus" para agregar uno</p>
          </div>
        )}
      </div>
    </div>
  );
}

// Grid de horas en la parte superior
function TimeGrid({ startHour, endHour, pixelsPerMinute }) {
  const hours = [];
  for (let h = startHour; h <= endHour; h++) {
    hours.push(h);
  }

  return (
    <div className="sticky top-0 z-20 bg-[#0a0a0f] border-b border-gray-800 h-10 flex">
      {hours.map(hour => (
        <div
          key={hour}
          className="flex-shrink-0 border-r border-gray-800 flex items-center justify-center text-xs text-gray-500 font-mono"
          style={{ width: 60 * pixelsPerMinute }}
        >
          {String(hour).padStart(2, '0')}:00
        </div>
      ))}
    </div>
  );
}

// Calcular rango de horas basado en todas las rutas
function calculateTimeRange(buses) {
  // Valores por defecto
  let minTime = 24 * 60;
  let maxTime = 0;
  let hasRoutes = false;

  buses.forEach(bus => {
    bus.routes.forEach(route => {
      hasRoutes = true;
      const [startH, startM] = (route.currentStartTime || route.start_time).split(':').map(Number);
      const [endH, endM] = (route.currentEndTime || route.end_time).split(':').map(Number);
      minTime = Math.min(minTime, startH * 60 + startM);
      maxTime = Math.max(maxTime, endH * 60 + endM);
    });
  });

  // Si no hay rutas, usar valores por defecto
  if (!hasRoutes) {
    return { start: 6, end: 22 };
  }

  return {
    start: Math.max(0, Math.floor(minTime / 60) - 1),
    end: Math.min(24, Math.ceil(maxTime / 60) + 1)
  };
}

// Convertir minutos a tiempo HH:mm
function minutesToTime(minutes) {
  const hrs = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

export default Workspace;
