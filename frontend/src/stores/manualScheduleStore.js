/**
 * Store Zustand para el Editor Manual de Horarios
 * 
 * Gestiona el estado global del modo constructor manual incluyendo:
 * - Buses en construcción con sus rutas asignadas
 * - Cache de tiempos OSRM
 * - Estado de validación
 * - Operaciones CRUD y DnD
 * 
 * @module stores/manualScheduleStore
 * @version 1.0.0
 * @requires zustand
 * 
 * @example
 * ```javascript
 * import { useManualScheduleStore } from './stores/manualScheduleStore';
 * 
 * // En un componente React
 * const { buses, addBus, assignRoute } = useManualScheduleStore();
 * ```
 */

import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { devtools, persist } from 'zustand/middleware';
import { v4 as uuidv4 } from 'uuid';

// ============================================================================
// CONSTANTS
// ============================================================================

/** Colores predefinidos para los buses */
const BUS_COLORS = [
  '#3B82F6', // blue-500
  '#10B981', // emerald-500
  '#F59E0B', // amber-500
  '#EF4444', // red-500
  '#8B5CF6', // violet-500
  '#EC4899', // pink-500
  '#06B6D4', // cyan-500
  '#84CC16', // lime-500
];

/** Tiempo mínimo de transición entre rutas (minutos) */
const MIN_TRANSITION_TIME = 10;

/** Tiempo máximo de viaje razonable (minutos) */
const MAX_REASONABLE_TRAVEL = 120;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Genera un ID único
 * @returns {string} UUID v4
 */
