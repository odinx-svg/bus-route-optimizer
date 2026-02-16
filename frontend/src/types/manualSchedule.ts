/**
 * Tipos TypeScript para el Editor Manual de Horarios
 * 
 * @module types/manualSchedule
 * @version 1.0.0
 */

// ============================================================================
// ENUMS
// ============================================================================

/** Estado de compatibilidad entre rutas consecutivas */
export type CompatibilityStatus = 'compatible' | 'incompatible' | 'pending' | 'unknown';

/** Estado global de validación del horario */
export type ValidationStatus = 'valid' | 'invalid' | 'pending' | 'unvalidated';

/** Estado de una ruta en la paleta */
export type RouteAvailabilityStatus = 'available' | 'assigned' | 'incompatible';

// ============================================================================
// CORE TYPES
// ============================================================================

/**
 * Representa una parada de autobús
 */
export interface Stop {
  stop_id: string;
  stop_name: string;
  latitude: number;
  longitude: number;
}

/**
 * Representa una ruta disponible (pieza de puzzle)
 */
export interface Route {
  route_id: string;
  route_name: string;
  school: string;
  stops: Stop[];
  /** Tiempo de inicio en formato HH:mm */
  start_time: string;
  /** Tiempo de fin en formato HH:mm */
  end_time: string;
  /** Duración en minutos */
  duration_minutes: number;
  /** Coordenadas del punto de inicio [lat, lng] */
  start_coords: [number, number];
  /** Coordenadas del punto de fin [lat, lng] */
  end_coords: [number, number];
  /** Color asignado para visualización */
  color?: string;
}

/**
 * Ruta asignada a un bus con metadatos adicionales
 */
export interface AssignedRoute {
  /** ID único de la asignación (para distinguir múltiples usos de la misma ruta) */
  assignmentId: string;
  routeId: string;
  /** Hora de inicio calculada (puede diferir de la ruta original si hay transiciones) */
  startTime: string;
  /** Hora de fin calculada */
  endTime: string;
  /** Posición en la secuencia del bus (0-based) */
  position: number;
  /** Estado de compatibilidad con la ruta anterior */
  compatibility: CompatibilityStatus;
  /** Tiempo de transición desde la ruta anterior (en minutos) */
  transitionTime?: number;
  /** Motivo de incompatibilidad si aplica */
  incompatibilityReason?: string;
}

/**
 * Bus en construcción con sus rutas asignadas
 */
export interface BusInConstruction {
  /** ID único del bus */
  busId: string;
  /** Nombre/identificador legible */
  busName: string;
  /** Color asignado para visualización */
  color: string;
  /** Rutas asignadas ordenadas por posición */
  assignedRoutes: AssignedRoute[];
  /** Tiempo total de operación en minutos */
  totalOperationTime?: number;
  /** Tiempo total de transición entre rutas */
  totalTransitionTime?: number;
}

// ============================================================================
// CACHE TYPES
// ============================================================================

/**
 * Key para el cache de OSRM: "routeA_end_routeB_start"
 */
export type OSRMCacheKey = string;

/**
 * Entrada del cache de tiempos OSRM
 */
export interface OSRMCacheEntry {
  /** Tiempo de viaje en minutos */
  durationMinutes: number;
  /** Distancia en metros */
  distanceMeters: number;
  /** Timestamp del cálculo */
  computedAt: number;
  /** Polilínea de la ruta (opcional, para visualización) */
  geometry?: string;
}

/**
 * Cache de tiempos OSRM calculados
 */
export type OSRMCache = Map<OSRMCacheKey, OSRMCacheEntry>;

// ============================================================================
// VALIDATION TYPES
// ============================================================================

/**
 * Par de rutas incompatibles
 */
export interface InvalidRoutePair {
  /** ID de la ruta anterior */
  routeA: string;
  /** ID de la siguiente ruta */
  routeB: string;
  /** Motivo de la incompatibilidad */
  reason: string;
  /** Tipo de conflicto */
  conflictType: 'time_overlap' | 'insufficient_transition' | 'unreachable';
  /** Tiempo mínimo requerido (si aplica) */
  requiredTime?: number;
  /** Tiempo disponible (si aplica) */
  availableTime?: number;
}

/**
 * Resultado de validación de una asignación específica
 */
export interface AssignmentValidation {
  assignmentId: string;
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

/**
 * Error de validación
 */
export interface ValidationError {
  code: string;
  message: string;
  field?: string;
}

/**
 * Advertencia de validación
 */
export interface ValidationWarning {
  code: string;
  message: string;
  suggestion?: string;
}

// ============================================================================
// STATE TYPES
// ============================================================================

/**
 * Estado global del editor manual de horarios
 */
export interface ManualScheduleState {
  // Buses en construcción
  buses: BusInConstruction[];
  
  // Rutas disponibles (piezas de puzzle)
  availableRoutes: Route[];
  
  // IDs de rutas ya asignadas (para filtrar disponibles)
  assignedRouteIds: Set<string>;
  
  // Cache de tiempos OSRM calculados
  osrmCache: OSRMCache;
  
  // Estado de validación global
  validationStatus: ValidationStatus;
  
  // Pares de rutas inválidas detectadas
  invalidPairs: InvalidRoutePair[];
  
