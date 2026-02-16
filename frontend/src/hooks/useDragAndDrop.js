/**
 * useDragAndDrop - Hook personalizado para manejar lógica DnD
 * 
 * Proporciona:
 * - Funciones helper para mover rutas entre buses
 * - Validación de compatibilidad
 * - Persistencia de estado
 * - Callbacks configurables
 */
import { useState, useCallback, useRef } from 'react';
import { arrayMove } from '@dnd-kit/sortable';

/**
 * Hook principal para gestionar operaciones DnD
 */
export function useDragAndDrop({
  initialSchedule = [],
  onScheduleChange,
  onValidationError,
  validateCompatibility,
}) {
  const [schedule, setSchedule] = useState(initialSchedule);
  const [isDragging, setIsDragging] = useState(false);
  const [dragPreview, setDragPreview] = useState(null);
  const [validationErrors, setValidationErrors] = useState({});
  
  // Ref para prevenir actualizaciones duplicadas
  const updateTimeoutRef = useRef(null);

  /**
   * Encontrar el bus y la ruta por sus IDs
   */
  const findRouteLocation = useCallback((routeId) => {
    for (const bus of schedule) {
      const routeIndex = bus.items?.findIndex(r => r.route_id === routeId || r.id === routeId);
      if (routeIndex !== -1) {
        return { busId: bus.bus_id || bus.id, routeIndex, route: bus.items[routeIndex] };
      }
    }
    return null;
  }, [schedule]);

  /**
   * Mover una ruta dentro del mismo bus (reordenar)
   */
  const reorderWithinBus = useCallback((busId, oldIndex, newIndex) => {
    setSchedule(prev => {
      const newSchedule = [...prev];
      const bus = newSchedule.find(b => (b.bus_id || b.id) === busId);
      if (!bus || !bus.items) return prev;
      
      bus.items = arrayMove(bus.items, oldIndex, newIndex);
      return newSchedule;
    });
  }, []);

  /**
   * Mover una ruta de un bus a otro
   */
  const moveRouteBetweenBuses = useCallback((fromBusId, toBusId, routeId, targetIndex = null) => {
    setSchedule(prev => {
      const newSchedule = JSON.parse(JSON.stringify(prev)); // Deep copy
      
      const fromBus = newSchedule.find(b => (b.bus_id || b.id) === fromBusId);
      const toBus = newSchedule.find(b => (b.bus_id || b.id) === toBusId);
      
      if (!fromBus || !toBus) return prev;
      
      const routeIndex = fromBus.items?.findIndex(r => (r.route_id || r.id) === routeId);
      if (routeIndex === -1) return prev;
      
      // Extraer la ruta
      const [route] = fromBus.items.splice(routeIndex, 1);
      
      // Agregar al bus destino
      if (!toBus.items) toBus.items = [];
      
      if (targetIndex !== null && targetIndex >= 0 && targetIndex <= toBus.items.length) {
        toBus.items.splice(targetIndex, 0, route);
      } else {
        toBus.items.push(route);
      }
      
      // Limpiar buses vacíos si es necesario
      // return newSchedule.filter(b => b.items?.length > 0);
      
      return newSchedule;
    });
  }, []);

  /**
   * Agregar una ruta nueva a un bus (desde palette)
   */
  const addRouteToBus = useCallback((busId, route, index = null) => {
    setSchedule(prev => {
      const newSchedule = JSON.parse(JSON.stringify(prev));
      const bus = newSchedule.find(b => (b.bus_id || b.id) === busId);
      
      if (!bus) return prev;
      if (!bus.items) bus.items = [];
      
      // Asegurar que la ruta tenga el formato correcto
      const normalizedRoute = {
        ...route,
        route_id: route.route_id || route.id,
      };
      
      if (index !== null && index >= 0 && index <= bus.items.length) {
        bus.items.splice(index, 0, normalizedRoute);
      } else {
        bus.items.push(normalizedRoute);
      }
      
      return newSchedule;
    });
  }, []);

  /**
   * Remover una ruta de un bus
   */
  const removeRouteFromBus = useCallback((busId, routeId) => {
    setSchedule(prev => {
      const newSchedule = JSON.parse(JSON.stringify(prev));
      const bus = newSchedule.find(b => (b.bus_id || b.id) === busId);
      
      if (!bus || !bus.items) return prev;
      
      bus.items = bus.items.filter(r => (r.route_id || r.id) !== routeId);
      
      return newSchedule;
    });
  }, []);

  /**
   * Validar si una ruta puede ser agregada a un bus
   */
  const validateRouteCompatibility = useCallback(async (busId, route) => {
    if (!validateCompatibility) return { isValid: true };
    
    try {
      const result = await validateCompatibility(busId, route);
      
      setValidationErrors(prev => ({
        ...prev,
        [busId]: result.isValid ? null : result.message,
      }));
      
      return result;
    } catch (error) {
      console.error('Error validando compatibilidad:', error);
      return { isValid: false, message: 'Error de validación' };
    }
  }, [validateCompatibility]);

  /**
   * Manejador de inicio de drag
   */
  const handleDragStart = useCallback((event) => {
    const { active } = event;
    setIsDragging(true);
    setDragPreview(active.data.current);
  }, []);

  /**
   * Manejador de drag over
   */
  const handleDragOver = useCallback((event) => {
    const { active, over } = event;
    
    if (!over) return;
    
    // Aquí se pueden agregar efectos de preview o validación en tiempo real
  }, []);

  /**
   * Manejador de fin de drag (lógica principal)
   */
  const handleDragEnd = useCallback((event) => {
    const { active, over } = event;
    
    setIsDragging(false);
    setDragPreview(null);
    
    if (!over) return;
    
    const activeData = active.data.current;
    const overData = over.data.current;
    
    if (!activeData || !overData) return;
    
    const activeType = activeData.type;
    const overType = overData.type;
    
    // Caso 1: Mover ruta desde palette a un bus
    if (activeType === 'route' && overType === 'bus') {
      const route = activeData.route;
      const targetBusId = overData.busId;
      
      // Validar antes de mover
      validateRouteCompatibility(targetBusId, route).then(result => {
        if (result.isValid) {
          addRouteToBus(targetBusId, route);
        } else {
          onValidationError?.(result.message);
        }
      });
      return;
    }
    
    // Caso 2: Mover ruta asignada a otro bus
    if (activeType === 'assigned-route' && overType === 'bus') {
      const fromBusId = activeData.busId;
      const toBusId = overData.busId;
      const routeId = activeData.route.route_id || activeData.route.id;
      
      if (fromBusId !== toBusId) {
        moveRouteBetweenBuses(fromBusId, toBusId, routeId);
      }
      return;
    }
    
    // Caso 3: Reordenar rutas dentro del mismo bus
    if (activeType === 'assigned-route' && overType === 'assigned-route') {
      const fromBusId = activeData.busId;
      const toBusId = overData.busId;
      const routeId = activeData.route.route_id || activeData.route.id;
      const overRouteId = overData.route.route_id || overData.route.id;
      
      if (fromBusId === toBusId) {
        // Reordenar dentro del mismo bus
        const bus = schedule.find(b => (b.bus_id || b.id) === fromBusId);
        if (bus && bus.items) {
          const oldIndex = bus.items.findIndex(r => (r.route_id || r.id) === routeId);
          const newIndex = bus.items.findIndex(r => (r.route_id || r.id) === overRouteId);
          if (oldIndex !== -1 && newIndex !== -1) {
            reorderWithinBus(fromBusId, oldIndex, newIndex);
          }
        }
      } else {
        // Mover a otro bus en posición específica
        const toBus = schedule.find(b => (b.bus_id || b.id) === toBusId);
        if (toBus && toBus.items) {
          const targetIndex = toBus.items.findIndex(r => (r.route_id || r.id) === overRouteId);
          moveRouteBetweenBuses(fromBusId, toBusId, routeId, targetIndex);
        }
      }
      return;
    }
  }, [schedule, addRouteToBus, moveRouteBetweenBuses, reorderWithinBus, validateRouteCompatibility, onValidationError]);

  /**
   * Sincronizar estado externo con estado interno
   */
  const syncSchedule = useCallback((newSchedule) => {
    // Debounce para evitar actualizaciones muy frecuentes
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }
    
    updateTimeoutRef.current = setTimeout(() => {
      setSchedule(newSchedule);
    }, 50);
  }, []);

  /**
   * Notificar cambios al componente padre
   */
  const notifyChange = useCallback(() => {
    onScheduleChange?.(schedule);
  }, [schedule, onScheduleChange]);

  return {
    // Estado
    schedule,
    isDragging,
    dragPreview,
    validationErrors,
    
    // Acciones
    setSchedule,
    syncSchedule,
    reorderWithinBus,
    moveRouteBetweenBuses,
    addRouteToBus,
    removeRouteFromBus,
    validateRouteCompatibility,
    notifyChange,
    
    // Handlers para DndContext
    handleDragStart,
    handleDragOver,
    handleDragEnd,
    
    // Helpers
    findRouteLocation,
  };
}

