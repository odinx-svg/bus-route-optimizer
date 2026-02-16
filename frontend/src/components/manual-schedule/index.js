/**
 * Componentes del Editor Manual de Horarios
 * 
 * @module components/manual-schedule
 * @version 1.0.0
 */

// Componentes principales
export { RouteCard, RouteCardSkeleton, RouteCardCompact } from './RouteCard';
export { RoutesPalette, RoutesPaletteCompact } from './RoutesPalette';
export { WorkspaceBusRow, WorkspaceBusRowSkeleton } from './WorkspaceBusRow';
export { RouteConnection } from './RouteConnection';
export { DropZoneIndicator, DropZoneBetweenRoutes } from './DropZoneIndicator';
export { CompatibilityTooltip } from './CompatibilityTooltip';
export { DragPreviewOverlay } from './DragPreviewOverlay';

// Re-exportar hooks relacionados
export {
  useManualSchedule,
  useOSRMValidation,
  useDragAndDrop,
} from '../../hooks/manual-schedule';

// Re-exportar store y selectores
export {
  useManualScheduleStore,
  useBusesWithStats,
  useAvailableRoutesOnly,
  useScheduleStats,
} from '../../stores/manualScheduleStore';

// Re-exportar tipos (para TypeScript)
export * from '../../types/manualSchedule';