function generateId() {
  // Fallback si uuid no está disponible
  if (typeof uuidv4 === 'function') {
    return uuidv4();
  }
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Genera un color para un bus basado en su índice
 * @param {number} index - Índice del bus
 * @returns {string} Color hex
 */
function getBusColor(index) {
  return BUS_COLORS[index % BUS_COLORS.length];
}

/**
 * Parsea tiempo HH:mm a minutos desde medianoche
 * @param {string} time - Tiempo en formato HH:mm
 * @returns {number} Minutos desde medianoche
 */
function timeToMinutes(time) {
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
}

/**
 * Convierte minutos desde medianoche a formato HH:mm
 * @param {number} minutes - Minutos desde medianoche
 * @returns {string} Tiempo en formato HH:mm
 */
function minutesToTime(minutes) {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

/**
 * Suma minutos a un tiempo
 * @param {string} time - Tiempo base HH:mm
 * @param {number} minutes - Minutos a sumar
 * @returns {string} Nuevo tiempo HH:mm
 */
function addMinutes(time, minutes) {
  return minutesToTime(timeToMinutes(time) + minutes);
}

/**
 * Genera la key para el cache OSRM
 * @param {string} routeAId - ID de ruta origen
 * @param {string} routeBId - ID de ruta destino
 * @returns {string} Key del cache
 */
function getOSRMCacheKey(routeAId, routeBId) {
  return `${routeAId}_end_${routeBId}_start`;
}

// ============================================================================
// INITIAL STATE
// ============================================================================

const initialState = {
  // Buses en construcción
  buses: [],
  
  // Rutas disponibles
  availableRoutes: [],
  
  // IDs de rutas asignadas
  assignedRouteIds: new Set(),
  
  // Cache de tiempos OSRM
  osrmCache: new Map(),
  
  // Estado de validación
  validationStatus: 'unvalidated',
  invalidPairs: [],
  assignmentValidations: new Map(),
  
  // Estado de carga
  isLoading: false,
  
  // Error global
  error: null,
};

// ============================================================================
// STORE CREATION
// ============================================================================

export const useManualScheduleStore = create(
  devtools(
    immer((set, get) => ({
      ...initialState,

      // ======================================================================
      // CRUD DE BUSES
      // ======================================================================

      /**
       * Agrega un nuevo bus al workspace
       * @param {string} [busName] - Nombre opcional del bus
       * @returns {string} ID del bus creado
       */
      addBus: (busName) => {
        const id = generateId();
        const state = get();
        const color = getBusColor(state.buses.length);
        
        set((draft) => {
          draft.buses.push({
            busId: id,
            busName: busName || `Bus ${state.buses.length + 1}`,
            color,
            assignedRoutes: [],
          });
        });
        
        return id;
      },

      /**
       * Elimina un bus y sus asignaciones
       * @param {string} busId - ID del bus a eliminar
       */
      removeBus: (busId) => {
        set((draft) => {
          const busIndex = draft.buses.findIndex(b => b.busId === busId);
          if (busIndex === -1) return;
          
          const bus = draft.buses[busIndex];
          
          // Liberar rutas asignadas
          bus.assignedRoutes.forEach(assignment => {
            draft.assignedRouteIds.delete(assignment.routeId);
          });
          
          draft.buses.splice(busIndex, 1);
          
          // Recalcular validaciones
          draft.validationStatus = 'pending';
        });
      },

      /**
       * Actualiza el nombre de un bus
       * @param {string} busId - ID del bus
       * @param {string} name - Nuevo nombre
       */
      updateBusName: (busId, name) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (bus) {
            bus.busName = name;
          }
        });
      },

      /**
       * Reordena los buses
       * @param {string[]} busIds - Array de IDs en el nuevo orden
       */
      reorderBuses: (busIds) => {
        set((draft) => {
          const busMap = new Map(draft.buses.map(b => [b.busId, b]));
          draft.buses = busIds
            .map(id => busMap.get(id))
            .filter(Boolean);
        });
      },

      // ======================================================================
      // CRUD DE ASIGNACIONES
      // ======================================================================

      /**
       * Asigna una ruta a un bus
       * @param {string} busId - ID del bus
       * @param {string} routeId - ID de la ruta
       * @param {number} [position] - Posición opcional (por defecto al final)
       * @returns {string|null} ID de la asignación o null si falla
       */
      assignRoute: (busId, routeId, position) => {
        const state = get();
        const bus = state.buses.find(b => b.busId === busId);
        const route = state.availableRoutes.find(r => r.route_id === routeId);
        
        if (!bus || !route) return null;
        if (state.assignedRouteIds.has(routeId)) return null;
        
        const assignmentId = generateId();
        const insertPosition = position ?? bus.assignedRoutes.length;
        
        set((draft) => {
          const targetBus = draft.buses.find(b => b.busId === busId);
          const targetRoute = draft.availableRoutes.find(r => r.route_id === routeId);
          
          // Calcular tiempos y compatibilidad
          const prevAssignment = targetBus.assignedRoutes[insertPosition - 1];
          const nextAssignment = targetBus.assignedRoutes[insertPosition];
          
          let startTime = targetRoute.start_time;
          let compatibility = 'compatible';
          let transitionTime = 0;
          
          if (prevAssignment) {
            const prevRoute = draft.availableRoutes.find(r => r.route_id === prevAssignment.routeId);
            const cacheKey = getOSRMCacheKey(prevRoute.route_id, routeId);
            const cached = draft.osrmCache.get(cacheKey);
            
            transitionTime = cached?.durationMinutes || 0;
            const prevEndTimeMinutes = timeToMinutes(prevAssignment.endTime);
            const newStartTimeMinutes = prevEndTimeMinutes + transitionTime + MIN_TRANSITION_TIME;
            const routeStartMinutes = timeToMinutes(targetRoute.start_time);
            
            if (newStartTimeMinutes > routeStartMinutes) {
              startTime = minutesToTime(newStartTimeMinutes);
              compatibility = 'incompatible';
            }
          }
          
          // Crear asignación
          const newAssignment = {
            assignmentId,
            routeId,
            startTime,
            endTime: addMinutes(startTime, targetRoute.duration_minutes),
            position: insertPosition,
            compatibility,
            transitionTime: transitionTime || undefined,
          };
          
          // Insertar en la posición correcta
          targetBus.assignedRoutes.splice(insertPosition, 0, newAssignment);
          
          // Actualizar posiciones de las siguientes
          targetBus.assignedRoutes.forEach((a, idx) => {
            a.position = idx;
          });
          
          // Marcar ruta como asignada
          draft.assignedRouteIds.add(routeId);
          
          // Recalcular validación para rutas adyacentes
          draft.validationStatus = 'pending';
        });
        
        return assignmentId;
      },

      /**
       * Desasigna una ruta de un bus
       * @param {string} busId - ID del bus
       * @param {string} assignmentId - ID de la asignación
       */
      unassignRoute: (busId, assignmentId) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (!bus) return;
          
          const assignmentIndex = bus.assignedRoutes.findIndex(
            a => a.assignmentId === assignmentId
          );
          if (assignmentIndex === -1) return;
          
          const assignment = bus.assignedRoutes[assignmentIndex];
          
          // Liberar ruta
          draft.assignedRouteIds.delete(assignment.routeId);
          
          // Eliminar asignación
          bus.assignedRoutes.splice(assignmentIndex, 1);
          
          // Actualizar posiciones
          bus.assignedRoutes.forEach((a, idx) => {
            a.position = idx;
          });
          
          draft.validationStatus = 'pending';
        });
      },

      /**
       * Mueve una ruta entre buses
       * @param {string} fromBusId - Bus origen
       * @param {string} toBusId - Bus destino
       * @param {string} assignmentId - ID de la asignación
       * @param {number} [newPosition] - Nueva posición
       */
      moveRoute: (fromBusId, toBusId, assignmentId, newPosition) => {
        set((draft) => {
          const fromBus = draft.buses.find(b => b.busId === fromBusId);
          const toBus = draft.buses.find(b => b.busId === toBusId);
          
          if (!fromBus || !toBus) return;
          
          const assignmentIndex = fromBus.assignedRoutes.findIndex(
            a => a.assignmentId === assignmentId
          );
          if (assignmentIndex === -1) return;
          
          const [assignment] = fromBus.assignedRoutes.splice(assignmentIndex, 1);
          
          const insertPosition = newPosition ?? toBus.assignedRoutes.length;
          
          // Recalcular compatibilidad en el nuevo bus
          const prevAssignment = toBus.assignedRoutes[insertPosition - 1];
          const route = draft.availableRoutes.find(r => r.route_id === assignment.routeId);
          
          if (prevAssignment && route) {
            const prevRoute = draft.availableRoutes.find(r => r.route_id === prevAssignment.routeId);
            const cacheKey = getOSRMCacheKey(prevRoute.route_id, route.route_id);
            const cached = draft.osrmCache.get(cacheKey);
            const transitionTime = cached?.durationMinutes || 0;
            
            const prevEndTimeMinutes = timeToMinutes(prevAssignment.endTime);
            const newStartTimeMinutes = prevEndTimeMinutes + transitionTime + MIN_TRANSITION_TIME;
            const routeStartMinutes = timeToMinutes(route.start_time);
            
            assignment.startTime = minutesToTime(Math.max(newStartTimeMinutes, routeStartMinutes));
            assignment.endTime = addMinutes(assignment.startTime, route.duration_minutes);
            assignment.compatibility = newStartTimeMinutes > routeStartMinutes ? 'incompatible' : 'compatible';
            assignment.transitionTime = transitionTime || undefined;
          } else {
            // Primera ruta del bus
            assignment.startTime = route.start_time;
            assignment.endTime = addMinutes(route.start_time, route.duration_minutes);
            assignment.compatibility = 'compatible';
            assignment.transitionTime = undefined;
          }
          
          toBus.assignedRoutes.splice(insertPosition, 0, assignment);
          
          // Actualizar posiciones en ambos buses
          fromBus.assignedRoutes.forEach((a, idx) => { a.position = idx; });
          toBus.assignedRoutes.forEach((a, idx) => { a.position = idx; });
          
          draft.validationStatus = 'pending';
        });
      },

      /**
       * Reordena las rutas dentro de un bus
       * @param {string} busId - ID del bus
       * @param {string[]} assignmentIds - IDs en el nuevo orden
       */
      reorderRoutesInBus: (busId, assignmentIds) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (!bus) return;
          
          const assignmentMap = new Map(bus.assignedRoutes.map(a => [a.assignmentId, a]));
          bus.assignedRoutes = assignmentIds
            .map(id => assignmentMap.get(id))
            .filter(Boolean)
            .map((a, idx) => ({ ...a, position: idx }));
          
          draft.validationStatus = 'pending';
        });
      },

      /**
       * Actualiza la hora de inicio de una ruta asignada
       * @param {string} busId - ID del bus
       * @param {string} assignmentId - ID de la asignación
       * @param {string} newStartTime - Nueva hora de inicio HH:mm
       */
      updateRouteStartTime: (busId, assignmentId, newStartTime) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (!bus) return;
          
          const assignment = bus.assignedRoutes.find(a => a.assignmentId === assignmentId);
          if (!assignment) return;
          
          const route = draft.availableRoutes.find(r => r.route_id === assignment.routeId);
          if (!route) return;
          
          assignment.startTime = newStartTime;
          assignment.endTime = addMinutes(newStartTime, route.duration_minutes);
          
          // Recalcular compatibilidad con la ruta anterior
          const assignmentIndex = bus.assignedRoutes.indexOf(assignment);
          if (assignmentIndex > 0) {
            const prevAssignment = bus.assignedRoutes[assignmentIndex - 1];
            const prevRoute = draft.availableRoutes.find(r => r.route_id === prevAssignment.routeId);
            const cacheKey = getOSRMCacheKey(prevRoute.route_id, route.route_id);
            const cached = draft.osrmCache.get(cacheKey);
            const transitionTime = cached?.durationMinutes || 0;
            
            const prevEndTimeMinutes = timeToMinutes(prevAssignment.endTime);
            const minRequiredStart = prevEndTimeMinutes + transitionTime + MIN_TRANSITION_TIME;
            const actualStart = timeToMinutes(newStartTime);
            
            assignment.compatibility = actualStart >= minRequiredStart ? 'compatible' : 'incompatible';
            assignment.transitionTime = transitionTime || undefined;
          }
          
          draft.validationStatus = 'pending';
        });
      },

      // ======================================================================
      // GESTIÓN DE RUTAS DISPONIBLES
      // ======================================================================

      /**
       * Establece las rutas disponibles
       * @param {Route[]} routes - Array de rutas
       */
      setAvailableRoutes: (routes) => {
        set((draft) => {
          draft.availableRoutes = routes;
        });
      },

      /**
       * Agrega una ruta disponible
       * @param {Route} route - Ruta a agregar
       */
      addAvailableRoute: (route) => {
        set((draft) => {
          if (!draft.availableRoutes.find(r => r.route_id === route.route_id)) {
            draft.availableRoutes.push(route);
          }
        });
      },

      /**
       * Elimina una ruta disponible
       * @param {string} routeId - ID de la ruta
       */
      removeAvailableRoute: (routeId) => {
        set((draft) => {
          draft.availableRoutes = draft.availableRoutes.filter(r => r.route_id !== routeId);
        });
      },

      // ======================================================================
      // CACHE OSRM
      // ======================================================================

      /**
       * Obtiene el tiempo OSRM cacheado entre dos rutas
       * @param {string} routeAId - ID ruta origen
       * @param {string} routeBId - ID ruta destino
       * @returns {OSRMCacheEntry|undefined} Entrada del cache
       */
      getOSRMTime: (routeAId, routeBId) => {
        const state = get();
        const key = getOSRMCacheKey(routeAId, routeBId);
        return state.osrmCache.get(key);
      },

      /**
       * Guarda el tiempo OSRM en cache
       * @param {string} routeAId - ID ruta origen
       * @param {string} routeBId - ID ruta destino
       * @param {OSRMCacheEntry} entry - Datos a cachear
       */
      setOSRMTime: (routeAId, routeBId, entry) => {
        set((draft) => {
          const key = getOSRMCacheKey(routeAId, routeBId);
          draft.osrmCache.set(key, entry);
        });
      },

      /**
       * Limpia el cache de OSRM
       */
      clearOSRMCache: () => {
        set((draft) => {
          draft.osrmCache.clear();
        });
      },

      // ======================================================================
      // VALIDACIÓN
      // ======================================================================

      /**
       * Valida todo el horario
       * @returns {Promise<void>}
       */
      validateSchedule: async () => {
        set((draft) => {
          draft.isLoading = true;
          draft.validationStatus = 'pending';
        });
        
        const state = get();
        const invalidPairs = [];
        
        // Validar cada bus
        state.buses.forEach(bus => {
          for (let i = 1; i < bus.assignedRoutes.length; i++) {
            const prev = bus.assignedRoutes[i - 1];
            const curr = bus.assignedRoutes[i];
            
            const prevRoute = state.availableRoutes.find(r => r.route_id === prev.routeId);
            const currRoute = state.availableRoutes.find(r => r.route_id === curr.routeId);
            
            if (!prevRoute || !currRoute) continue;
            
            const cacheKey = getOSRMCacheKey(prevRoute.route_id, currRoute.route_id);
            const cached = state.osrmCache.get(cacheKey);
            
            const transitionTime = cached?.durationMinutes || 0;
            const minRequired = transitionTime + MIN_TRANSITION_TIME;
            
            const prevEndMinutes = timeToMinutes(prev.endTime);
            const currStartMinutes = timeToMinutes(curr.startTime);
            const availableTime = currStartMinutes - prevEndMinutes;
            
            if (availableTime < minRequired) {
              invalidPairs.push({
                routeA: prevRoute.route_id,
                routeB: currRoute.route_id,
                reason: `Transición insuficiente: ${availableTime}min disponibles, ${minRequired}min requeridos`,
                conflictType: 'insufficient_transition',
                requiredTime: minRequired,
                availableTime,
              });
            }
          }
        });
        
        set((draft) => {
          draft.invalidPairs = invalidPairs;
          draft.validationStatus = invalidPairs.length > 0 ? 'invalid' : 'valid';
          draft.isLoading = false;
        });
      },

      /**
       * Valida una asignación específica
       * @param {string} busId - ID del bus
       * @param {string} assignmentId - ID de la asignación
       * @returns {AssignmentValidation} Resultado de validación
       */
      validateAssignment: (busId, assignmentId) => {
        const state = get();
        const bus = state.buses.find(b => b.busId === busId);
        if (!bus) {
          return { assignmentId, isValid: false, errors: [{ code: 'BUS_NOT_FOUND', message: 'Bus no encontrado' }], warnings: [] };
        }
        
        const assignment = bus.assignedRoutes.find(a => a.assignmentId === assignmentId);
        if (!assignment) {
          return { assignmentId, isValid: false, errors: [{ code: 'ASSIGNMENT_NOT_FOUND', message: 'Asignación no encontrada' }], warnings: [] };
        }
        
        const errors = [];
        const warnings = [];
        
        if (assignment.compatibility === 'incompatible') {
          errors.push({
            code: 'INCOMPATIBLE_TRANSITION',
            message: 'La transición desde la ruta anterior es incompatible',
            field: 'compatibility',
          });
        }
        
        return { assignmentId, isValid: errors.length === 0, errors, warnings };
      },

      /**
       * Establece el estado de validación
       * @param {ValidationStatus} status - Nuevo estado
       */
      setValidationStatus: (status) => {
        set((draft) => {
          draft.validationStatus = status;
        });
      },

      // ======================================================================
      // ESTADO GLOBAL
      // ======================================================================

      /**
       * Establece el estado de carga
       * @param {boolean} isLoading - Estado de carga
       */
      setLoading: (isLoading) => {
        set((draft) => {
          draft.isLoading = isLoading;
        });
      },

      /**
       * Establece el error global
       * @param {string|null} error - Mensaje de error o null
       */
      setError: (error) => {
        set((draft) => {
          draft.error = error;
        });
      },

      /**
       * Resetea el estado al inicial
       */
      reset: () => {
        set((draft) => {
          Object.assign(draft, initialState);
        });
      },

      // ======================================================================
      // UTILIDADES
      // ======================================================================

      /**
       * Obtiene un bus por ID
       * @param {string} busId - ID del bus
       * @returns {BusInConstruction|undefined}
       */
      getBusById: (busId) => {
        return get().buses.find(b => b.busId === busId);
      },

      /**
       * Obtiene una ruta por ID
       * @param {string} routeId - ID de la ruta
       * @returns {Route|undefined}
       */
      getRouteById: (routeId) => {
        return get().availableRoutes.find(r => r.route_id === routeId);
      },

      /**
       * Obtiene una asignación por ID
       * @param {string} assignmentId - ID de la asignación
       * @returns {{bus: BusInConstruction, assignment: AssignedRoute}|undefined}
       */
      getAssignmentById: (assignmentId) => {
        for (const bus of get().buses) {
          const assignment = bus.assignedRoutes.find(a => a.assignmentId === assignmentId);
          if (assignment) {
            return { bus, assignment };
          }
        }
        return undefined;
      },

      /**
       * Obtiene rutas compatibles con una ruta dada
       * @param {string} routeId - ID de la ruta
       * @returns {Route[]} Rutas compatibles
       */
      getCompatibleRoutes: (routeId) => {
        const state = get();
        const route = state.availableRoutes.find(r => r.route_id === routeId);
        if (!route) return [];
        
        return state.availableRoutes.filter(r => {
          if (r.route_id === routeId) return false;
          if (state.assignedRouteIds.has(r.route_id)) return false;
          
          const cacheKey = getOSRMCacheKey(routeId, r.route_id);
          const cached = state.osrmCache.get(cacheKey);
          
          if (!cached) return true; // Sin datos, asumir compatible
          
          const routeEndMinutes = timeToMinutes(route.end_time);
          const nextStartMinutes = timeToMinutes(r.start_time);
          const availableTime = nextStartMinutes - routeEndMinutes;
          
          return availableTime >= cached.durationMinutes + MIN_TRANSITION_TIME;
        });
      },

      /**
       * Verifica si dos rutas pueden ser consecutivas
       * @param {string} routeAId - ID ruta anterior
       * @param {string} routeBId - ID ruta siguiente
       * @returns {boolean} true si son compatibles
       */
      canRoutesBeConsecutive: (routeAId, routeBId) => {
        const state = get();
        const routeA = state.availableRoutes.find(r => r.route_id === routeAId);
        const routeB = state.availableRoutes.find(r => r.route_id === routeBId);
        
        if (!routeA || !routeB) return false;
        
        const cacheKey = getOSRMCacheKey(routeAId, routeBId);
        const cached = state.osrmCache.get(cacheKey);
        
        if (!cached) return true;
        
        const endAMinutes = timeToMinutes(routeA.end_time);
        const startBMinutes = timeToMinutes(routeB.start_time);
        const availableTime = startBMinutes - endAMinutes;
        
        return availableTime >= cached.durationMinutes + MIN_TRANSITION_TIME;
      },

      // ======================================================================
      // EXPORTAR/IMPORTAR
      // ======================================================================

      /**
       * Exporta el horario a un objeto serializable
       * @returns {object} Horario exportado
       */
      exportSchedule: () => {
        const state = get();
        return {
          version: '1.0',
          exportedAt: new Date().toISOString(),
          buses: state.buses.map(bus => ({
            busId: bus.busId,
            busName: bus.busName,
            color: bus.color,
            assignedRoutes: bus.assignedRoutes.map(a => ({
              routeId: a.routeId,
              startTime: a.startTime,
              endTime: a.endTime,
              position: a.position,
            })),
          })),
          availableRoutes: state.availableRoutes,
        };
      },

      /**
       * Importa un horario desde un objeto
       * @param {object} data - Datos a importar
       */
      importSchedule: (data) => {
        set((draft) => {
          draft.buses = data.buses || [];
          draft.availableRoutes = data.availableRoutes || [];
          draft.assignedRouteIds = new Set(
            draft.buses.flatMap(b => b.assignedRoutes.map(a => a.routeId))
          );
          draft.validationStatus = 'pending';
        });
      },
    })),
    { name: 'manual-schedule-store' }
  )
);

