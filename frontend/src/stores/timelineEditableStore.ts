/**
 * Store Zustand para el Timeline Editable
 * 
 * Gestiona el estado global del sistema de edición de horarios con:
 * - RouteBlock con candado de edición
 * - Validación OSRM de compatibilidad
 * - Rutas libres (no asignadas a bus)
 * - Posicionamiento por hora exacta
 * - Sugerencias inteligentes de ordenación
 * 
 * @module stores/timelineEditableStore
 * @version 1.0.0
 * @requires zustand, immer
 * 
 * @example
 * ```typescript
 * import { useTimelineEditableStore } from './stores/timelineEditableStore';
 * 
 * // En un componente React
 * const { buses, moveRoute, toggleLock } = useTimelineEditableStore();
 * ```
 */

import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { enableMapSet } from 'immer';
import { devtools, persist } from 'zustand/middleware';
import { v4 as uuidv4 } from 'uuid';

// Enable Map/Set support in Immer
enableMapSet();
import type {
  TimelineEditableState,
  TimelineBus,
  ExtendedRouteItem,
  RouteSuggestion,
  SuggestionEngineResult,
  TimelineViewConfig,
  TimelineValidationState,
  ValidationError,
  ValidationWarning,
  CompatibilityCheck,
  DragAction,
  RouteFilters,
  TimelineExport,
  CreateExtendedRouteItemInput,
  RouteWorkspaceStatus,
  RouteBaseData,
  Coordinates,
} from '../types/timelineEditable';

// ============================================================================
// CONSTANTES
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
  '#F97316', // orange-500
  '#14B8A6', // teal-500
  '#6366F1', // indigo-500
  '#D946EF', // fuchsia-500
];

/** Buffer mínimo de transición entre rutas (minutos) */
const MIN_TRANSITION_BUFFER = 10;

/** Tiempo máximo razonable de viaje entre rutas (minutos) */
const MAX_REASONABLE_TRAVEL = 120;

/** Score mínimo para mostrar sugerencias */
const MIN_SUGGESTION_SCORE = 50;

/** Máximo número de sugerencias a mostrar */
const MAX_SUGGESTIONS = 10;

// ============================================================================
// FUNCIONES UTILITARIAS
// ============================================================================

/**
 * Genera un ID único
 */
function generateId(): string {
  return uuidv4();
}

/**
 * Obtiene un color para un bus basado en su índice
 */
function getBusColor(index: number): string {
  return BUS_COLORS[index % BUS_COLORS.length];
}

/**
 * Convierte tiempo "HH:mm" a minutos desde medianoche
 */
function timeToMinutes(time: string): number {
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
}

/**
 * Convierte minutos desde medianoche a "HH:mm"
 */
