// Exportaciones principales del módulo timeline-editable

// Componente principal
export { TimelineEditable } from './TimelineEditable';

// Nuevo Workspace profesional
export { Workspace } from './Workspace';
export { RouteLego } from './RouteLego';
export { BusTrack } from './BusTrack';
export { UnassignedPanel } from './UnassignedPanel';
export { WorkspaceToolbar } from './WorkspaceToolbar';
export { RouteDetailsPanel } from './RouteDetailsPanel';

// Componentes de drag & drop
export { HourDropZone } from './drag-drop/HourDropZone';

// Componentes de bus
export { BusTimelineTrack, BusRow } from './bus-row';

// Componentes compartidos
export {
  RouteBlock,
  HourLine,
  BusLabel,
  BusControls,
  generateHours,
  getRoutesInHour,
  getTotalHours,
  formatHour
} from './shared';

// Panel de rutas no asignadas (legacy)
export { UnassignedRoutesPanel } from './unassigned-panel/UnassignedRoutesPanel';

// Sugerencias
export { SmartSuggestionList, SmartSuggestionCard, AutoSortToggle } from './suggestions';
