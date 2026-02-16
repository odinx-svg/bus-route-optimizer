import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  DndContext,
  closestCorners,
  PointerSensor,
  KeyboardSensor,
  TouchSensor,
  useSensor,
  useSensors,
  DragOverlay,
  defaultDropAnimationSideEffects,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { RoutesPalette } from '../components/manual-schedule/RoutesPalette';
import { RouteCard } from '../components/manual-schedule/RouteCard';
import { WorkspaceBusRow } from '../components/manual-schedule/WorkspaceBusRow';
import { notifications } from '../services/notifications';

// Constantes
const STORAGE_KEY = 'manual_schedule_draft';
const DAY_LABELS = { L: 'Lunes', M: 'Martes', Mc: 'Miércoles', X: 'Jueves', V: 'Viernes' };
const ALL_DAYS = ['L', 'M', 'Mc', 'X', 'V'];

/**
 * ValidationSummary - Panel de validación global del horario
 */
function ValidationSummary({ buses, validations }) {
  const stats = useMemo(() => {
    const totalBuses = buses.length;
    const totalRoutes = buses.reduce((sum, bus) => sum + bus.routes.length, 0);
    const totalErrors = Object.values(validations).reduce((sum, v) => {
      return sum + (v.errors?.length || 0);
    }, 0);
    const totalWarnings = Object.values(validations).reduce((sum, v) => {
      return sum + (v.warnings?.length || 0);
    }, 0);

    return { totalBuses, totalRoutes, totalErrors, totalWarnings };
  }, [buses, validations]);

  const statusColor = stats.totalErrors > 0 ? 'red' : stats.totalWarnings > 0 ? 'amber' : 'green';
  
  const colors = {
    red: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', icon: 'text-red-500' },
    amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', icon: 'text-amber-500' },
    green: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400', icon: 'text-green-500' },
  };

  const theme = colors[statusColor];

  return (
    <div className={`mt-4 p-4 rounded-xl border ${theme.bg} ${theme.border}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-gray-800/50 ${theme.icon}`}>
            {stats.totalErrors > 0 ? (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            ) : stats.totalWarnings > 0 ? (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
          </div>
          <div>
            <h4 className={`font-semibold ${theme.text}`}>
              {stats.totalErrors > 0 
                ? 'Se encontraron errores de validación' 
                : stats.totalWarnings > 0 
                  ? 'Validación con advertencias' 
                  : 'Horario válido'}
            </h4>
            <p className="text-sm text-gray-400">
              {stats.totalBuses} buses • {stats.totalRoutes} rutas asignadas
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-4 text-sm">
          {stats.totalErrors > 0 && (
            <div className="flex items-center gap-1.5 text-red-400">
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
              <span>{stats.totalErrors} errores</span>
            </div>
          )}
          {stats.totalWarnings > 0 && (
            <div className="flex items-center gap-1.5 text-amber-400">
              <span className="w-2 h-2 rounded-full bg-amber-500"></span>
              <span>{stats.totalWarnings} advertencias</span>
            </div>
          )}
          {stats.totalErrors === 0 && stats.totalWarnings === 0 && (
            <div className="flex items-center gap-1.5 text-green-400">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              <span>Todo correcto</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * WorkspaceArea - Contenedor del área de trabajo
 */
function WorkspaceArea({ children, isOver }) {
  return (
    <div 
      className={`
        flex-1 overflow-y-auto rounded-xl bg-gray-900/30 border-2 border-dashed min-h-0
        ${isOver ? 'border-indigo-500/50 bg-indigo-500/5' : 'border-gray-700/50'}
        transition-all duration-200 p-4 space-y-3
      `}
    >
      {children}
    </div>
  );
}

/**
 * EmptyWorkspace - Estado vacío del workspace
 */
function EmptyWorkspace({ onAddBus }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center">
      <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
        <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
        </svg>
      </div>
      <h3 className="text-lg font-medium text-gray-300 mb-2">Sin buses asignados</h3>
      <p className="text-sm text-gray-500 mb-4 max-w-xs">
        Añade un bus para comenzar a construir el horario manualmente
      </p>
      <button
        onClick={onAddBus}
        className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        Añadir Bus
      </button>
    </div>
  );
}

/**
 * ManualSchedulePage - Página principal del constructor de horarios manual
 */
export function ManualSchedulePage({ routes = [], onSave }) {
  // Transformar rutas al formato del editor manual
  const transformRoutes = useMemo(() => {
    return routes.map(route => ({
      id: route.route_id || route.id,
      code: route.route_id || route.id || 'Sin código',
      startTime: route.start_time || route.departure_time || '00:00',
      endTime: route.end_time || route.arrival_time || '00:00',
      origin: route.origin || route.stops?.[0]?.name || 'Origen',
      destination: route.destination || route.stops?.[route.stops?.length - 1]?.name || 'Destino',
      type: route.type || (route.stops?.[0]?.type === 'entry' ? 'entry' : 'exit'),
      // Datos adicionales para OSRM
      startCoordinates: route.start_coordinates || route.stops?.[0]?.coordinates,
      endCoordinates: route.end_coordinates || route.stops?.[route.stops?.length - 1]?.coordinates,
    }));
  }, [routes]);

  // Estado principal
  const [buses, setBuses] = useState(() => {
    // Cargar desde localStorage si existe
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch {
          return [{ id: 'B001', routes: [], type: 'standard' }];
        }
      }
    }
    return [{ id: 'B001', routes: [], type: 'standard' }];
  });

  const [availableRoutes, setAvailableRoutes] = useState(transformRoutes);
  const [validationResults, setValidationResults] = useState({});
  const [activeDragItem, setActiveDragItem] = useState(null);
  const [isOverWorkspace, setIsOverWorkspace] = useState(false);
  const [activeDay, setActiveDay] = useState('L');
  const [isSaving, setIsSaving] = useState(false);

  // Filtrar rutas disponibles (no asignadas a ningún bus)
  const assignedRouteIds = useMemo(() => {
    const ids = new Set();
    buses.forEach(bus => {
      bus.routes.forEach(route => ids.add(route.id));
    });
    return ids;
  }, [buses]);

  const filteredAvailableRoutes = useMemo(() => {
    return availableRoutes.filter(route => !assignedRouteIds.has(route.id));
  }, [availableRoutes, assignedRouteIds]);

  // Actualizar availableRoutes cuando cambian las rutas de entrada
  useEffect(() => {
    if (transformRoutes.length > 0) {
      setAvailableRoutes(transformRoutes);
    }
  }, [transformRoutes]);

  // Auto-guardar en localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(buses));
    }
  }, [buses]);

  // Validar horario en tiempo real
  useEffect(() => {
    const validations = {};
    
    buses.forEach(bus => {
      const busValidations = { errors: [], warnings: [] };
      
      bus.routes.forEach((route, index) => {
        if (index === 0) return;
        
        const prevRoute = bus.routes[index - 1];
        const [endHour, endMin] = prevRoute.endTime.split(':').map(Number);
        const [startHour, startMin] = route.startTime.split(':').map(Number);
        
        const endTime = endHour * 60 + endMin;
        const startTime = startHour * 60 + startMin;
        const buffer = startTime - endTime;
        
        if (buffer < 0) {
          busValidations.errors.push({
            type: 'overlap',
            message: `Solapamiento entre ${prevRoute.code} y ${route.code}`,
            routeIndex: index,
          });
        } else if (buffer < 10) {
          busValidations.warnings.push({
            type: 'short_buffer',
            message: `Buffer corto (${buffer}min) entre ${prevRoute.code} y ${route.code}`,
            routeIndex: index,
          });
        }
      });
      
      validations[bus.id] = busValidations;
    });
    
    setValidationResults(validations);
  }, [buses]);

  // Sensores DnD
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 200, tolerance: 5 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Generar nuevo ID de bus
  const generateBusId = useCallback(() => {
    const existingNumbers = buses
      .map(b => parseInt(b.id.replace('B', '')))
      .filter(n => !isNaN(n));
    const maxNum = Math.max(0, ...existingNumbers);
    return `B${String(maxNum + 1).padStart(3, '0')}`;
  }, [buses]);

  // Handlers
  const handleAddBus = useCallback(() => {
    const newId = generateBusId();
    setBuses(prev => [...prev, { id: newId, routes: [], type: 'standard' }]);
    notifications.success('Bus añadido', `Bus ${newId} creado correctamente`);
  }, [generateBusId]);

  const handleRemoveBus = useCallback((busId) => {
    if (!confirm(`¿Eliminar el bus ${busId}?`)) return;
    
    setBuses(prev => {
      const bus = prev.find(b => b.id === busId);
      // Liberar rutas asignadas
      if (bus && bus.routes.length > 0) {
        // Las rutas vuelven a estar disponibles automáticamente
      }
      return prev.filter(b => b.id !== busId);
    });
  }, []);

  const handleDragStart = useCallback((event) => {
    const { active } = event;
    setActiveDragItem(active.data.current);
  }, []);

  const handleDragOver = useCallback((event) => {
    const { over } = event;
    setIsOverWorkspace(!!over);
  }, []);

  const handleDragEnd = useCallback((event) => {
    const { active, over } = event;
    setActiveDragItem(null);
    setIsOverWorkspace(false);

    if (!over) return;

    const activeData = active.data.current;
    const overId = over.id;

    // Determinar tipo de operación
    if (activeData?.type === 'route') {
      if (overId.startsWith('bus-')) {
        // Dropear en un bus
        const busId = overId.replace('bus-', '');
        handleDropRoute(activeData.route, busId);
      } else if (overId === 'workspace') {
        // Dropear en workspace vacío - crear nuevo bus
        const newId = generateBusId();
        setBuses(prev => [...prev, { id: newId, routes: [activeData.route], type: 'standard' }]);
      }
    }
  }, [generateBusId]);

  const handleDropRoute = useCallback((route, busId, position) => {
    setBuses(prev => prev.map(bus => {
      if (bus.id !== busId) return bus;
      
      // Verificar si la ruta ya está en este bus
      const exists = bus.routes.some(r => r.id === route.id);
      if (exists) return bus;
      
      const newRoutes = [...bus.routes];
      if (position !== undefined && position >= 0 && position <= newRoutes.length) {
        newRoutes.splice(position, 0, route);
      } else {
        newRoutes.push(route);
      }
      
      return { ...bus, routes: newRoutes };
    }));
  }, []);

  const handleRemoveRoute = useCallback((busId, routeId) => {
    setBuses(prev => prev.map(bus => {
      if (bus.id !== busId) return bus;
      return {
        ...bus,
        routes: bus.routes.filter(r => r.id !== routeId),
      };
    }));
  }, []);

  const handleMoveRoute = useCallback((fromBusId, toBusId, routeId, newIndex) => {
    if (fromBusId === toBusId) {
      // Reordenar dentro del mismo bus
      setBuses(prev => prev.map(bus => {
        if (bus.id !== fromBusId) return bus;
        const routes = [...bus.routes];
        const oldIndex = routes.findIndex(r => r.id === routeId);
        if (oldIndex === -1) return bus;
        
        const [route] = routes.splice(oldIndex, 1);
        routes.splice(newIndex, 0, route);
        return { ...bus, routes };
      }));
    } else {
      // Mover entre buses
      setBuses(prev => {
        const newBuses = prev.map(bus => ({ ...bus, routes: [...bus.routes] }));
        const fromBus = newBuses.find(b => b.id === fromBusId);
        const toBus = newBuses.find(b => b.id === toBusId);
        
        if (!fromBus || !toBus) return prev;
        
        const routeIndex = fromBus.routes.findIndex(r => r.id === routeId);
        if (routeIndex === -1) return prev;
        
        const [route] = fromBus.routes.splice(routeIndex, 1);
        
        if (newIndex !== undefined && newIndex >= 0) {
          toBus.routes.splice(newIndex, 0, route);
        } else {
          toBus.routes.push(route);
        }
        
        return newBuses;
      });
    }
  }, []);

  const handleClearAll = useCallback(() => {
    if (!confirm('¿Limpiar todo el horario? Esto eliminará todas las asignaciones.')) return;
    setBuses(prev => prev.map(bus => ({ ...bus, routes: [] })));
    notifications.info('Horario limpiado', 'Todas las asignaciones han sido eliminadas');
  }, []);

  const handleSaveSchedule = useCallback(async () => {
    // Verificar errores antes de guardar
    const hasErrors = Object.values(validationResults).some(v => v.errors?.length > 0);
    if (hasErrors) {
      notifications.error('No se puede guardar', 'Corrige los errores de validación primero');
      return;
    }

    setIsSaving(true);
    const loadingToast = notifications.loading('Guardando horario...');

    try {
      // Preparar datos en formato schedule
      const scheduleData = {
        day: activeDay,
        buses: buses.map(bus => ({
          bus_id: bus.id,
          items: bus.routes.map((route, index) => ({
            route_id: route.id,
            route_code: route.code,
            start_time: route.startTime,
            end_time: route.endTime,
            origin: route.origin,
            destination: route.destination,
            type: route.type,
            order: index,
          })),
        })),
        stats: {
          total_buses: buses.length,
          total_routes: buses.reduce((sum, b) => sum + b.routes.length, 0),
          total_duration: buses.reduce((sum, b) => {
            return sum + b.routes.reduce((routeSum, r) => {
              const [sh, sm] = r.startTime.split(':').map(Number);
              const [eh, em] = r.endTime.split(':').map(Number);
              const start = sh * 60 + sm;
              const end = eh * 60 + em;
              return routeSum + (end >= start ? end - start : (24 * 60 - start) + end);
            }, 0);
          }, 0),
        },
      };

      // Enviar a backend si hay callback
      if (onSave) {
        await onSave(scheduleData);
      }

      // Guardar en localStorage como schedule definitivo
      localStorage.setItem('manual_schedule_final', JSON.stringify(scheduleData));
      
      notifications.dismiss(loadingToast);
      notifications.success('Horario guardado', 'El horario manual ha sido guardado correctamente');
    } catch (error) {
      console.error('Error saving schedule:', error);
      notifications.dismiss(loadingToast);
      notifications.error('Error al guardar', error.message || 'Ocurrió un error al guardar el horario');
    } finally {
      setIsSaving(false);
    }
  }, [buses, activeDay, validationResults, onSave]);

  // Renderizar overlay de arrastre
  const renderDragOverlay = useCallback((item) => {
    if (!item) return null;
    
    if (item.type === 'route') {
      return (
        <div className="transform rotate-3 scale-105">
          <RouteCard route={item.route} isDragging={true} />
        </div>
      );
    }
    
    return null;
  }, []);

  // Animation config
  const dropAnimation = {
    sideEffects: defaultDropAnimationSideEffects({
      styles: { active: { opacity: '0.5' } },
    }),
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="flex h-[calc(100vh-120px)] bg-[#0e0e10] rounded-xl overflow-hidden">
        {/* Panel izquierdo: Rutas disponibles */}
        <div className="w-80 flex-shrink-0 p-4 border-r border-gray-800 overflow-y-auto">
          <RoutesPalette 
            routes={filteredAvailableRoutes}
            title="Rutas Disponibles"
          />
        </div>

        {/* Área central: Workspace */}
        <div className="flex-1 flex flex-col p-4 min-w-0 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-bold text-white flex items-center gap-2">
                <svg className="w-6 h-6 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                Constructor de Horarios
              </h1>
              
              {/* Selector de día */}
              <div className="flex items-center gap-1 bg-gray-800 rounded-lg p-1">
                {ALL_DAYS.map(day => (
                  <button
                    key={day}
                    onClick={() => setActiveDay(day)}
                    className={`
                      px-3 py-1.5 rounded-md text-xs font-medium transition-all
                      ${activeDay === day 
                        ? 'bg-indigo-500 text-white' 
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
                      }
                    `}
                    title={DAY_LABELS[day]}
                  >
                    {day}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleClearAll}
                disabled={buses.every(b => b.routes.length === 0)}
                className="
                  px-3 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed
                  text-gray-300 rounded-lg text-sm font-medium transition-colors
                  flex items-center gap-2
                "
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Limpiar
              </button>
              
              <button
                onClick={handleAddBus}
                className="
                  px-3 py-2 bg-gray-800 hover:bg-gray-700 
                  text-white rounded-lg text-sm font-medium transition-colors
                  flex items-center gap-2
                "
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Añadir Bus
              </button>
              
              <button
                onClick={handleSaveSchedule}
                disabled={isSaving || buses.every(b => b.routes.length === 0)}
                className="
                  px-4 py-2 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed
                  text-white rounded-lg text-sm font-medium transition-colors
                  flex items-center gap-2 shadow-lg shadow-indigo-500/20
                "
              >
                {isSaving ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Guardando...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                    </svg>
                    Guardar Horario
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Workspace */}
          <WorkspaceArea isOver={isOverWorkspace}>
            {buses.length === 0 ? (
              <EmptyWorkspace onAddBus={handleAddBus} />
            ) : (
              <SortableContext 
                items={buses.map(b => b.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-3">
                  {buses.map((bus, index) => (
                    <div key={bus.id} className="relative group">
                      <WorkspaceBusRow
                        bus={bus}
                        routes={bus.routes}
                        validations={validationResults[bus.id]}
                        onDrop={(route, pos) => handleDropRoute(route, bus.id, pos)}
                        onRemoveRoute={(routeId) => handleRemoveRoute(bus.id, routeId)}
                      />
                      
                      {/* Botón eliminar bus */}
                      <button
                        onClick={() => handleRemoveBus(bus.id)}
                        className="
                          absolute -right-2 top-1/2 -translate-y-1/2 
                          w-6 h-6 rounded-full bg-red-500 text-white
                          opacity-0 group-hover:opacity-100 transition-opacity
                          flex items-center justify-center shadow-lg
                          hover:bg-red-600
                        "
                        title="Eliminar bus"
                      >
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </SortableContext>
            )}
          </WorkspaceArea>

          {/* Panel de validación global */}
          {buses.length > 0 && (
            <ValidationSummary 
              buses={buses} 
              validations={validationResults} 
            />
          )}
        </div>
      </div>

      {/* DragOverlay para preview de arrastre */}
      <DragOverlay dropAnimation={dropAnimation}>
        {activeDragItem && renderDragOverlay(activeDragItem)}
      </DragOverlay>
    </DndContext>
  );
}

export default ManualSchedulePage;