  // Validaciones por asignación
  assignmentValidations: Map<string, AssignmentValidation>;
  
  // Estado de carga
  isLoading: boolean;
  
  // Error global
  error: string | null;
}

/**
 * Acciones del store
 */
export interface ManualScheduleActions {
  // CRUD de buses
  addBus: (busName?: string) => string;
  removeBus: (busId: string) => void;
  updateBusName: (busId: string, name: string) => void;
  reorderBuses: (busIds: string[]) => void;
  
  // CRUD de asignaciones
  assignRoute: (busId: string, routeId: string, position?: number) => string | null;
  unassignRoute: (busId: string, assignmentId: string) => void;
  moveRoute: (fromBusId: string, toBusId: string, assignmentId: string, newPosition?: number) => void;
  reorderRoutesInBus: (busId: string, assignmentIds: string[]) => void;
  updateRouteStartTime: (busId: string, assignmentId: string, newStartTime: string) => void;
  
  // Gestión de rutas disponibles
  setAvailableRoutes: (routes: Route[]) => void;
  addAvailableRoute: (route: Route) => void;
  removeAvailableRoute: (routeId: string) => void;
  
  // Cache OSRM
  getOSRMTime: (routeAId: string, routeBId: string) => OSRMCacheEntry | undefined;
  setOSRMTime: (routeAId: string, routeBId: string, entry: OSRMCacheEntry) => void;
  clearOSRMCache: () => void;
  
  // Validación
  validateSchedule: () => Promise<void>;
  validateAssignment: (busId: string, assignmentId: string) => AssignmentValidation;
  setValidationStatus: (status: ValidationStatus) => void;
  
  // Estado global
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
  
  // Utilidades
  getBusById: (busId: string) => BusInConstruction | undefined;
  getRouteById: (routeId: string) => Route | undefined;
  getAssignmentById: (assignmentId: string) => { bus: BusInConstruction; assignment: AssignedRoute } | undefined;
  getCompatibleRoutes: (routeId: string) => Route[];
  canRoutesBeConsecutive: (routeAId: string, routeBId: string) => boolean;
  
  // Exportar/Importar
  exportSchedule: () => object;
  importSchedule: (data: object) => void;
}

/**
 * Store completo (estado + acciones)
 */
export type ManualScheduleStore = ManualScheduleState & ManualScheduleActions;

// ============================================================================
// DnD TYPES
// ============================================================================

/**
 * Tipos de elementos arrastrables
 */
export type DraggableType = 'route' | 'assigned-route' | 'bus';

/**
 * Datos del elemento arrastrado (ruta de la paleta)
 */
export interface DraggableRouteData {
  type: 'route';
  routeId: string;
}

/**
 * Datos del elemento arrastrado (ruta ya asignada)
 */
export interface DraggableAssignedRouteData {
  type: 'assigned-route';
  assignmentId: string;
  routeId: string;
  busId: string;
  position: number;
}

/**
 * Datos del elemento arrastrado (bus completo)
 */
export interface DraggableBusData {
  type: 'bus';
  busId: string;
}

/**
 * Unión de todos los tipos de datos arrastrables
 */
export type DraggableData = DraggableRouteData | DraggableAssignedRouteData | DraggableBusData;

// ============================================================================
// COMPONENT PROPS
// ============================================================================

/**
 * Props del componente WorkspaceArea
 */
export interface WorkspaceAreaProps {
  className?: string;
}

/**
 * Props del componente BusRow
 */
export interface BusRowProps {
  bus: BusInConstruction;
  isActive?: boolean;
  className?: string;
}

/**
 * Props del componente AssignedRouteBlock
 */
export interface AssignedRouteBlockProps {
  assignment: AssignedRoute;
  route: Route;
  busId: string;
  isDragging?: boolean;
  className?: string;
}

/**
 * Props del componente RoutesPalette
 */
export interface RoutesPaletteProps {
  className?: string;
}

/**
 * Props del componente DraggableRouteCard
 */
export interface DraggableRouteCardProps {
  route: Route;
  status: RouteAvailabilityStatus;
  isDraggable?: boolean;
  className?: string;
}

/**
 * Props del componente CompatibilityPreview
 */
export interface CompatibilityPreviewProps {
  routeA?: Route;
  routeB?: Route;
  isVisible: boolean;
  position?: { x: number; y: number };
}

// ============================================================================
// API TYPES
// ============================================================================

/**
 * Request para calcular tiempo OSRM entre dos puntos
 */
export interface OSRMTimeRequest {
  fromLat: number;
  fromLng: number;
  toLat: number;
  toLng: number;
  routeAId: string;
  routeBId: string;
}

/**
 * Response del cálculo OSRM
 */
export interface OSRMTimeResponse {
  durationMinutes: number;
  distanceMeters: number;
  geometry?: string;
}

/**
 * Request para validar una secuencia de rutas
 */
export interface ValidateSequenceRequest {
  routeIds: string[];
}

/**
 * Response de validación de secuencia
 */
export interface ValidateSequenceResponse {
  isValid: boolean;
  invalidPairs: InvalidRoutePair[];
  totalDuration: number;
  totalTransitionTime: number;
}
