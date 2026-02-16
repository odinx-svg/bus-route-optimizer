/**
 * Tipos TypeScript para el Timeline Editable
 * 
 * Sistema de gestión de horarios con funcionalidades avanzadas:
 * - RouteBlock con candado de edición
 * - Validación OSRM de compatibilidad
 * - Rutas libres (no asignadas a bus)
 * - Posicionamiento por hora exacta
 * - Sugerencias inteligentes de ordenación
 * 
 * @module types/timelineEditable
 * @version 1.0.0
 */

// ============================================================================
// ENUMS Y TIPOS BÁSICOS
// ============================================================================

/** Estado de compatibilidad entre rutas consecutivas */
export type CompatibilityStatus = 'compatible' | 'incompatible' | 'warning' | 'pending' | 'unknown';

/** Estado de una ruta en el workspace */
export type RouteWorkspaceStatus = 'assigned' | 'unassigned' | 'conflict' | 'locked';

/** Estado global de validación del horario */
export type ValidationStatus = 'valid' | 'invalid' | 'pending' | 'validating' | 'unvalidated';

/** Tipo de acción de drag & drop */
export type DragAction = 'move' | 'reorder' | 'assign' | 'unassign';

/** Nivel de zoom de la timeline */
export type TimelineZoom = 'compact' | 'normal' | 'detailed';

/** Dirección de transición (para OSRM) */
export type TransitionDirection = 'entry' | 'exit' | 'both';

// ============================================================================
// COORDENADAS Y GEOLOCALIZACIÓN
// ============================================================================

/**
 * Coordenadas geográficas
 */
export interface Coordinates {
  lat: number;
  lon: number;
}

/**
 * Datos geográficos completos de una ruta
 */
export interface RouteGeography {
  startCoordinates: Coordinates;
  endCoordinates: Coordinates;
  origin: string;
  destination: string;
  distanceMeters?: number;
  estimatedDurationMinutes?: number;
}

// ============================================================================
// COMPATIBILIDAD Y VALIDACIÓN
// ============================================================================

/**
 * Resultado de validación de compatibilidad entre dos rutas
 */
export interface CompatibilityCheck {
  /** ID de la ruta con la que se verifica compatibilidad */
  routeId: string;
  /** Tiempo de viaje calculado entre rutas (minutos) */
  travelTimeMinutes: number;
  /** Buffer de seguridad aplicado (minutos) */
  bufferMinutes: number;
  /** Tiempo total requerido (viaje + buffer) */
  totalRequiredMinutes: number;
  /** Indica si la transición es compatible */
  isCompatible: boolean;
  /** Nivel de compatibilidad (0-100) */
  compatibilityScore: number;
  /** Mensaje explicativo */
  message?: string;
  /** Código de error si no es compatible */
  errorCode?: 'INSUFFICIENT_TIME' | 'OVERLAPPING' | 'UNREACHABLE' | 'CALCULATION_ERROR';
  /** Detalles adicionales del cálculo OSRM */
  osrmDetails?: {
    distanceMeters: number;
    durationMinutes: number;
    geometry?: string;
    computedAt: Date;
  };
}

/**
 * Resumen de compatibilidad de una ruta con sus vecinos
 */
export interface RouteCompatibility {
  /** Compatibilidad con la ruta anterior */
  previousRoute?: CompatibilityCheck;
  /** Compatibilidad con la ruta siguiente */
  nextRoute?: CompatibilityCheck;
  /** Estado global de compatibilidad */
  overallStatus: CompatibilityStatus;
}

/**
 * Error de validación individual
 */
export interface ValidationError {
  /** Código único del error */
  code: string;
  /** Mensaje descriptivo */
  message: string;
  /** Campo o elemento relacionado */
  field?: string;
  /** IDs de rutas involucradas */
  routeIds?: string[];
  /** ID del bus involucrado */
  busId?: string;
  /** Nivel de severidad */
  severity: 'error' | 'warning' | 'info';
}

/**
 * Advertencia de validación
 */
export interface ValidationWarning {
  code: string;
  message: string;
  suggestion?: string;
  routeId?: string;
  busId?: string;
}

// ============================================================================
// ROUTE BLOCK (PIEZA DE LEGO)
// ============================================================================

/**
 * Datos base de una ruta (del sistema original)
 */
export interface RouteBaseData {
  route_id: string;
  route_code: string;
  route_name: string;
  school: string;
  start_time: string;  // "HH:mm"
  end_time: string;    // "HH:mm"
  duration_minutes: number;
  type: 'entry' | 'exit';
  stops: Array<{
    stop_id: string;
    stop_name: string;
    latitude: number;
    longitude: number;
  }>;
  color?: string;
}

/**
 * Item de ruta extendido para el timeline editable
 * Representa una "pieza de lego" que puede manipularse
 */
