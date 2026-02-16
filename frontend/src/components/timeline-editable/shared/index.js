// Exportaciones del módulo shared
export { generateHours, getRoutesInHour, getTotalHours, formatHour } from './utils';
export { RouteBlock } from './RouteBlock';
export { HourLine } from './HourLine';
export { BusLabel } from './BusLabel';
export { BusControls } from './BusControls';

// Error Boundaries
export { 
  TimelineErrorBoundary, 
  SectionErrorBoundary, 
  useErrorHandler 
} from './ErrorBoundary';

// Loading States
export {
  TimelineLoading,
  SuggestionsLoading,
  ValidatingIndicator,
  RoutesLoading,
  BusesLoading,
  MapLoading,
  OfflineIndicator,
  FallbackIndicator,
  SlowConnectionIndicator,
  TimelineSkeleton,
  ProgressiveLoading
} from './LoadingStates';

// Empty States
export {
  NoRoutesEmptyState,
  NoUnassignedRoutes,
  AllRoutesLocked,
  NoSearchResults,
  NoBusesEmptyState,
  EmptyTimeline,
  NoHistoryEmptyState,
  NoSuggestionsEmptyState,
  LoadErrorState,
  NoFilterResults,
  EmptyMapState
} from './EmptyStates';

// Confirm Dialogs
export {
  ConfirmClearBusDialog,
  ConfirmSaveDialog,
  ConfirmDeleteRouteDialog,
  ConfirmMoveRouteDialog,
  ConfirmLockToggleDialog,
  ConfirmUnsavedChangesDialog,
  GenericConfirmDialog
} from './ConfirmDialogs';