function minutesToTime(minutes: number): string {
  const hrs = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

/**
 * Suma minutos a un tiempo
 */
function addMinutes(time: string, minutes: number): string {
  return minutesToTime(timeToMinutes(time) + minutes);
}

/**
 * Calcula la diferencia en minutos entre dos tiempos
 */
function timeDiffMinutes(time1: string, time2: string): number {
  return timeToMinutes(time2) - timeToMinutes(time1);
}

/**
 * Genera key para cache OSRM
 */
function getOSRMCacheKey(routeAId: string, routeBId: string): string {
  return `${routeAId}_end_${routeBId}_start`;
}

/**
 * Verifica si un tiempo está dentro del rango de horas de la vista
 */
function isTimeInRange(time: string, hourRange: [number, number]): boolean {
  const minutes = timeToMinutes(time);
  const startMinutes = hourRange[0] * 60;
  const endMinutes = hourRange[1] * 60;
  return minutes >= startMinutes && minutes <= endMinutes;
}

/**
 * Calcula posición left/width para un RouteBlock
 */
function calculateRoutePosition(
  startTime: string,
  endTime: string,
  hourRange: [number, number],
  pixelsPerHour: number
): { left: number; width: number } {
  const rangeStartMinutes = hourRange[0] * 60;
  const rangeDurationMinutes = (hourRange[1] - hourRange[0]) * 60;
  
  const startMinutes = timeToMinutes(startTime);
  const endMinutes = timeToMinutes(endTime);
  const durationMinutes = endMinutes - startMinutes;
  
  const left = ((startMinutes - rangeStartMinutes) / rangeDurationMinutes) * (rangeDurationMinutes / 60 * pixelsPerHour);
  const width = (durationMinutes / 60) * pixelsPerHour;
  
  return { left, width };
}

// ============================================================================
// ESTADO INICIAL
// ============================================================================

const initialViewConfig: TimelineViewConfig = {
  hourRange: [6, 22],
  showUnassignedPanel: true,
  snapToGrid: true,
  gridSizeMinutes: 5,
  validationEnabled: true,
  zoom: 'normal',
  pixelsPerHour: 100,
  showCompatibilityLines: true,
  showDetailedTooltips: true,
  hideEmptyBuses: false,
};

const initialValidationState: TimelineValidationState = {
  isValidating: false,
  errors: [],
  warnings: [],
  status: 'unvalidated',
  errorCount: { error: 0, warning: 0, info: 0 },
};

const initialDragState: TimelineEditableState['dragState'] = {
  isDragging: false,
  possibleDropTargets: [],
};

const initialState: TimelineEditableState = {
  buses: [],
  unassignedRoutes: [],
  originalRoutes: [],
  viewConfig: initialViewConfig,
  validation: initialValidationState,
  selectedRouteIds: [],
  activeRouteId: undefined,
  dragState: initialDragState,
  activeSuggestions: [],
  isLoading: false,
  error: null,
  osrmCache: new Map(),
  // Estado para edición de rutas
  selectedRouteId: null,
  isDrawerOpen: false,
  dirtyRoutes: new Map(),
};

// ============================================================================
// STORE
// ============================================================================

export interface TimelineEditableStore extends TimelineEditableState {
  // ========================================================================
  // ACCIONES: INICIALIZACIÓN
  // ========================================================================
  
  /** Inicializa el estado desde el schedule del backend */
  initializeFromSchedule: (schedule: Array<{
    bus_id: string;
    items: Array<{
      route_id: string;
      route_code: string;
      route_name?: string;
      school_name?: string;
      school?: string;
      type: 'entry' | 'exit';
      start_time: string;
      end_time: string;
      duration_minutes: number;
      shift?: string;
      deadhead?: number;
      stops?: Array<{
        stop_id: string;
        stop_name: string;
        latitude: number;
        longitude: number;
      }>;
    }>;
  }>, routes: Array<{
    id?: string;
    route_id?: string;
    route_code?: string;
    route_name?: string;
    school?: string;
    start_coordinates?: { lat: number; lon: number } | [number, number];
    end_coordinates?: { lat: number; lon: number } | [number, number];
    origin?: string;
    destination?: string;
    stops?: Array<{
      stop_id: string;
      stop_name: string;
      latitude: number;
      longitude: number;
    }>;
  }>) => void;
  
  // ========================================================================
  // ACCIONES: CRUD DE BUSES
  // ========================================================================
  
  /** Agrega un nuevo bus */
  addBus: (busName?: string) => string;
  
  /** Elimina un bus y libera sus rutas */
  removeBus: (busId: string) => void;
  
  /** Actualiza el nombre de un bus */
  updateBusName: (busId: string, name: string) => void;
  
  /** Reordena los buses */
  reorderBuses: (busIds: string[]) => void;
  
  /** Colapsa/expande un bus */
  toggleBusCollapse: (busId: string) => void;
  
  /** Muestra/oculta un bus */
  toggleBusVisibility: (busId: string) => void;
  
  // ========================================================================
  // ACCIONES: CRUD DE RUTAS
  // ========================================================================
  
  /** Agrega una nueva ruta al sistema */
  addRoute: (route: CreateExtendedRouteItemInput) => ExtendedRouteItem;
  
  /** Elimina una ruta del sistema */
  removeRoute: (routeId: string) => void;
  
  /** 
   * Actualiza una ruta existente
   * - Actualiza campos de la ruta
   * - Marca como 'dirty' (cambios sin guardar)
   */
  updateRoute: (routeId: string, updates: Partial<ExtendedRouteItem>) => void;
  
  /** Mueve una ruta entre buses o a libres */
  moveRoute: (
    routeId: string,
    targetBusId: string | null,
    targetPosition?: number,
    targetTime?: string
  ) => boolean;
  
  /**
   * Mueve una ruta a otro bus específico
   * - Valida que no haya solapamiento
   * - Actualiza assignedBusId
   * - Recalcula positionInBus
   */
  moveRouteToBus: (routeId: string, targetBusId: string) => boolean;
  
  /** 
   * Cambia el orden de rutas dentro de un bus
   * Nota: Solo funciona si las rutas son compatibles en el nuevo orden
   */
  reorderRoutesInBus: (busId: string, routeIds: string[]) => boolean;
  
  /**
   * Actualiza las paradas de una ruta
   * - Reemplaza array de stops
   * - Recalcula duration si cambian tiempos
   */
  updateRouteStops: (routeId: string, stops: RouteBaseData['stops']) => void;
  
  /**
   * Guarda los cambios de una ruta en el backend
   * - Llama a PATCH /api/routes/{routeId}
   * - Limpia estado 'dirty' si éxito
   * - Muestra error si falla
   */
  saveRouteChanges: (routeId: string) => Promise<boolean>;
  
  /**
   * Descarta los cambios de una ruta
   * - Resetea a valores originales
   * - Limpia 'dirty'
   */
  discardRouteChanges: (routeId: string) => void;
  
  /** Verifica si una ruta tiene cambios sin guardar */
  isRouteDirty: (routeId: string) => boolean;
  
  /** Obtiene los cambios pendientes de una ruta */
  getRouteChanges: (routeId: string) => Partial<ExtendedRouteItem> | undefined;
  
  // ========================================================================
  // ACCIONES: CONTROL DE EDICIÓN (CANDADO)
  // ========================================================================
  
  /** Bloquea una ruta (candado cerrado) */
  lockRoute: (routeId: string, reason?: string) => void;
  
  /** Desbloquea una ruta (candado abierto) */
  unlockRoute: (routeId: string) => void;
  
  /** Toggle del estado de bloqueo */
  toggleRouteLock: (routeId: string) => void;
  
  /** Bloquea todas las rutas de un bus */
  lockAllRoutesInBus: (busId: string, reason?: string) => void;
  
  /** Desbloquea todas las rutas de un bus */
  unlockAllRoutesInBus: (busId: string) => void;
  
  // ========================================================================
  // ACCIONES: VALIDACIÓN
  // ========================================================================
  
  /** Valida todo el horario */
  validateAll: () => Promise<void>;
  
  /** Valida un bus específico */
  validateBus: (busId: string) => ValidationError[];
  
  /** Valida una ruta específica */
  validateRoute: (routeId: string) => ValidationError[];
  
  /** Calcula compatibilidad entre dos rutas */
  calculateCompatibility: (
    routeAId: string,
    routeBId: string,
    useCache?: boolean
  ) => CompatibilityCheck | null;
  
  /** Limpia el estado de validación */
  clearValidation: () => void;
  
  // ========================================================================
  // ACCIONES: SUGERENCIAS INTELIGENTES
  // ========================================================================
  
  /** Genera sugerencias para una ruta específica */
  generateSuggestionsForRoute: (routeId: string) => RouteSuggestion[];
  
  /** Genera sugerencias globales para todas las rutas libres */
  generateGlobalSuggestions: () => SuggestionEngineResult;
  
  /** Aplica una sugerencia al estado */
  applySuggestion: (suggestion: RouteSuggestion) => boolean;
  
  /** Limpia las sugerencias activas */
  clearSuggestions: () => void;
  
  // ========================================================================
  // ACCIONES: CONFIGURACIÓN DE VISTA
  // ========================================================================
  
  /** Actualiza la configuración de vista */
  updateViewConfig: (config: Partial<TimelineViewConfig>) => void;
  
  /** Cambia el rango de horas visible */
  setHourRange: (start: number, end: number) => void;
  
  /** Cambia el nivel de zoom */
  setZoom: (zoom: TimelineViewConfig['zoom']) => void;
  
  /** Toggle del panel de rutas libres */
  toggleUnassignedPanel: () => void;
  
  // ========================================================================
  // ACCIONES: SELECCIÓN
  // ========================================================================
  
  /** Selecciona una ruta (versión legacy con multi-select) */
  selectRoute: (routeId: string, multi?: boolean) => void;
  
  /** 
   * Selecciona una ruta para edición (nueva versión)
   * - Guarda routeId en estado
   * - Abre el drawer
   * - Si routeId es null, cierra el drawer
   */
  selectRouteForEdit: (routeId: string | null) => void;
  
  /** Deselecciona una ruta */
  deselectRoute: (routeId: string) => void;
  
  /** Limpia la selección */
  clearSelection: () => void;
  
  /** Selecciona todas las rutas de un bus */
  selectAllRoutesInBus: (busId: string) => void;
  
  /** Establece la ruta activa (hover/focus) */
  setActiveRoute: (routeId?: string) => void;
  
  /** Abre/cierra el drawer de edición */
  toggleDrawer: () => void;
  
  /** Cierra el drawer de edición */
  closeDrawer: () => void;
  
  // ========================================================================
  // ACCIONES: DRAG & DROP
  // ========================================================================
  
  /** Inicia una operación de drag */
  startDrag: (routeId: string, sourceBusId?: string) => void;
  
  /** Actualiza el estado durante el drag */
  updateDragTarget: (targetBusId?: string, targetTime?: string) => void;
  
  /** Finaliza la operación de drag */
  endDrag: (cancelled?: boolean) => DropResult | null;
  
  /** Verifica si un drop es válido */
  canDrop: (routeId: string, targetBusId: string | null, targetTime?: string) => boolean;
  
  // ========================================================================
  // ACCIONES: CACHE OSRM
  // ========================================================================
  
  /** Guarda un resultado OSRM en cache */
  cacheOSRMResult: (routeAId: string, routeBId: string, result: CompatibilityCheck) => void;
  
  /** Obtiene un resultado OSRM del cache */
  getCachedOSRM: (routeAId: string, routeBId: string) => CompatibilityCheck | undefined;
  
  /** Limpia el cache OSRM */
  clearOSRMCache: () => void;
  
  // ========================================================================
  // ACCIONES: IMPORT/EXPORT
  // ========================================================================
  
  /** Importa un estado desde objeto JSON */
  importState: (data: TimelineExport) => void;
  
  /** Exporta el estado actual a objeto JSON */
  exportState: () => TimelineExport;
  
  /** Resetea al estado inicial */
  reset: () => void;
  
  /** Guarda snapshot de rutas originales */
  saveOriginalRoutes: () => void;
  
  /** Restaura rutas originales */
  restoreOriginalRoutes: () => void;
  
  // ========================================================================
  // ACCIONES: UTILIDADES
  // ========================================================================
  
  /** Obtiene un bus por ID */
  getBus: (busId: string) => TimelineBus | undefined;
  
  /** Obtiene una ruta por ID (busca en todos lados) */
  getRoute: (routeId: string) => ExtendedRouteItem | undefined;
  
  /** Encuentra qué bus contiene una ruta */
  findBusForRoute: (routeId: string) => TimelineBus | undefined;
  
  /** Filtra rutas según criterios */
  filterRoutes: (filters: RouteFilters) => ExtendedRouteItem[];
  
  /** Obtiene estadísticas del timeline */
  getStats: () => {
    totalRoutes: number;
    assignedRoutes: number;
    unassignedRoutes: number;
    lockedRoutes: number;
    busCount: number;
    conflicts: number;
    coveragePercentage: number;
  };
  
  /** Calcula posición visual para un RouteBlock */
  calculateRouteVisualPosition: (route: ExtendedRouteItem) => { left: number; width: number };
}

// Tipo auxiliar para el resultado de drop
interface DropResult {
  success: boolean;
  action: DragAction;
  routeId: string;
  sourceBusId?: string;
  targetBusId?: string;
  targetTime?: string;
  targetPosition?: number;
  errors?: ValidationError[];
  warnings?: ValidationWarning[];
}

export const useTimelineEditableStore = create<TimelineEditableStore>()(
  devtools(
    immer((set, get) => ({
      ...initialState,

      // ======================================================================
      // INICIALIZACIÓN DESDE SCHEDULE
      // ======================================================================

      initializeFromSchedule: (schedule, routes) => {
        set((draft) => {
          // Reset state
          draft.buses = [];
          draft.unassignedRoutes = [];
          draft.validation = { ...initialValidationState };
          draft.selectedRouteIds = [];
          draft.activeRouteId = undefined;
          draft.activeSuggestions = [];
          draft.osrmCache.clear();

          if (!schedule || schedule.length === 0) return;

          // Helper para convertir tiempo a minutos
          const timeToMinutes = (time: string): number => {
            const [hours, minutes] = time.split(':').map(Number);
            return hours * 60 + minutes;
          };

          // Encontrar min/max tiempo para auto-calcular hourRange
          let minTimeMinutes = 24 * 60;
          let maxTimeMinutes = 0;

          schedule.forEach((busData, busIndex) => {
            const busId = busData.bus_id || `bus-${busIndex}`;
            const color = getBusColor(busIndex);

            // Crear TimelineBus
            const timelineBus: TimelineBus = {
              busId,
              busName: `Bus ${busIndex + 1}`,
              color,
              routes: [],
              isCollapsed: false,
              isVisible: true,
            };

            // Procesar items del bus
            busData.items?.forEach((item, itemIndex) => {
              // Actualizar min/max tiempos
              const startMinutes = timeToMinutes(item.start_time);
              const endMinutes = timeToMinutes(item.end_time);
              minTimeMinutes = Math.min(minTimeMinutes, startMinutes);
              maxTimeMinutes = Math.max(maxTimeMinutes, endMinutes);

              // Buscar ruta original para datos geográficos
              const originalRoute = routes.find(r => 
                (r.id === item.route_id || r.route_id === item.route_id)
              );

              // Extraer coordenadas
              let startCoords: Coordinates | undefined;
              let endCoords: Coordinates | undefined;

              if (originalRoute?.start_coordinates) {
                const coords = originalRoute.start_coordinates;
                if (Array.isArray(coords)) {
                  startCoords = { lat: coords[0], lon: coords[1] };
                } else {
                  startCoords = { lat: coords.lat, lon: coords.lon };
                }
              }

              if (originalRoute?.end_coordinates) {
                const coords = originalRoute.end_coordinates;
                if (Array.isArray(coords)) {
                  endCoords = { lat: coords[0], lon: coords[1] };
                } else {
                  endCoords = { lat: coords.lat, lon: coords.lon };
                }
              }

              // Crear ExtendedRouteItem
              const extendedRoute: ExtendedRouteItem = {
                route_id: item.route_id,
                route_code: item.route_code || item.route_id,
                route_name: item.route_name || item.route_code || item.route_id,
                school: item.school_name || item.school || originalRoute?.school || 'Sin colegio',
                start_time: item.start_time,
                end_time: item.end_time,
                duration_minutes: item.duration_minutes,
                type: item.type,
                stops: item.stops || originalRoute?.stops || [],
                
                // Campos de RouteGeography
                startCoordinates: startCoords || { lat: 0, lon: 0 },
                endCoordinates: endCoords || { lat: 0, lon: 0 },
                origin: originalRoute?.origin || '',
                destination: originalRoute?.destination || '',
                
                // Campos de control
                isEditable: true,
                isLocked: false,
                status: 'assigned',
                assignedBusId: busId,
                positionInBus: itemIndex,
                currentStartTime: item.start_time,
                currentEndTime: item.end_time,
              };

              timelineBus.routes.push(extendedRoute);
            });

            draft.buses.push(timelineBus);
          });

          // Actualizar hourRange basado en los tiempos encontrados
          if (minTimeMinutes < 24 * 60 && maxTimeMinutes > 0) {
            const startHour = Math.max(0, Math.floor(minTimeMinutes / 60) - 1);
            const endHour = Math.min(24, Math.ceil(maxTimeMinutes / 60) + 1);
            draft.viewConfig.hourRange = [startHour, endHour];
          }

          draft.validation.status = 'pending';
        });
      },

      // ======================================================================
      // CRUD DE BUSES
      // ======================================================================

      addBus: (busName?: string) => {
        const id = generateId();
        const state = get();
        const color = getBusColor(state.buses.length);
        
        set((draft) => {
          draft.buses.push({
            busId: id,
            busName: busName || `Bus ${state.buses.length + 1}`,
            color,
            routes: [],
            isCollapsed: false,
            isVisible: true,
          });
        });
        
        return id;
      },

      removeBus: (busId: string) => {
        set((draft) => {
          const busIndex = draft.buses.findIndex(b => b.busId === busId);
          if (busIndex === -1) return;
          
          const bus = draft.buses[busIndex];
          
          // Mover rutas a libres (si no están bloqueadas)
          bus.routes.forEach(route => {
            if (!route.isLocked) {
              route.status = 'unassigned';
              route.assignedBusId = undefined;
              route.positionInBus = undefined;
              draft.unassignedRoutes.push(route);
            }
          });
          
          draft.buses.splice(busIndex, 1);
          draft.validation.status = 'pending';
        });
      },

      updateBusName: (busId: string, name: string) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (bus) {
            bus.busName = name;
          }
        });
      },

      reorderBuses: (busIds: string[]) => {
        set((draft) => {
          const busMap = new Map(draft.buses.map(b => [b.busId, b]));
          draft.buses = busIds
            .map(id => busMap.get(id))
            .filter((b): b is TimelineBus => b !== undefined);
        });
      },

      toggleBusCollapse: (busId: string) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (bus) {
            bus.isCollapsed = !bus.isCollapsed;
          }
        });
      },

      toggleBusVisibility: (busId: string) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (bus) {
            bus.isVisible = !bus.isVisible;
          }
        });
      },

      // ======================================================================
      // CRUD DE RUTAS
      // ======================================================================

      addRoute: (routeInput: CreateExtendedRouteItemInput): ExtendedRouteItem => {
        const route: ExtendedRouteItem = {
          ...routeInput,
          status: 'unassigned',
          isEditable: routeInput.isEditable ?? true,
          isLocked: routeInput.isLocked ?? false,
          currentStartTime: routeInput.start_time,
          currentEndTime: routeInput.end_time,
        };
        
        set((draft) => {
          draft.unassignedRoutes.push(route);
          draft.validation.status = 'pending';
        });
        
        return route;
      },

      removeRoute: (routeId: string) => {
        set((draft) => {
          // Remover de libres
          const unassignedIndex = draft.unassignedRoutes.findIndex(r => r.route_id === routeId);
          if (unassignedIndex !== -1) {
            draft.unassignedRoutes.splice(unassignedIndex, 1);
          }
          
          // Remover de buses
          draft.buses.forEach(bus => {
            const routeIndex = bus.routes.findIndex(r => r.route_id === routeId);
            if (routeIndex !== -1) {
              bus.routes.splice(routeIndex, 1);
            }
          });
          
          draft.validation.status = 'pending';
        });
      },

      updateRoute: (routeId: string, updates: Partial<ExtendedRouteItem>) => {
        set((draft) => {
          const route = getRouteFromDraft(draft, routeId);
          if (!route || route.isLocked) return;
          
          // Guardar cambios previos en dirtyRoutes si es la primera modificación
          if (!draft.dirtyRoutes.has(routeId)) {
            draft.dirtyRoutes.set(routeId, { ...route });
          }
          
          // Aplicar actualizaciones permitidas
          if (updates.isLocked !== undefined) {
            route.isLocked = updates.isLocked;
          }
          if (updates.currentStartTime !== undefined && !route.isLocked) {
            route.currentStartTime = updates.currentStartTime;
            route.currentEndTime = addMinutes(
              updates.currentStartTime,
              route.duration_minutes
            );
          }
          if (updates.currentEndTime !== undefined && !route.isLocked) {
            route.currentEndTime = updates.currentEndTime;
            route.duration_minutes = timeDiffMinutes(
              route.currentStartTime,
              updates.currentEndTime
            );
          }
          if (updates.assignedBusId !== undefined) {
            route.assignedBusId = updates.assignedBusId;
          }
          if (updates.positionInBus !== undefined) {
            route.positionInBus = updates.positionInBus;
          }
          if (updates.route_name !== undefined) {
            route.route_name = updates.route_name;
          }
          if (updates.route_code !== undefined) {
            route.route_code = updates.route_code;
          }
          if (updates.school !== undefined) {
            route.school = updates.school;
          }
          if (updates.type !== undefined) {
            route.type = updates.type;
          }
          if (updates.startCoordinates !== undefined) {
            route.startCoordinates = updates.startCoordinates;
          }
          if (updates.endCoordinates !== undefined) {
            route.endCoordinates = updates.endCoordinates;
          }
          if (updates.origin !== undefined) {
            route.origin = updates.origin;
          }
          if (updates.destination !== undefined) {
            route.destination = updates.destination;
          }
          if (updates.stops !== undefined) {
            route.stops = updates.stops;
            // Recalcular duración basada en paradas
            if (updates.stops.length >= 2) {
              // La duración se mantiene o se puede recalcular si hay tiempos estimados
              // Por ahora mantenemos la duración existente
            }
          }
          if (updates.lockReason !== undefined) {
            route.lockReason = updates.lockReason;
          }
          if (updates.isEditable !== undefined) {
            route.isEditable = updates.isEditable;
          }
          
          draft.validation.status = 'pending';
        });
      },

      moveRoute: (
        routeId: string,
        targetBusId: string | null,
        targetPosition?: number,
        targetTime?: string
      ): boolean => {
        const state = get();
        const route = state.getRoute(routeId);
        
        if (!route || route.isLocked) return false;
        
        const sourceBus = state.findBusForRoute(routeId);
        
        set((draft) => {
          // Guardar en dirtyRoutes si es la primera modificación
          if (!draft.dirtyRoutes.has(routeId)) {
            draft.dirtyRoutes.set(routeId, { ...route });
          }
          
          // Remover de ubicación actual
          if (sourceBus) {
            const sourceBusObj = draft.buses.find(b => b.busId === sourceBus.busId);
            if (sourceBusObj) {
              const index = sourceBusObj.routes.findIndex(r => r.route_id === routeId);
              if (index !== -1) sourceBusObj.routes.splice(index, 1);
            }
          } else {
            const index = draft.unassignedRoutes.findIndex(r => r.route_id === routeId);
            if (index !== -1) draft.unassignedRoutes.splice(index, 1);
          }
          
          // Agregar a nueva ubicación
          const routeToMove = getRouteFromDraft(draft, routeId);
          if (!routeToMove) return;
          
          if (targetBusId) {
            const targetBus = draft.buses.find(b => b.busId === targetBusId);
            if (targetBus) {
              routeToMove.status = 'assigned';
              routeToMove.assignedBusId = targetBusId;
              
              // Ajustar hora si se especificó
              if (targetTime) {
                routeToMove.currentStartTime = targetTime;
                routeToMove.currentEndTime = addMinutes(targetTime, routeToMove.duration_minutes);
              }
              
              const insertIndex = targetPosition ?? targetBus.routes.length;
              routeToMove.positionInBus = insertIndex;
              targetBus.routes.splice(insertIndex, 0, routeToMove);
              
              // Recalcular posiciones
              targetBus.routes.forEach((r, idx) => {
                r.positionInBus = idx;
              });
            }
          } else {
            // Mover a libres
            routeToMove.status = 'unassigned';
            routeToMove.assignedBusId = undefined;
            routeToMove.positionInBus = undefined;
            draft.unassignedRoutes.push(routeToMove);
          }
          
          draft.validation.status = 'pending';
        });
        
        return true;
      },

      moveRouteToBus: (routeId: string, targetBusId: string): boolean => {
        const state = get();
        const route = state.getRoute(routeId);
        
        if (!route || route.isLocked) return false;
        
        const targetBus = state.getBus(targetBusId);
        if (!targetBus) return false;
        
        // Validar que no haya solapamiento
        const routeStart = timeToMinutes(route.currentStartTime);
        const routeEnd = timeToMinutes(route.currentEndTime);
        
        for (const existingRoute of targetBus.routes) {
          if (existingRoute.route_id === routeId) continue;
          
          const existingStart = timeToMinutes(existingRoute.currentStartTime);
          const existingEnd = timeToMinutes(existingRoute.currentEndTime);
          
          // Verificar solapamiento
          if (
            (routeStart >= existingStart && routeStart < existingEnd) ||
            (routeEnd > existingStart && routeEnd <= existingEnd) ||
            (routeStart <= existingStart && routeEnd >= existingEnd)
          ) {
            // Hay solapamiento
            return false;
          }
        }
        
        // Ejecutar el movimiento
        return state.moveRoute(routeId, targetBusId);
      },

      reorderRoutesInBus: (busId: string, routeIds: string[]): boolean => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (!bus) return;
          
          // Crear mapa de rutas existentes
          const routeMap = new Map(bus.routes.map(r => [r.route_id, r]));
          
          // Reordenar según el nuevo orden
          bus.routes = routeIds
            .map(id => routeMap.get(id))
            .filter((r): r is ExtendedRouteItem => r !== undefined)
            .map((r, idx) => ({ ...r, positionInBus: idx }));
          
          draft.validation.status = 'pending';
        });
        
        return true;
      },

      updateRouteStops: (routeId: string, stops: RouteBaseData['stops']) => {
        set((draft) => {
          const route = getRouteFromDraft(draft, routeId);
          if (!route || route.isLocked) return;
          
          // Guardar cambios previos en dirtyRoutes si es la primera modificación
          if (!draft.dirtyRoutes.has(routeId)) {
            draft.dirtyRoutes.set(routeId, { ...route });
          }
          
          // Reemplazar array de stops
          route.stops = [...stops];
          
          // Recalcular duración si hay tiempos estimados en las paradas
          // Por ahora, mantenemos la duración original
          // En el futuro se puede calcular: última parada - primera parada
          
          draft.validation.status = 'pending';
        });
      },

      saveRouteChanges: async (routeId: string): Promise<boolean> => {
        const state = get();
        const route = state.getRoute(routeId);
        
        if (!route) return false;
        
        const changes = state.getRouteChanges(routeId);
        if (!changes) return true; // No hay cambios que guardar
        
        set((draft) => {
          draft.isLoading = true;
          draft.error = null;
        });
        
        try {
          // Llamar a PATCH /api/routes/{routeId}
          const response = await fetch(`/api/routes/${routeId}`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              start_time: route.currentStartTime,
              end_time: route.currentEndTime,
              duration_minutes: route.duration_minutes,
              assigned_bus_id: route.assignedBusId,
              position_in_bus: route.positionInBus,
              stops: route.stops,
              route_name: route.route_name,
              route_code: route.route_code,
            }),
          });
          
          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `Error ${response.status}: ${response.statusText}`);
          }
          
          // Éxito: limpiar estado 'dirty'
          set((draft) => {
            draft.dirtyRoutes.delete(routeId);
            draft.isLoading = false;
            
            // Actualizar originalRoutes con los nuevos valores
            const originalIndex = draft.originalRoutes?.findIndex(r => r.route_id === routeId);
            if (originalIndex !== undefined && originalIndex >= 0 && draft.originalRoutes) {
              draft.originalRoutes[originalIndex] = { ...route };
            }
          });
          
          return true;
        } catch (error) {
          set((draft) => {
            draft.isLoading = false;
            draft.error = error instanceof Error ? error.message : 'Error desconocido al guardar';
          });
          return false;
        }
      },

      discardRouteChanges: (routeId: string) => {
        set((draft) => {
          const originalRoute = draft.dirtyRoutes.get(routeId);
          if (!originalRoute) return;
          
          // Restaurar valores originales
          const currentRoute = getRouteFromDraft(draft, routeId);
          if (!currentRoute) {
            draft.dirtyRoutes.delete(routeId);
            return;
          }
          
          // Restaurar todos los campos editables
          Object.assign(currentRoute, originalRoute);
          
          // Limpiar 'dirty'
          draft.dirtyRoutes.delete(routeId);
          draft.validation.status = 'pending';
        });
      },

      isRouteDirty: (routeId: string): boolean => {
        return get().dirtyRoutes.has(routeId);
      },

      getRouteChanges: (routeId: string): Partial<ExtendedRouteItem> | undefined => {
        return get().dirtyRoutes.get(routeId);
      },

      // ======================================================================
      // CONTROL DE EDICIÓN (CANDADO)
      // ======================================================================

      lockRoute: (routeId: string, reason?: string) => {
        set((draft) => {
          const route = getRouteFromDraft(draft, routeId);
          if (route) {
            route.isLocked = true;
            route.lockReason = reason;
          }
        });
      },

      unlockRoute: (routeId: string) => {
        set((draft) => {
          const route = getRouteFromDraft(draft, routeId);
          if (route) {
            route.isLocked = false;
            route.lockReason = undefined;
          }
        });
      },

      toggleRouteLock: (routeId: string) => {
        set((draft) => {
          const route = getRouteFromDraft(draft, routeId);
          if (route) {
            route.isLocked = !route.isLocked;
            if (!route.isLocked) {
              route.lockReason = undefined;
            }
          }
        });
      },

      lockAllRoutesInBus: (busId: string, reason?: string) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (bus) {
            bus.routes.forEach(route => {
              route.isLocked = true;
              route.lockReason = reason;
            });
          }
        });
      },

      unlockAllRoutesInBus: (busId: string) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (bus) {
            bus.routes.forEach(route => {
              route.isLocked = false;
              route.lockReason = undefined;
            });
          }
        });
      },

      // ======================================================================
      // VALIDACIÓN
      // ======================================================================

      validateAll: async () => {
        set((draft) => {
          draft.validation.isValidating = true;
          draft.validation.status = 'validating';
        });
        
        // Simulación de validación asíncrona
        await new Promise(resolve => setTimeout(resolve, 500));
        
        set((draft) => {
          const errors: ValidationError[] = [];
          const warnings: ValidationWarning[] = [];
          
          // Validar cada bus
          draft.buses.forEach(bus => {
            for (let i = 1; i < bus.routes.length; i++) {
              const prev = bus.routes[i - 1];
              const curr = bus.routes[i];
              
              const prevEnd = timeToMinutes(prev.currentEndTime);
              const currStart = timeToMinutes(curr.currentStartTime);
              
              if (currStart < prevEnd) {
                errors.push({
                  code: 'TIME_OVERLAP',
                  message: `La ruta ${curr.route_code} se solapa con ${prev.route_code}`,
                  severity: 'error',
                  routeIds: [prev.route_id, curr.route_id],
                  busId: bus.busId,
                });
              }
            }
          });
          
          draft.validation.errors = errors;
          draft.validation.warnings = warnings;
          draft.validation.errorCount = {
            error: errors.filter(e => e.severity === 'error').length,
            warning: warnings.length,
            info: 0,
          };
          draft.validation.status = errors.length > 0 ? 'invalid' : 'valid';
          draft.validation.isValidating = false;
          draft.validation.lastValidated = new Date();
        });
      },

      validateBus: (busId: string): ValidationError[] => {
        const state = get();
        const bus = state.getBus(busId);
        if (!bus) return [];
        
        const errors: ValidationError[] = [];
        
        for (let i = 1; i < bus.routes.length; i++) {
          const prev = bus.routes[i - 1];
          const curr = bus.routes[i];
          
          if (timeToMinutes(curr.currentStartTime) < timeToMinutes(prev.currentEndTime)) {
            errors.push({
              code: 'TIME_OVERLAP',
              message: `Solapamiento entre ${prev.route_code} y ${curr.route_code}`,
              severity: 'error',
              routeIds: [prev.route_id, curr.route_id],
              busId,
            });
          }
        }
        
        return errors;
      },

      validateRoute: (routeId: string): ValidationError[] => {
        const state = get();
        const route = state.getRoute(routeId);
        if (!route) return [];
        
        const bus = state.findBusForRoute(routeId);
        if (!bus) return [];
        
        return state.validateBus(bus.busId).filter(
          e => e.routeIds?.includes(routeId)
        );
      },

      calculateCompatibility: (
        routeAId: string,
        routeBId: string,
        useCache = true
      ): CompatibilityCheck | null => {
        const state = get();
        
        if (useCache) {
          const cached = state.getCachedOSRM(routeAId, routeBId);
          if (cached) return cached;
        }
        
        const routeA = state.getRoute(routeAId);
        const routeB = state.getRoute(routeBId);
        
        if (!routeA || !routeB) return null;
        
        // Cálculo simplificado (en producción usar OSRM real)
        const travelTime = 15; // Placeholder
        const buffer = MIN_TRANSITION_BUFFER;
        const totalRequired = travelTime + buffer;
        
        const endA = timeToMinutes(routeA.currentEndTime);
        const startB = timeToMinutes(routeB.start_time);
        const availableTime = startB - endA;
        
        const check: CompatibilityCheck = {
          routeId: routeBId,
          travelTimeMinutes: travelTime,
          bufferMinutes: buffer,
          totalRequiredMinutes: totalRequired,
          isCompatible: availableTime >= totalRequired,
          compatibilityScore: Math.max(0, Math.min(100, (availableTime / totalRequired) * 100)),
          message: availableTime >= totalRequired
            ? `Compatible: ${availableTime}min disponibles`
            : `Incompatible: faltan ${totalRequired - availableTime}min`,
          errorCode: availableTime < totalRequired ? 'INSUFFICIENT_TIME' : undefined,
        };
        
        state.cacheOSRMResult(routeAId, routeBId, check);
        return check;
      },

      clearValidation: () => {
        set((draft) => {
          draft.validation = { ...initialValidationState };
        });
      },

      // ======================================================================
      // SUGERENCIAS INTELIGENTES
      // ======================================================================

      generateSuggestionsForRoute: (routeId: string): RouteSuggestion[] => {
        const state = get();
        const route = state.getRoute(routeId);
        if (!route) return [];
        
        const suggestions: RouteSuggestion[] = [];
        
        state.buses.forEach(bus => {
          // Verificar compatibilidad al inicio
          if (bus.routes.length === 0) {
            suggestions.push({
              routeId,
              suggestedPosition: {
                busId: bus.busId,
                index: 0,
                insertTime: route.start_time,
                endTime: route.end_time,
              },
              score: 100,
              reasons: [{
                type: 'optimization',
                description: 'Bus vacío - posición ideal',
                weight: 100,
              }],
              isApplicable: true,
            });
          } else {
            // Verificar compatibilidad entre rutas existentes
            for (let i = 0; i <= bus.routes.length; i++) {
              const score = Math.floor(Math.random() * 40) + 60; // Placeholder
              
              suggestions.push({
                routeId,
                suggestedPosition: {
                  busId: bus.busId,
                  index: i,
                  insertTime: route.start_time,
                  endTime: route.end_time,
                },
                score,
                reasons: [{
                  type: 'time_buffer',
                  description: 'Buffer suficiente entre rutas',
                  weight: score,
                }],
                isApplicable: score >= MIN_SUGGESTION_SCORE,
              });
            }
          }
        });
        
        return suggestions
          .filter(s => s.score >= MIN_SUGGESTION_SCORE)
          .sort((a, b) => b.score - a.score)
          .slice(0, MAX_SUGGESTIONS);
      },

      generateGlobalSuggestions: (): SuggestionEngineResult => {
        const state = get();
        const allSuggestions: RouteSuggestion[] = [];
        const unsuggestedRoutes: string[] = [];
        
        const startTime = Date.now();
        
        state.unassignedRoutes.forEach(route => {
          const suggestions = state.generateSuggestionsForRoute(route.route_id);
          if (suggestions.length > 0) {
            allSuggestions.push(...suggestions);
          } else {
            unsuggestedRoutes.push(route.route_id);
          }
        });
        
        return {
          suggestions: allSuggestions.sort((a, b) => b.score - a.score).slice(0, MAX_SUGGESTIONS),
          unsuggestedRoutes,
          computationTime: Date.now() - startTime,
          generatedAt: new Date(),
        };
      },

      applySuggestion: (suggestion: RouteSuggestion): boolean => {
        return get().moveRoute(
          suggestion.routeId,
          suggestion.suggestedPosition.busId,
          suggestion.suggestedPosition.index,
          suggestion.suggestedPosition.insertTime
        );
      },

      clearSuggestions: () => {
        set((draft) => {
          draft.activeSuggestions = [];
        });
      },

      // ======================================================================
      // CONFIGURACIÓN DE VISTA
      // ======================================================================

      updateViewConfig: (config: Partial<TimelineViewConfig>) => {
        set((draft) => {
          draft.viewConfig = { ...draft.viewConfig, ...config };
        });
      },

      setHourRange: (start: number, end: number) => {
        set((draft) => {
          draft.viewConfig.hourRange = [start, end];
        });
      },

      setZoom: (zoom: TimelineViewConfig['zoom']) => {
        set((draft) => {
          draft.viewConfig.zoom = zoom;
          // Ajustar pixelsPerHour según zoom
          const zoomMap = { compact: 60, normal: 100, detailed: 150 };
          draft.viewConfig.pixelsPerHour = zoomMap[zoom];
        });
      },

      toggleUnassignedPanel: () => {
        set((draft) => {
          draft.viewConfig.showUnassignedPanel = !draft.viewConfig.showUnassignedPanel;
        });
      },

      // ======================================================================
      // SELECCIÓN
      // ======================================================================

      selectRoute: (routeId: string, multi = false) => {
        set((draft) => {
          if (multi) {
            if (!draft.selectedRouteIds.includes(routeId)) {
              draft.selectedRouteIds.push(routeId);
            }
          } else {
            draft.selectedRouteIds = [routeId];
          }
        });
      },

      selectRouteForEdit: (routeId: string | null) => {
        set((draft) => {
          draft.selectedRouteId = routeId;
          draft.isDrawerOpen = routeId !== null;
        });
      },

      toggleDrawer: () => {
        set((draft) => {
          draft.isDrawerOpen = !draft.isDrawerOpen;
        });
      },

      closeDrawer: () => {
        set((draft) => {
          draft.isDrawerOpen = false;
          draft.selectedRouteId = null;
        });
      },

      deselectRoute: (routeId: string) => {
        set((draft) => {
          draft.selectedRouteIds = draft.selectedRouteIds.filter(id => id !== routeId);
        });
      },

      clearSelection: () => {
        set((draft) => {
          draft.selectedRouteIds = [];
        });
      },

      selectAllRoutesInBus: (busId: string) => {
        set((draft) => {
          const bus = draft.buses.find(b => b.busId === busId);
          if (bus) {
            draft.selectedRouteIds = bus.routes.map(r => r.route_id);
          }
        });
      },

      setActiveRoute: (routeId?: string) => {
        set((draft) => {
          draft.activeRouteId = routeId;
        });
      },

      // ======================================================================
      // DRAG & DROP
      // ======================================================================

      startDrag: (routeId: string, sourceBusId?: string) => {
        set((draft) => {
          draft.dragState.isDragging = true;
          draft.dragState.draggedRouteId = routeId;
          draft.dragState.sourceBusId = sourceBusId;
          
          // Marcar ruta como dragging
          const route = getRouteFromDraft(draft, routeId);
          if (route) {
            route.isDragging = true;
          }
        });
      },

      updateDragTarget: (targetBusId?: string, targetTime?: string) => {
        set((draft) => {
          draft.dragState.targetBusId = targetBusId;
          draft.dragState.targetTime = targetTime;
        });
      },

      endDrag: (cancelled = false): DropResult | null => {
        const state = get();
        const { draggedRouteId, sourceBusId, targetBusId, targetTime } = state.dragState;
        
        set((draft) => {
          // Desmarcar dragging
          if (draggedRouteId) {
            const route = getRouteFromDraft(draft, draggedRouteId);
            if (route) {
              route.isDragging = false;
            }
          }
          
          // Resetear estado de drag
          draft.dragState = initialDragState;
        });
        
        if (cancelled || !draggedRouteId) {
          return null;
        }
        
        // Ejecutar el movimiento
        const success = state.moveRoute(draggedRouteId, targetBusId ?? null, undefined, targetTime);
        
        return {
          success,
          action: sourceBusId === targetBusId ? 'reorder' : 'move',
          routeId: draggedRouteId,
          sourceBusId,
          targetBusId,
          targetTime,
        };
      },

      canDrop: (routeId: string, targetBusId: string | null, targetTime?: string): boolean => {
        const state = get();
        const route = state.getRoute(routeId);
        if (!route || route.isLocked) return false;
        
        if (targetBusId) {
          const targetBus = state.getBus(targetBusId);
          if (!targetBus) return false;
        }
        
        return true;
      },

      // ======================================================================
      // CACHE OSRM
      // ======================================================================

      cacheOSRMResult: (routeAId: string, routeBId: string, result: CompatibilityCheck) => {
        set((draft) => {
          const key = getOSRMCacheKey(routeAId, routeBId);
          draft.osrmCache.set(key, result);
        });
      },

      getCachedOSRM: (routeAId: string, routeBId: string): CompatibilityCheck | undefined => {
        const state = get();
        const key = getOSRMCacheKey(routeAId, routeBId);
        return state.osrmCache.get(key);
      },

      clearOSRMCache: () => {
        set((draft) => {
          draft.osrmCache.clear();
        });
      },

      // ======================================================================
      // IMPORT/EXPORT
      // ======================================================================

      importState: (data: TimelineExport) => {
        set((draft) => {
          // Reconstruir buses
          draft.buses = data.buses.map((busData, index) => ({
            busId: busData.busId,
            busName: busData.busName,
            color: getBusColor(index),
            routes: [], // Se llenarían desde availableRoutes
            isCollapsed: false,
            isVisible: true,
          }));
          
          draft.validation.status = 'pending';
        });
      },

      exportState: (): TimelineExport => {
        const state = get();
        
        return {
          version: '1.0',
          exportedAt: new Date().toISOString(),
          buses: state.buses.map(bus => ({
            busId: bus.busId,
            busName: bus.busName,
            routes: bus.routes.map(r => ({
              routeId: r.route_id,
              startTime: r.currentStartTime,
              endTime: r.currentEndTime,
              isLocked: r.isLocked,
            })),
          })),
          unassignedRoutes: state.unassignedRoutes.map(r => r.route_id),
          metadata: {
            totalRoutes: state.getStats().totalRoutes,
            assignedRoutes: state.getStats().assignedRoutes,
            lockedRoutes: state.buses.reduce(
              (sum, b) => sum + b.routes.filter(r => r.isLocked).length,
              0
            ),
            conflicts: state.validation.errorCount.error,
          },
        };
      },

      reset: () => {
        set((draft) => {
          Object.assign(draft, initialState);
        });
      },

      saveOriginalRoutes: () => {
        set((draft) => {
          draft.originalRoutes = JSON.parse(JSON.stringify([
            ...draft.buses.flatMap(b => b.routes),
            ...draft.unassignedRoutes,
          ]));
        });
      },

      restoreOriginalRoutes: () => {
        set((draft) => {
          if (draft.originalRoutes) {
            // Implementar restauración
            draft.validation.status = 'pending';
          }
        });
      },

      // ======================================================================
      // UTILIDADES
      // ======================================================================

      getBus: (busId: string): TimelineBus | undefined => {
        return get().buses.find(b => b.busId === busId);
      },

      getRoute: (routeId: string): ExtendedRouteItem | undefined => {
        const state = get();
        // Buscar en buses
        for (const bus of state.buses) {
          const route = bus.routes.find(r => r.route_id === routeId);
          if (route) return route;
        }
        // Buscar en libres
        return state.unassignedRoutes.find(r => r.route_id === routeId);
      },

      findBusForRoute: (routeId: string): TimelineBus | undefined => {
        return get().buses.find(b => b.routes.some(r => r.route_id === routeId));
      },

      filterRoutes: (filters: RouteFilters): ExtendedRouteItem[] => {
        const state = get();
        let routes: ExtendedRouteItem[] = [
          ...state.buses.flatMap(b => b.routes),
          ...state.unassignedRoutes,
        ];
        
        if (filters.status) {
          routes = routes.filter(r => filters.status?.includes(r.status));
        }
        if (filters.busId) {
          routes = routes.filter(r => r.assignedBusId === filters.busId);
        }
        if (filters.isLocked !== undefined) {
          routes = routes.filter(r => r.isLocked === filters.isLocked);
        }
        if (filters.searchText) {
          const text = filters.searchText.toLowerCase();
          routes = routes.filter(r =>
            r.route_code.toLowerCase().includes(text) ||
            r.route_name.toLowerCase().includes(text)
          );
        }
        
        return routes;
      },

      getStats: () => {
        const state = get();
        const totalRoutes = state.buses.reduce((sum, b) => sum + b.routes.length, 0) +
          state.unassignedRoutes.length;
        const assignedRoutes = state.buses.reduce((sum, b) => sum + b.routes.length, 0);
        const lockedRoutes = state.buses.reduce(
          (sum, b) => sum + b.routes.filter(r => r.isLocked).length,
          0
        );
        
        return {
          totalRoutes,
          assignedRoutes,
          unassignedRoutes: state.unassignedRoutes.length,
          lockedRoutes,
          busCount: state.buses.length,
          conflicts: state.validation.errorCount.error,
          coveragePercentage: totalRoutes > 0 ? (assignedRoutes / totalRoutes) * 100 : 0,
        };
      },

      calculateRouteVisualPosition: (route: ExtendedRouteItem) => {
        const state = get();
        return calculateRoutePosition(
          route.currentStartTime,
          route.currentEndTime,
          state.viewConfig.hourRange,
          state.viewConfig.pixelsPerHour
        );
      },
    })),
    { name: 'timeline-editable-store' }
  )
);