export interface ExtendedRouteItem extends RouteBaseData, RouteGeography {
  // ==========================================================================
  // Control de Edición (Candado)
  // ==========================================================================
  
  /** 
   * Si la ruta puede ser editada (movida, cambio de hora)
   * @default true
   */
  isEditable: boolean;
  
  /**
   * Si la ruta está bloqueada (candado cerrado)
   * Cuando isLocked=true, no se puede mover ni modificar
   * @default false
   */
  isLocked: boolean;
  
  /**
   * Razón del bloqueo (para mostrar al usuario)
   */
  lockReason?: string;
  
  /**
   * ID del bus original de la optimización
   * Útil para saber de dónde viene inicialmente
   */
  originalBusId?: string;
  
  // ==========================================================================
  // Estado en el Workspace
  // ==========================================================================
  
  /** Estado actual de la ruta */
  status: RouteWorkspaceStatus;
  
  /** ID del bus al que está asignada (si aplica) */
  assignedBusId?: string;
  
  /** 
   * Posición en el bus (índice en el array de rutas)
   * Solo relevante cuando status === 'assigned'
   */
  positionInBus?: number;
  
  /** 
   * Hora de inicio actual (puede diferir de la original)
   * Se actualiza cuando hay conflictos de compatibilidad
   */
  currentStartTime: string;
  
  /** Hora de fin actual calculada */
  currentEndTime: string;
  
  // ==========================================================================
  // Validación
  // ==========================================================================
  
  /** Resultados de validación de compatibilidad */
  compatibility?: RouteCompatibility;
  
  /** 
   * Timestamp de última validación
   */
  lastValidated?: Date;
  
  // ==========================================================================
  // Metadatos UI
  // ==========================================================================
  
  /** 
   * Si está seleccionada (para operaciones multi-select)
   * @default false
   */
  isSelected?: boolean;
  
  /** 
   * Si está siendo arrastrada
   * @default false
   */
  isDragging?: boolean;
  
  /** 
   * Nivel de opacidad (para efectos visuales)
   * @default 1
   */
  opacity?: number;
}

// ============================================================================
// BUS EN TIMELINE
// ============================================================================

/**
 * Estructura de un bus en el timeline editable
 */
export interface TimelineBus {
  /** ID único del bus */
  busId: string;
  
  /** Nombre/identificador legible */
  busName: string;
  
  /** Color asignado para visualización */
  color: string;
  
  /** 
   * Rutas asignadas ordenadas por hora de inicio
   * El orden en el array representa la secuencia
   */
  routes: ExtendedRouteItem[];
  
  /** 
   * Si la fila está colapsada en la UI
   * @default false
   */
  isCollapsed: boolean;
  
  /**
   * Si el bus está visible en la vista actual
   * @default true
   */
  isVisible: boolean;
  
  /**
   * Metadatos calculados
   */
  metadata?: {
    totalOperationTime: number;
    totalTransitionTime: number;
    routeCount: number;
    firstRouteStart: string;
    lastRouteEnd: string;
  };
}

// ============================================================================
// CONFIGURACIÓN DE VISTA
// ============================================================================

/**
 * Configuración de la vista del timeline
 */
export interface TimelineViewConfig {
  /** Rango de horas visible [inicio, fin] */
  hourRange: [number, number];  // Ej: [6, 22]
  
  /** 
   * Mostrar panel de rutas no asignadas
   * @default true
   */
  showUnassignedPanel: boolean;
  
  /** 
   * Ajustar a minutos exactos (grid)
   * @default true
   */
  snapToGrid: boolean;
  
  /** 
   * Tamaño del grid en minutos (para snap)
   * @default 5
   */
  gridSizeMinutes: number;
  
  /** 
   * Validación automática habilitada
   * @default true
   */
  validationEnabled: boolean;
  
  /** Nivel de zoom actual */
  zoom: TimelineZoom;
  
  /** 
   * Anchura de una hora en píxeles (para cálculos de posición)
   * @default 100
   */
  pixelsPerHour: number;
  
  /** 
   * Mostrar líneas de compatibilidad entre rutas
   * @default true
   */
  showCompatibilityLines: boolean;
  
  /** 
   * Mostrar tooltips detallados
   * @default true
   */
  showDetailedTooltips: boolean;
  
  /** 
   * Colapsar buses sin rutas
   * @default false
   */
  hideEmptyBuses: boolean;
}

// ============================================================================
// ESTADO GLOBAL
// ============================================================================

/**
 * Estado de validación global del timeline
 */
export interface TimelineValidationState {
  /** Si está validando actualmente */
  isValidating: boolean;
  
  /** Errores detectados */
  errors: ValidationError[];
  
  /** Advertencias detectadas */
  warnings: ValidationWarning[];
  
  /** Timestamp de última validación */
  lastValidated?: Date;
  