// ============================================================================
// SELECTORS (Hooks auxiliares)
// ============================================================================

/**
 * Hook selector para obtener buses con información enriquecida
 * @returns {Array} Buses con datos calculados
 */
export function useBusesWithStats() {
  return useManualScheduleStore((state) => {
    return state.buses.map(bus => {
      const totalOperationTime = bus.assignedRoutes.reduce((sum, a) => {
        const route = state.availableRoutes.find(r => r.route_id === a.routeId);
        return sum + (route?.duration_minutes || 0);
      }, 0);
      
      const totalTransitionTime = bus.assignedRoutes.reduce((sum, a) => {
        return sum + (a.transitionTime || 0);
      }, 0);
      
      return {
        ...bus,
        totalOperationTime,
        totalTransitionTime,
        totalTime: totalOperationTime + totalTransitionTime,
      };
    });
  });
}

/**
 * Hook selector para obtener rutas disponibles (no asignadas)
 * @returns {Array} Rutas disponibles
 */
export function useAvailableRoutesOnly() {
  return useManualScheduleStore((state) => 
    state.availableRoutes.filter(r => !state.assignedRouteIds.has(r.route_id))
  );
}

/**
 * Hook selector para obtener estadísticas del horario
 * @returns {object} Estadísticas
 */
export function useScheduleStats() {
  return useManualScheduleStore((state) => {
    const totalBuses = state.buses.length;
    const totalRoutes = state.availableRoutes.length;
    const assignedRoutes = state.assignedRouteIds.size;
    const unassignedRoutes = totalRoutes - assignedRoutes;
    const hasErrors = state.invalidPairs.length > 0;
    
    return {
      totalBuses,
      totalRoutes,
      assignedRoutes,
      unassignedRoutes,
      progress: totalRoutes > 0 ? (assignedRoutes / totalRoutes) * 100 : 0,
      hasErrors,
      isValid: state.validationStatus === 'valid',
      isComplete: assignedRoutes === totalRoutes && !hasErrors,
    };
  });
}

export default useManualScheduleStore;