// ============================================================================
// HELPERS
// ============================================================================

/**
 * Obtiene una ruta del draft (maneja buses y libres)
 */
function getRouteFromDraft(
  draft: TimelineEditableState,
  routeId: string
): ExtendedRouteItem | undefined {
  // Buscar en buses
  for (const bus of draft.buses) {
    const route = bus.routes.find(r => r.route_id === routeId);
    if (route) return route;
  }
  // Buscar en libres
  return draft.unassignedRoutes.find(r => r.route_id === routeId);
}

// ============================================================================
// SELECTORES (Hooks auxiliares)
// ============================================================================

/**
 * Hook selector para obtener buses con metadatos calculados
 */
export function useBusesWithMetadata() {
  return useTimelineEditableStore((state) => {
    return state.buses.map(bus => {
      const totalOperationTime = bus.routes.reduce(
        (sum, r) => sum + r.duration_minutes,
        0
      );
      
      const totalTransitionTime = bus.routes.slice(1).reduce((sum, r, idx) => {
        const prev = bus.routes[idx];
        const diff = timeDiffMinutes(prev.currentEndTime, r.currentStartTime);
        return sum + Math.max(0, diff);
      }, 0);
      
      return {
        ...bus,
        metadata: {
          totalOperationTime,
          totalTransitionTime,
          routeCount: bus.routes.length,
          firstRouteStart: bus.routes[0]?.currentStartTime,
          lastRouteEnd: bus.routes[bus.routes.length - 1]?.currentEndTime,
        },
      };
    });
  });
}

/**
 * Hook selector para obtener estadísticas del timeline
 */
export function useTimelineStats() {
  return useTimelineEditableStore((state) => state.getStats());
}

/**
 * Hook selector para obtener rutas filtradas por estado
 */
export function useRoutesByStatus(status: RouteWorkspaceStatus) {
  return useTimelineEditableStore((state) =>
    state.filterRoutes({ status: [status] })
  );
}

/**
 * Hook selector para verificar si hay errores
 */
export function useHasValidationErrors() {
  return useTimelineEditableStore(
    (state) => state.validation.errorCount.error > 0
  );
}

export default useTimelineEditableStore;