  /** Estado global */
  status: ValidationStatus;
  
  /** Contador de errores por severidad */
  errorCount: {
    error: number;
    warning: number;
    info: number;
  };
}

/**
 * Estado completo del Timeline Editable
 */
export interface TimelineEditableState {
  // ==========================================================================
  // Datos Principales
  // ==========================================================================
  
  /** Buses con sus rutas asignadas */
  buses: TimelineBus[];
  
  /** Rutas no asignadas (libres) */
  unassignedRoutes: ExtendedRouteItem[];
  
  /** Rutas originales (backup para reset) */
  originalRoutes?: ExtendedRouteItem[];
  
  // ==========================================================================
  // Configuración
  // ==========================================================================
  
  viewConfig: TimelineViewConfig;
  
  // ==========================================================================
  // Validación
  // ==========================================================================
  
  validation: TimelineValidationState;
  
  // ==========================================================================
  // Estado UI
  // ==========================================================================
  
  /** 
   * IDs de rutas seleccionadas (multi-select)
   */
  selectedRouteIds: string[];
  
  /** 
   * ID de la ruta activa (hover o click)
   */
  activeRouteId?: string;
  
  /** 
   * ID de la ruta seleccionada para edición (drawer)
   */
  selectedRouteId: string | null;
  
  /** 
   * Si el drawer de edición está abierto
   */
  isDrawerOpen: boolean;
  
  /** 
   * Estado de drag & drop
   */
  dragState: {
    isDragging: boolean;
    draggedRouteId?: string;
    sourceBusId?: string;
    targetBusId?: string;
    targetTime?: string;
    possibleDropTargets: string[];
  };
  
  /** 
   * Sugerencias activas
   */
  activeSuggestions: RouteSuggestion[];
  
  // ==========================================================================
  // Estado de Carga
  // ==========================================================================
  
  isLoading: boolean;
  error: string | null;
  
  // ==========================================================================
  // Cache
  // ==========================================================================
  
  /** Cache de cálculos OSRM */
  osrmCache: Map<string, CompatibilityCheck>;
  
  // ==========================================================================
  // Estado de Edición
  // ==========================================================================
  
  /** 
   * Mapa de rutas con cambios sin guardar (dirty)
   * La key es el routeId, el valor es la ruta original antes de modificaciones
   */
  dirtyRoutes: Map<string, ExtendedRouteItem>;
}

// ============================================================================
// SUGERENCIAS INTELIGENTES
// ============================================================================

/**
 * Razón de una sugerencia
 */
export interface SuggestionReason {
  /** Tipo de razón */
  type: 'time_buffer' | 'geographic_proximity' | 'route_sequence' | 'optimization';
  /** Descripción legible */
  description: string;
  /** Peso de esta razón en el score (0-100) */
  weight: number;
}

/**
 * Sugerencia de posición para una ruta
 */
export interface RouteSuggestion {
  /** ID de la ruta a posicionar */
  routeId: string;
  
  /** Posición sugerida */
  suggestedPosition: {
    /** ID del bus objetivo */
    busId: string;
    /** Índice de inserción en el array de rutas */
    index: number;
    /** Hora exacta de inicio sugerida */
    insertTime: string;
    /** Hora de fin calculada */
    endTime: string;
  };
  
  /** 
   * Score de 0-100 
   * Mayor = mejor compatibilidad
   */
  score: number;
  
  /** Razones que justifican la sugerencia */
  reasons: SuggestionReason[];
  
  /** 
   * Impacto esperado si se aplica
   */
  impact?: {
    timeSaved: number;
    conflictsResolved: number;
    newConflicts: number;
  };
  
  /** Si es aplicable en el estado actual */
  isApplicable: boolean;
  
  /** Razón por la que no es aplicable (si aplica) */
  notApplicableReason?: string;
}

/**
 * Resultado del motor de sugerencias
 */
export interface SuggestionEngineResult {
  /** Sugerencias ordenadas por score */
  suggestions: RouteSuggestion[];
  /** Rutas sin sugerencias válidas */
  unsuggestedRoutes: string[];
  /** Tiempo de cálculo (ms) */
  computationTime: number;
  /** Timestamp de generación */
  generatedAt: Date;
}

// ============================================================================
// DRAG & DROP
// ============================================================================

/**
 * Datos de un elemento arrastrable (RouteBlock)
 */
export interface DraggableRouteData {
  type: 'route-block';
  routeId: string;
  routeCode: string;
  sourceBusId?: string;
  isLocked: boolean;
  startTime: string;
  endTime: string;
}

/**
 * Datos de una zona de drop (hora específica)
 */
export interface DroppableZoneData {
  type: 'hour-zone' | 'bus-track' | 'unassigned-panel';
  busId?: string;
  hour?: number;
  accepts: string[];
}