/**
 * Hook para manejar el estado del palette de rutas
 */
export function useRoutePalette(initialRoutes = []) {
  const [availableRoutes, setAvailableRoutes] = useState(initialRoutes);
  const [selectedRoutes, setSelectedRoutes] = useState([]);
  const [filter, setFilter] = useState(''); // 'all' | 'entry' | 'exit'
  const [searchQuery, setSearchQuery] = useState('');

  const filteredRoutes = availableRoutes.filter(route => {
    const matchesType = filter === 'all' || 
      (filter === 'entry' && (route.type === 'entry' || route.route_type === 'entry')) ||
      (filter === 'exit' && (route.type === 'exit' || route.route_type === 'exit'));
    
    const matchesSearch = !searchQuery || 
      route.id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      route.school_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      route.destination?.toLowerCase().includes(searchQuery.toLowerCase());
    
    return matchesType && matchesSearch;
  });

  const removeRoute = useCallback((routeId) => {
    setAvailableRoutes(prev => prev.filter(r => (r.id || r.route_id) !== routeId));
  }, []);

  const restoreRoute = useCallback((route) => {
    setAvailableRoutes(prev => {
      if (prev.some(r => (r.id || r.route_id) === (route.id || route.route_id))) {
        return prev;
      }
      return [...prev, route];
    });
  }, []);

  const selectRoute = useCallback((routeId) => {
    setSelectedRoutes(prev => {
      if (prev.includes(routeId)) {
        return prev.filter(id => id !== routeId);
      }
      return [...prev, routeId];
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedRoutes(filteredRoutes.map(r => r.id || r.route_id));
  }, [filteredRoutes]);

  const deselectAll = useCallback(() => {
    setSelectedRoutes([]);
  }, []);

  return {
    availableRoutes,
    filteredRoutes,
    selectedRoutes,
    filter,
    searchQuery,
    setAvailableRoutes,
    setFilter,
    setSearchQuery,
    removeRoute,
    restoreRoute,
    selectRoute,
    selectAll,
    deselectAll,
  };
}

/**
 * Hook para manejar validaciones OSRM
 */
export function useOSRMValidation(apiBaseUrl = '/api') {
  const [isValidating, setIsValidating] = useState(false);
  const [validationResults, setValidationResults] = useState({});

  const validateRoute = useCallback(async (busId, route) => {
    setIsValidating(true);
    
    try {
      const response = await fetch(`${apiBaseUrl}/validate-route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ busId, route }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      
      setValidationResults(prev => ({
        ...prev,
        [`${busId}-${route.id || route.route_id}`]: result,
      }));
      
      return result;
    } catch (error) {
      console.error('Error validando con OSRM:', error);
      return { 
        isValid: false, 
        message: 'Error de conexión con el servicio de validación' 
      };
    } finally {
      setIsValidating(false);
    }
  }, [apiBaseUrl]);

  const validateMultiple = useCallback(async (validations) => {
    setIsValidating(true);
    
    try {
      const response = await fetch(`${apiBaseUrl}/validate-routes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ validations }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const results = await response.json();
      setValidationResults(results);
      return results;
    } catch (error) {
      console.error('Error validando rutas:', error);
      return {};
    } finally {
      setIsValidating(false);
    }
  }, [apiBaseUrl]);

  const clearValidation = useCallback((key) => {
    setValidationResults(prev => {
      const newResults = { ...prev };
      delete newResults[key];
      return newResults;
    });
  }, []);

  return {
    isValidating,
    validationResults,
    validateRoute,
    validateMultiple,
    clearValidation,
  };
}

export default useDragAndDrop;