/**
 * Resultado de una operación de drop
 */
export interface DropResult {
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

// ============================================================================
// EVENTOS
// ============================================================================

/**
 * Evento de cambio en el timeline
 */
export interface TimelineChangeEvent {
  type: 'route_moved' | 'route_locked' | 'route_unlocked' | 'time_changed' | 'route_added' | 'route_removed';
  routeId: string;
  busId?: string;
  previousValue?: unknown;
  newValue?: unknown;
  timestamp: Date;
  userAction: boolean;
}

/**
 * Historial de cambios (para undo/redo)
 */
export interface TimelineHistory {
  past: TimelineEditableState[];
  present: TimelineEditableState;
  future: TimelineEditableState[];
  canUndo: boolean;
  canRedo: boolean;
}

// ============================================================================
// PROPS DE COMPONENTES
// ============================================================================

/**
 * Props del componente TimelineEditable principal
 */
export interface TimelineEditableProps {
  /** Buses iniciales (de la optimización) */
  initialBuses?: TimelineBus[];
  /** Rutas disponibles no asignadas */
  initialUnassignedRoutes?: ExtendedRouteItem[];
  /** Configuración inicial de vista */
  initialViewConfig?: Partial<TimelineViewConfig>;
  /** Callback cuando cambia el estado */
  onStateChange?: (state: TimelineEditableState) => void;
  /** Callback cuando hay errores de validación */
  onValidationError?: (errors: ValidationError[]) => void;
  /** Callback al aplicar una sugerencia */
  onSuggestionApply?: (suggestion: RouteSuggestion) => void;
  /** Clase CSS adicional */
  className?: string;
}

/**
 * Props del RouteBlock
 */
export interface RouteBlockProps {
  route: ExtendedRouteItem;
  busId?: string;
  isDragging?: boolean;
  isOverlay?: boolean;
  onLockToggle?: (routeId: string) => void;
  onClick?: (route: ExtendedRouteItem) => void;
  className?: string;
}

/**
 * Props del BusTimelineRow
 */
export interface BusTimelineRowProps {
  bus: TimelineBus;
  isActive?: boolean;
  dropDisabled?: boolean;
  onCollapseToggle?: (busId: string) => void;
  onRouteClick?: (route: ExtendedRouteItem) => void;
  className?: string;
}

/**
 * Props del UnassignedRoutesPanel
 */
export interface UnassignedRoutesPanelProps {
  routes: ExtendedRouteItem[];
  suggestions?: RouteSuggestion[];
  isCollapsed?: boolean;
  onCollapseToggle?: () => void;
  onRouteClick?: (route: ExtendedRouteItem) => void;
  onSuggestionClick?: (suggestion: RouteSuggestion) => void;
  className?: string;
}

/**
 * Props del TimelineHeader
 */
export interface TimelineHeaderProps {
  hourRange: [number, number];
  zoom: TimelineZoom;
  pixelsPerHour: number;
  onZoomChange?: (zoom: TimelineZoom) => void;
  onHourRangeChange?: (range: [number, number]) => void;
  className?: string;
}

/**
 * Props del ValidationOverlay
 */
export interface ValidationOverlayProps {
  validation: TimelineValidationState;
  onErrorClick?: (error: ValidationError) => void;
  onDismiss?: () => void;
  className?: string;
}

// ============================================================================
// UTILIDADES DE TIPO
// ============================================================================

/**
 * Tipo para crear una nueva ExtendedRouteItem desde datos base
 */
export type CreateExtendedRouteItemInput = Omit<
  ExtendedRouteItem,
  'status' | 'isEditable' | 'isLocked' | 'currentStartTime' | 'currentEndTime' | 'compatibility'
> & Partial<Pick<ExtendedRouteItem, 'isEditable' | 'isLocked'>>;

/**
 * Tipo para actualizar una ruta (solo campos editables)
 */
export type UpdateRouteInput = Partial<Pick<
  ExtendedRouteItem,
  'isLocked' | 'currentStartTime' | 'assignedBusId' | 'positionInBus'
>>;

/**
 * Filtros para buscar rutas
 */
export interface RouteFilters {
  status?: RouteWorkspaceStatus[];
  busId?: string;
  timeRange?: { start: string; end: string };
  isLocked?: boolean;
  hasConflicts?: boolean;
  searchText?: string;
}

/**
 * Resultado de exportación del timeline
 */
export interface TimelineExport {
  version: string;
  exportedAt: string;
  buses: Array<{
    busId: string;
    busName: string;
    routes: Array<{
      routeId: string;
      startTime: string;
      endTime: string;
      isLocked: boolean;
    }>;
  }>;
  unassignedRoutes: string[];
  metadata: {
    totalRoutes: number;
    assignedRoutes: number;
    lockedRoutes: number;
    conflicts: number;
  };
}
