/**
 * UnifiedWorkspace - Workspace Unificado para Horarios
 * 
 * Combina el Constructor Manual y el Timeline Editable en un unico workspace.
 * Soporta tres modos:
 * - 'create': Crear horario manual desde cero
 * - 'edit': Editar un horario existente
 * - 'optimize': Editar una optimizacion generada (modo borrador)
 * 
 * Layout: Mapa arriba (35%), Constructor abajo (65%)
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  DndContext,
  closestCorners,
  pointerWithin,
  PointerSensor,
  KeyboardSensor,
  TouchSensor,
  useSensor,
  useSensors,
  DragOverlay,
  defaultDropAnimationSideEffects,
  useDroppable,
} from '@dnd-kit/core';
import {
  sortableKeyboardCoordinates,
} from '@dnd-kit/sortable';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap, ZoomControl } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { 
  FileEdit, 
  Save, 
  Upload, 
  AlertCircle, 
  CheckCircle, 
  Clock,
  LayoutList,
  MoreHorizontal,
  Trash2,
  Plus,
  Wifi,
  WifiOff,
  Download,
  Search,
  Ban,
  Edit3,
  Copy,
  GitBranch
} from 'lucide-react';
import { RoutesPalette } from '../manual-schedule/RoutesPalette';
import { RouteCard } from '../manual-schedule/RouteCard';
import { notifications } from '../../services/notifications';
import { useScheduleValidation } from '../../hooks/useScheduleValidation';
import { downloadIncidentsAsCsv, downloadIncidentsAsJson } from '../../utils/incidentsExport';
import { buildRouteCapacityMap, getItemCapacityNeeded } from '../../utils/capacity';
import { RouteEditModal } from './RouteEditModal';
import { TimelineBusRow, TimelineScale, TimelineControls, calculateTimelineCompression } from './TimelineBusRow';
import { TransferZone } from './TransferZone';

// ============================================================================
// CONSTANTES
// ============================================================================

const STORAGE_KEY_DRAFT = 'unified_workspace_draft';
const STORAGE_KEY_STATUS = 'unified_workspace_status';
const STORAGE_KEY_AUTO_REASSIGN = 'unified_workspace_auto_reassign_critical_v1';
const DAY_LABELS = { L: 'Lunes', M: 'Martes', Mc: 'Miercoles', X: 'Jueves', V: 'Viernes' };
const ALL_DAYS = ['L', 'M', 'Mc', 'X', 'V'];
const TIMELINE_BUS_INFO_WIDTH = 118;
const CRITICAL_GLOBAL_ISSUE_TYPES = new Set(['INSUFFICIENT_TIME', 'OVERLAPPING_ROUTES', 'INVALID_TIME_RANGE']);
const CRITICAL_LOCAL_ISSUE_TYPES = new Set(['positioning_infeasible', 'overlap']);

const BUS_COLORS = [
  '#6366F1', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899',
  '#06B6D4', '#F97316', '#84CC16', '#14B8A6', '#EF4444',
];

const BUS_ID_PATTERN = /^B(\d+)/i;

function getBusOrderValue(busId = '', fallback = 999999) {
  const match = String(busId).match(BUS_ID_PATTERN);
  if (!match) return fallback;
  const value = Number.parseInt(match[1], 10);
  return Number.isFinite(value) ? value : fallback;
}

function normalizeBusId(raw = '') {
  const compact = String(raw || '').trim().toUpperCase().replace(/\s+/g, '');
  if (!compact) return '';
  const numericMatch = compact.match(/^B?(\d+)$/i);
  if (numericMatch) {
    return `B${String(Number.parseInt(numericMatch[1], 10)).padStart(3, '0')}`;
  }
  return compact;
}

function sortBusesById(busList = []) {
  return [...busList].sort((a, b) => {
    const aId = normalizeBusId(a?.id);
    const bId = normalizeBusId(b?.id);
    const diff = getBusOrderValue(aId, Number.MAX_SAFE_INTEGER) - getBusOrderValue(bId, Number.MAX_SAFE_INTEGER);
    if (diff !== 0) return diff;
    return String(aId || '').localeCompare(String(bId || ''));
  });
}

function ensureUniqueBusIds(busList = []) {
  const used = new Set();
  let maxNum = 0;

  for (const bus of busList) {
    const num = getBusOrderValue(normalizeBusId(bus?.id), -1);
    if (num >= 0) maxNum = Math.max(maxNum, num);
  }

  return busList.map((bus) => {
    let nextId = normalizeBusId(bus?.id);
    if (!nextId) {
      maxNum += 1;
      nextId = `B${String(maxNum).padStart(3, '0')}`;
    }

    if (used.has(nextId)) {
      do {
        maxNum += 1;
        nextId = `B${String(maxNum).padStart(3, '0')}`;
      } while (used.has(nextId));
    }

    used.add(nextId);
    return { ...bus, id: nextId };
  });
}

function toMinutesSafe(value) {
  if (!value || typeof value !== 'string') return Number.MAX_SAFE_INTEGER;
  const [h = 0, m = 0] = value.split(':').map((v) => Number.parseInt(v, 10));
  if (!Number.isFinite(h) || !Number.isFinite(m)) return Number.MAX_SAFE_INTEGER;
  return (h * 60) + m;
}

function extractPositioningMinutes(item = {}) {
  const raw = (
    item?.positioningMinutes ??
    item?.positioning_minutes ??
    item?.deadheadMinutes ??
    item?.deadhead_minutes ??
    item?.deadhead ??
    0
  );
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? Math.max(0, Math.round(parsed)) : 0;
}

function withPositioningMinutes(route = {}, minutes = 0) {
  const normalized = Number.isFinite(Number(minutes)) ? Math.max(0, Math.round(Number(minutes))) : 0;
  return {
    ...route,
    positioningMinutes: normalized,
    positioning_minutes: normalized,
    deadheadMinutes: normalized,
    deadhead_minutes: normalized,
    deadhead: normalized,
    rawRoute: {
      ...(route?.rawRoute || {}),
      positioning_minutes: normalized,
      deadhead_minutes: normalized,
      deadhead: normalized,
    },
  };
}

function sortRoutesByTime(routes = []) {
  return [...routes].sort((a, b) => {
    const startDiff = toMinutesSafe(a?.startTime || a?.start_time) - toMinutesSafe(b?.startTime || b?.start_time);
    if (startDiff !== 0) return startDiff;

    const endDiff = toMinutesSafe(a?.endTime || a?.end_time) - toMinutesSafe(b?.endTime || b?.end_time);
    if (endDiff !== 0) return endDiff;

    return String(a?.code || a?.id || '').localeCompare(String(b?.code || b?.id || ''));
  });
}

function getRouteId(route = {}) {
  return String(route?.id || route?.route_id || '').trim();
}

function routeMatchesId(route = {}, routeId = '') {
  const normalizedRouteId = String(routeId || '').trim();
  if (!normalizedRouteId) return false;
  return getRouteId(route) === normalizedRouteId;
}

function generateNextBusIdFromList(busList = []) {
  const existingNumbers = (busList || [])
    .map((b) => getBusOrderValue(normalizeBusId(b?.id), NaN))
    .filter((n) => Number.isFinite(n));
  const maxNum = Math.max(0, ...existingNumbers);
  return `B${String(maxNum + 1).padStart(3, '0')}`;
}

function extractContractFromRoute(route = {}) {
  const directContract = (
    route?.contract_id ??
    route?.contractId ??
    route?.rawRoute?.contract_id ??
    route?.rawRoute?.contractId ??
    ''
  );
  if (String(directContract || '').trim()) {
    return String(directContract).trim().toUpperCase();
  }

  const rawCode = String(route?.code || route?.id || '');
  const firstBlock = rawCode.split('_')[0] || rawCode;
  const match = firstBlock.match(/[A-Z]{2}\d{4,5}/i);
  if (match) return String(match[0]).toUpperCase();
  return firstBlock || 'SIN_CONTRATO';
}

function dedupeRoutes(routes = []) {
  const seen = new Set();
  const result = [];

  for (const route of sortRoutesByTime(routes)) {
    const key = [
      route?.id || route?.route_id || '',
      route?.startTime || route?.start_time || '',
      route?.endTime || route?.end_time || '',
      route?.type || '',
    ].join('|');
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(route);
  }

  return result;
}

function normalizeWorkspaceBuses(busList = []) {
  const merged = new Map();
  let unnamedIndex = 0;

  for (const bus of busList || []) {
    const normalizedId = normalizeBusId(bus?.id || bus?.bus_id);
    const key = normalizedId || `__unnamed_${unnamedIndex++}`;
    const currentRoutes = Array.isArray(bus?.routes) ? bus.routes : [];

    if (!merged.has(key)) {
      merged.set(key, {
        id: normalizedId || '',
        routes: [...currentRoutes],
        type: bus?.type || 'standard',
      });
      continue;
    }

    const target = merged.get(key);
    target.routes.push(...currentRoutes);
  }

  const mergedList = Array.from(merged.values()).map((bus) => ({
    ...bus,
    routes: dedupeRoutes(bus.routes),
  }));

  return sortBusesById(ensureUniqueBusIds(mergedList));
}

// ============================================================================
// COMPONENTES DE UI
// ============================================================================

/**
 * StatusBadge - Indicador visual del estado del horario
 */
function StatusBadge({ mode, isDirty, hasErrors, hasUnsavedChanges }) {
  const configs = {
    create: {
      icon: Plus,
      label: 'Modo Manual',
      color: 'bg-gt-info/10 text-gt-info border-gt-info/30'
    },
    edit: {
      icon: FileEdit,
      label: 'Modo Edicion',
      color: 'bg-gt-text-muted/10 text-gt-text border-gt-border'
    },
    optimize: {
      icon: Clock,
      label: 'Modo Borrador',
      color: 'bg-gt-warning/10 text-gt-warning border-gt-warning/30'
    },
  };

  const config = configs[mode] || configs.create;
  const Icon = config.icon;

  return (
    <div className={`gt-glass data-mono flex items-center gap-2 px-3 py-1.5 rounded-lg border ${config.color}`}>
      <Icon className="w-3.5 h-3.5" />
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em]">{config.label}</span>
      {hasUnsavedChanges && (
        <span className="w-1.5 h-1.5 rounded-full bg-gt-warning animate-pulse" title="Cambios sin guardar" />
      )}
      {hasErrors && (
        <AlertCircle className="w-3.5 h-3.5 text-gt-danger" title="Tiene errores" />
      )}
    </div>
  );
}
/**
 * ValidationSummary - Panel de validacion global
 */
function ValidationSummary({ buses, validations }) {
  const stats = useMemo(() => {
    const totalBuses = buses.length;
    const totalRoutes = buses.reduce((sum, bus) => sum + bus.routes.length, 0);
    const totalErrors = Object.values(validations).reduce((sum, v) => sum + (v.errors?.length || 0), 0);
    const totalWarnings = Object.values(validations).reduce((sum, v) => sum + (v.warnings?.length || 0), 0);
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
    <div className={`control-card p-3 rounded-md border ${theme.bg} ${theme.border}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg bg-gray-800/50 ${theme.icon}`}>
            {stats.totalErrors > 0 ? <AlertCircle className="w-4 h-4" /> : 
             stats.totalWarnings > 0 ? <Clock className="w-4 h-4" /> : 
             <CheckCircle className="w-4 h-4" />}
          </div>
          <div>
            <h4 className={`text-xs font-semibold uppercase tracking-[0.1em] ${theme.text}`}>
              {stats.totalErrors > 0 ? 'Errores de validacion' : 
               stats.totalWarnings > 0 ? 'Advertencias' : 'Horario valido'}
            </h4>
            <p className="text-[11px] text-slate-500 data-mono">
              {stats.totalBuses} buses | {stats.totalRoutes} rutas
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3 text-xs">
          {stats.totalErrors > 0 && (
            <div className="flex items-center gap-1 text-red-400">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
              <span>{stats.totalErrors} errores</span>
            </div>
          )}
          {stats.totalWarnings > 0 && (
            <div className="flex items-center gap-1 text-amber-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              <span>{stats.totalWarnings} advertencias</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * WorkspaceArea - Contenedor del area de trabajo (droppable)
 * 
 * Ahora es un droppable que acepta rutas. Cuando se suelta una ruta aqui,
 * se crea un nuevo bus con esa ruta.
 */
function WorkspaceArea({ children, isOverWorkspace }) {
  const { isOver, setNodeRef } = useDroppable({
    id: 'workspace',
    data: { type: 'workspace' },
  });

  const isActive = isOver || isOverWorkspace;

  return (
    <div 
      ref={setNodeRef}
      className={`
        h-full rounded-xl gt-stat-card border border-dashed overflow-auto
        ${isActive ? 'border-gt-accent/60 bg-gt-accent/5' : 'border-gt-border'}
        transition-all duration-200 p-3
      `}
      style={{ minWidth: 'fit-content' }}
    >
      {children}
      
      {/* Indicador visual de drop zone */}
      {isActive && (
        <div className="absolute inset-0 bg-gt-accent/5 border border-gt-accent/40 rounded-xl flex items-center justify-center pointer-events-none z-50">
          <div className="gt-glass px-4 py-2 rounded-lg border border-gt-accent/30">
            <span className="text-[11px] font-semibold tracking-wider text-gt-accent uppercase">Insertar en nuevo bus</span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * EmptyWorkspace - Estado vacio
 */
function EmptyWorkspace({ onAddBus }) {
  return (
    <div className="flex flex-col items-center justify-center h-48 text-center">
      <div className="w-12 h-12 rounded-xl gt-glass flex items-center justify-center mb-3">
        <LayoutList className="w-6 h-6 text-gt-text-muted" />
      </div>
      <h3 className="text-sm font-medium text-gt-text mb-1 uppercase tracking-[0.08em]">Sin buses asignados</h3>
      <p className="text-xs text-gt-text-muted mb-3">Crea una unidad para iniciar el plan operativo</p>
      <button
        onClick={onAddBus}
        className="gt-btn-secondary px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5"
      >
        <Plus className="w-3.5 h-3.5" />
        Anadir bus
      </button>
    </div>
  );
}

// ============================================================================
// COMPONENTE PRINCIPAL
// ============================================================================

export function UnifiedWorkspace({ 
  mode = 'create', 
  routes = [], 
  initialSchedule = null,
  scheduleByDay = null,
  activeDay: externalActiveDay = null,
  validationReport = null,
  onValidationReportChange = null,
  onSave,
  onPublish,
  onExport = null,
  onLiveScheduleChange = null,
  selectedBusIdExternal = null,
  selectedRouteIdExternal = null,
  onBusSelect = null,
  onRouteSelect = null,
  visibleBusIds = null,
  pinnedBusIds = [],
  onTogglePinBus = null,
}) {
  // Helper function to format time from backend (handles "HH:MM:SS" or time objects)
  function formatTimeFromBackend(timeValue) {
    if (!timeValue) return '';
    if (typeof timeValue === 'string') {
      // Handle "HH:MM:SS" or "HH:MM"
      const parts = timeValue.split(':');
      if (parts.length >= 2) {
        return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
      }
    }
    return '';
  }

  // Helper to calculate end time based on duration
  function calculateEndTime(startTime, durationMinutes) {
    if (!startTime || !durationMinutes) return '';
    const [h, m] = startTime.split(':').map(Number);
    const totalMinutes = h * 60 + m + durationMinutes;
    const endH = Math.floor(totalMinutes / 60);
    const endM = totalMinutes % 60;
    return `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
  }

  const routeCapacityById = useMemo(() => buildRouteCapacityMap(routes), [routes]);

  // Transformar rutas al formato interno
  const transformRoutes = useMemo(() => {
    return routes.map(route => {
      // Parse times correctly from backend format
      let startTime = '';
      let endTime = '';
      
      // Backend sends departure_time for exits, arrival_time for entries
      if (route.type === 'exit') {
        // Salidas: departure_time = hora salida colegio, arrival_time seria la ultima parada
        startTime = formatTimeFromBackend(route.departure_time);
        endTime = formatTimeFromBackend(route.arrival_time) || calculateEndTime(startTime, route.duration_minutes || 30);
      } else {
        // Entradas: departure_time = hora primera parada, arrival_time = hora llegada colegio
        if (route.departure_time) {
          startTime = formatTimeFromBackend(route.departure_time);
        } else if (route.stops?.length > 0 && route.stops[0].time_from_start !== undefined) {
          // Calculate based on arrival_time - first_stop_time
          const arrivalTime = formatTimeFromBackend(route.arrival_time);
          if (arrivalTime) {
            const [h, m] = arrivalTime.split(':').map(Number);
            const totalMinutes = h * 60 + m - route.stops[0].time_from_start;
            const startH = Math.floor(totalMinutes / 60);
            const startM = totalMinutes % 60;
            startTime = `${String(startH).padStart(2, '0')}:${String(startM).padStart(2, '0')}`;
          }
        }
        endTime = formatTimeFromBackend(route.arrival_time);
      }
      
      // If still no times, try alternative fields
      if (!startTime) startTime = formatTimeFromBackend(route.start_time);
      if (!endTime) endTime = formatTimeFromBackend(route.end_time);
      
      // Default fallback
      if (!startTime) startTime = '07:00';
      if (!endTime) endTime = '08:00';
      
      const origin = route.origin || 
        (route.stops?.length > 0 ? route.stops[0].name : undefined) || 
        (route.type === 'exit' ? route.school_name : 'Origen');
        
      const destination = route.destination || 
        route.school_name || 
        (route.stops?.length > 0 ? route.stops[route.stops.length - 1].name : 'Destino');
      
      return {
        id: route.route_id || route.id,
        code: route.route_id || route.id || 'Sin codigo',
        startTime,
        endTime,
        origin,
        destination,
        type: route.type || 'entry',
        stops: route.stops || [],
        school: route.school_name || route.school || '',
        start_location: route.start_location || route.start_loc || null,
        end_location: route.end_location || route.end_loc || null,
        positioningMinutes: extractPositioningMinutes(route),
        capacityNeeded: getItemCapacityNeeded(route, routeCapacityById),
        vehicle_capacity_min: route.vehicle_capacity_min ?? route.vehicleCapacityMin ?? null,
        vehicle_capacity_max: route.vehicle_capacity_max ?? route.vehicleCapacityMax ?? null,
        vehicle_capacity_range: route.vehicle_capacity_range ?? route.vehicleCapacityRange ?? null,
        rawRoute: route, // Keep reference to original data
      };
    });
  }, [routeCapacityById, routes]);

  // Estado principal
  const [buses, setBuses] = useState(() => {
    // Si hay schedule inicial (modo optimize/edit), usarlo
    if (initialSchedule) {
      const mappedBuses = initialSchedule.map((bus, idx) => ({
        id: bus.bus_id || bus.id || `B${String(idx + 1).padStart(3, '0')}`,
        routes: (bus.items || bus.routes || []).map(item => ({
          id: item.route_id || item.id,
          code: item.route_code || item.route_id || item.id,
          startTime: item.start_time,
          endTime: item.end_time,
          origin: item.origin || '',
          destination: item.destination || '',
          type: item.type || 'entry',
          stops: item.stops || [],
          school: item.school_name || item.school || '',
          start_location: item.start_location || item.start_loc || null,
          end_location: item.end_location || item.end_loc || null,
          positioningMinutes: extractPositioningMinutes(item),
          capacityNeeded: getItemCapacityNeeded(item, routeCapacityById),
          vehicle_capacity_min: item.vehicle_capacity_min ?? item.vehicleCapacityMin ?? null,
          vehicle_capacity_max: item.vehicle_capacity_max ?? item.vehicleCapacityMax ?? null,
          vehicle_capacity_range: item.vehicle_capacity_range ?? item.vehicleCapacityRange ?? null,
        })),
        type: 'standard',
      }));
      return normalizeWorkspaceBuses(mappedBuses);
    }
    // Intentar cargar borrador
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(STORAGE_KEY_DRAFT);
      if (saved) {
        try {
          return normalizeWorkspaceBuses(JSON.parse(saved));
        } catch { }
      }
    }
    return [{ id: 'B001', routes: [], type: 'standard' }];
  });

  const [availableRoutes, setAvailableRoutes] = useState(transformRoutes);
  const [transferRoutes, setTransferRoutes] = useState([]); // Rutas en zona de transferencia
  const [validationResults, setValidationResults] = useState({});
  const [activeDragItem, setActiveDragItem] = useState(null);
  const [isOverWorkspace, setIsOverWorkspace] = useState(false);
  const [isDraggingRoute, setIsDraggingRoute] = useState(false);
  const [activeDay, setActiveDay] = useState(externalActiveDay || 'L');
  const [isSaving, setIsSaving] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [internalSelectedBusId, setInternalSelectedBusId] = useState(null);
  const [internalSelectedRouteId, setInternalSelectedRouteId] = useState(null);
  const selectedBusId = selectedBusIdExternal ?? internalSelectedBusId;
  const selectedRouteId = selectedRouteIdExternal ?? internalSelectedRouteId;
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [viewMode, setViewMode] = useState('timeline'); // 'list' | 'timeline'
  const [timelineZoom, setTimelineZoom] = useState(140); // pixeles por hora (default optimo)
  const [timelineRange, setTimelineRange] = useState({ min: 6, max: 22 }); // rango horario por defecto
  const timelineViewportRef = useRef(null);
  const [timelineViewportWidth, setTimelineViewportWidth] = useState(0);
  const timelinePanRef = useRef({
    active: false,
    startX: 0,
    startScrollLeft: 0,
  });
  const [isTimelinePanning, setIsTimelinePanning] = useState(false);
  const isBusFilterActive = Array.isArray(visibleBusIds);
  const visibleBusIdSet = useMemo(
    () => new Set((Array.isArray(visibleBusIds) ? visibleBusIds : []).map((id) => String(id || '').trim())),
    [visibleBusIds],
  );
  const pinnedBusIdSet = useMemo(
    () => new Set((Array.isArray(pinnedBusIds) ? pinnedBusIds : []).map((id) => String(id || '').trim())),
    [pinnedBusIds],
  );
  const displayedBuses = useMemo(() => {
    if (!isBusFilterActive) return buses;
    return buses.filter((bus) => visibleBusIdSet.has(String(bus?.id || bus?.bus_id || '')));
  }, [buses, isBusFilterActive, visibleBusIdSet]);
  
  // Calcular compresion del timeline (eliminar huecos vacios)
  const { segments: compressedSegments, compressedWidth } = useMemo(() => {
    // Obtener todas las rutas de todos los buses
    const allRoutes = displayedBuses.flatMap(bus => bus.routes);
    return calculateTimelineCompression(allRoutes, timelineRange.min, timelineRange.max);
  }, [displayedBuses, timelineRange.min, timelineRange.max]);

  // Zoom efectivo: si el zoom base deja huecos a la derecha, se estira para ocupar todo el workspace.
  const effectiveTimelineZoom = useMemo(() => {
    const segmentEndMinutes = compressedSegments?.length > 0
      ? compressedSegments[compressedSegments.length - 1].end
      : (timelineRange.max - timelineRange.min) * 60;
    if (!segmentEndMinutes || timelineViewportWidth <= 0) return timelineZoom;

    const baseTrackWidth = (segmentEndMinutes / 60) * timelineZoom;
    const minTrackWidthToFillViewport = Math.max(0, timelineViewportWidth - TIMELINE_BUS_INFO_WIDTH - 2);
    if (baseTrackWidth >= minTrackWidthToFillViewport) return timelineZoom;

    const fitZoom = (minTrackWidthToFillViewport * 60) / segmentEndMinutes;
    return Math.max(timelineZoom, fitZoom);
  }, [compressedSegments, timelineRange.min, timelineRange.max, timelineViewportWidth, timelineZoom]);
  
  const [pendingValidations, setPendingValidations] = useState(new Set());
  const [isInitialized, setIsInitialized] = useState(false);
  const [globalValidationRunning, setGlobalValidationRunning] = useState(false);
  const [reassignRunning, setReassignRunning] = useState(false);
  const [autoReassignCritical, setAutoReassignCritical] = useState(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem(STORAGE_KEY_AUTO_REASSIGN) === '1';
  });
  const [lastReassignSummary, setLastReassignSummary] = useState(null);
  const [positioningRefreshRunning, setPositioningRefreshRunning] = useState(false);
  const [positioningRefreshStats, setPositioningRefreshStats] = useState({ done: 0, total: 0 });
  const [globalValidationReport, setGlobalValidationReport] = useState(validationReport || null);
  const [globalFilter, setGlobalFilter] = useState({
    severity: 'all',
    day: 'all',
    bus: 'all',
    query: '',
  });
  const [listSort, setListSort] = useState({
    key: 'bus_time',
    direction: 'asc',
  });

  // Estado para modal de edicion de rutas
  const [routeEditModal, setRouteEditModal] = useState({
    isOpen: false,
    mode: 'edit', // 'edit', 'create', 'duplicate'
    route: null,
  });
  const busesRef = useRef(buses);
  const refreshRunIdRef = useRef(0);
  const refreshTimerRef = useRef(null);
  const refreshPendingAllRef = useRef(false);
  const refreshPendingBusIdsRef = useRef(new Set());

  const updateSelectedBus = useCallback((nextBusId) => {
    const value = nextBusId || null;
    setInternalSelectedBusId(value);
    if (typeof onBusSelect === 'function') {
      onBusSelect(value);
    }
  }, [onBusSelect]);

  const updateSelectedRoute = useCallback((nextRouteId) => {
    const value = nextRouteId || null;
    setInternalSelectedRouteId(value);
    if (typeof onRouteSelect === 'function') {
      onRouteSelect(value);
    }
  }, [onRouteSelect]);

  useEffect(() => {
    busesRef.current = buses;
  }, [buses]);

  useEffect(() => () => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_KEY_AUTO_REASSIGN, autoReassignCritical ? '1' : '0');
  }, [autoReassignCritical]);

  // Efecto para sincronizar con initialSchedule cuando cambia (post-optimizacion)
  useEffect(() => {
    if (initialSchedule && !isInitialized) {
      const mappedBuses = initialSchedule.map((bus, idx) => ({
        id: bus.bus_id || bus.id || `B${String(idx + 1).padStart(3, '0')}`,
        routes: (bus.items || bus.routes || []).map(item => ({
          id: item.route_id || item.id,
          code: item.route_code || item.route_id || item.id,
          startTime: item.start_time,
          endTime: item.end_time,
          origin: item.origin || '',
          destination: item.destination || '',
          type: item.type || 'entry',
          stops: item.stops || [],
          school: item.school_name || item.school || '',
          start_location: item.start_location || item.start_loc || null,
          end_location: item.end_location || item.end_loc || null,
          positioningMinutes: extractPositioningMinutes(item),
          capacityNeeded: getItemCapacityNeeded(item, routeCapacityById),
          vehicle_capacity_min: item.vehicle_capacity_min ?? item.vehicleCapacityMin ?? null,
          vehicle_capacity_max: item.vehicle_capacity_max ?? item.vehicleCapacityMax ?? null,
          vehicle_capacity_range: item.vehicle_capacity_range ?? item.vehicleCapacityRange ?? null,
        })),
        type: 'standard',
      }));
      setBuses(normalizeWorkspaceBuses(mappedBuses));
      setIsInitialized(true);
    }
  }, [initialSchedule, isInitialized, routeCapacityById]);

  // Reset initialization when mode changes
  useEffect(() => {
    setIsInitialized(false);
  }, [mode]);

  // Re-sync buses when changing day while working with persisted schedules.
  useEffect(() => {
    if (mode === 'optimize' || mode === 'edit') {
      setIsInitialized(false);
    }
  }, [mode, externalActiveDay, initialSchedule]);

  useEffect(() => {
    if (externalActiveDay) {
      setActiveDay(externalActiveDay);
    }
  }, [externalActiveDay]);

  useEffect(() => {
    setGlobalValidationReport(validationReport || null);
  }, [validationReport]);

  // Medir ancho visible del workspace timeline para "fit to width" dinámico.
  useEffect(() => {
    const el = timelineViewportRef.current;
    if (!el) return;

    const updateWidth = () => {
      const w = Math.round(el.clientWidth || 0);
      setTimelineViewportWidth((prev) => (prev === w ? prev : w));
    };

    updateWidth();

    const observer = new ResizeObserver(() => updateWidth());
    observer.observe(el);
    return () => observer.disconnect();
  }, [viewMode]);

  useEffect(() => {
    if (!isTimelinePanning) return;

    const handleMouseMove = (event) => {
      const viewport = timelineViewportRef.current;
      const pan = timelinePanRef.current;
      if (!viewport || !pan.active) return;

      const deltaX = event.clientX - pan.startX;
      viewport.scrollLeft = pan.startScrollLeft - deltaX;
    };

    const handleMouseUp = () => {
      timelinePanRef.current.active = false;
      setIsTimelinePanning(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isTimelinePanning]);

  // WebSocket de validacion OSRM
  const { 
    isConnected: wsConnected, 
    connectionState,
    validating: osrmValidating,
    validateConnection,
    canAssignRoute,
    validateBus,
    validateAllBuses
  } = useScheduleValidation();

  const osrmBadgeState = connectionState === 'connected'
    ? 'connected'
    : (connectionState === 'connecting' || connectionState === 'reconnecting' ? 'reconnecting' : 'disconnected');

  const recomputePositioningForBus = useCallback(async (bus) => {
    if (!bus || !Array.isArray(bus.routes) || bus.routes.length === 0) {
      return { bus, changed: false };
    }

    const orderedRoutes = sortRoutesByTime(bus.routes);
    const nextRoutes = orderedRoutes.map((route, idx) => (
      idx === 0 ? withPositioningMinutes(route, 0) : withPositioningMinutes(route, extractPositioningMinutes(route))
    ));

    let changed = false;

    for (let i = 1; i < nextRoutes.length; i += 1) {
      const prevRoute = nextRoutes[i - 1];
      const currRoute = nextRoutes[i];
      try {
        const validation = await validateConnection(prevRoute, currRoute);
        const travelMinutes = Number(validation?.travel_time);
        if (Number.isFinite(travelMinutes) && travelMinutes >= 0) {
          const normalized = Math.max(0, Math.round(travelMinutes));
          if (extractPositioningMinutes(currRoute) !== normalized) {
            nextRoutes[i] = withPositioningMinutes(currRoute, normalized);
            changed = true;
          }
        }
      } catch (error) {
        console.warn('[Workspace] OSRM positioning recompute failed', {
          bus_id: bus.id,
          route_a: prevRoute?.id || prevRoute?.route_id,
          route_b: currRoute?.id || currRoute?.route_id,
          error: error?.message || String(error),
        });
      }
    }

    const orderChanged = orderedRoutes.some((route, idx) => {
      const original = bus.routes[idx];
      return String(route?.id || route?.route_id || '') !== String(original?.id || original?.route_id || '');
    });

    return {
      bus: (changed || orderChanged) ? { ...bus, routes: nextRoutes } : bus,
      changed: changed || orderChanged,
    };
  }, [validateConnection]);

  const refreshPositioningMinutes = useCallback(async (targetBusIds = null) => {
    const runId = Date.now();
    refreshRunIdRef.current = runId;

    const idSet = Array.isArray(targetBusIds) && targetBusIds.length > 0
      ? new Set(targetBusIds.map((id) => String(id || '').trim()).filter(Boolean))
      : null;

    const sourceBuses = busesRef.current || [];
    const busesToRefresh = idSet
      ? sourceBuses.filter((bus) => idSet.has(String(bus?.id || '').trim()))
      : sourceBuses;

    if (!busesToRefresh.length) {
      return { refreshed: 0, updated: 0 };
    }

    setPositioningRefreshRunning(true);
    setPositioningRefreshStats({ done: 0, total: busesToRefresh.length });

    const updatesByBusId = new Map();
    let processed = 0;

    try {
      for (const bus of busesToRefresh) {
        const { bus: updatedBus, changed } = await recomputePositioningForBus(bus);
        if (refreshRunIdRef.current !== runId) {
          return { refreshed: processed, updated: updatesByBusId.size, cancelled: true };
        }
        if (changed && updatedBus?.id) {
          updatesByBusId.set(String(updatedBus.id), updatedBus);
        }
        processed += 1;
        setPositioningRefreshStats({ done: processed, total: busesToRefresh.length });
      }

      if (updatesByBusId.size > 0) {
        setBuses((prev) => prev.map((bus) => updatesByBusId.get(String(bus?.id || '')) || bus));
      }

      return { refreshed: processed, updated: updatesByBusId.size };
    } finally {
      if (refreshRunIdRef.current === runId) {
        setPositioningRefreshRunning(false);
        setPositioningRefreshStats({ done: 0, total: 0 });
      }
    }
  }, [recomputePositioningForBus]);

  const requestPositioningRefresh = useCallback((targetBusIds = null, delayMs = 120) => {
    if (Array.isArray(targetBusIds) && targetBusIds.length > 0) {
      targetBusIds.forEach((id) => {
        const normalized = String(id || '').trim();
        if (normalized) refreshPendingBusIdsRef.current.add(normalized);
      });
    } else {
      refreshPendingAllRef.current = true;
      refreshPendingBusIdsRef.current.clear();
    }

    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }

    refreshTimerRef.current = setTimeout(() => {
      const refreshAll = refreshPendingAllRef.current;
      const ids = refreshAll ? null : Array.from(refreshPendingBusIdsRef.current);
      refreshPendingAllRef.current = false;
      refreshPendingBusIdsRef.current.clear();
      refreshTimerRef.current = null;
      refreshPositioningMinutes(ids).catch((error) => {
        console.error('[Workspace] Failed to refresh positioning minutes', error);
      });
    }, delayMs);
  }, [refreshPositioningMinutes]);

  const handleValidateBus = useCallback(async (bus) => {
    const result = await validateBus(bus);
    requestPositioningRefresh([bus?.id], 0);
    return result;
  }, [requestPositioningRefresh, validateBus]);

  // Calcular rutas asignadas
  const assignedRouteIds = useMemo(() => {
    const ids = new Set();
    buses.forEach(bus => bus.routes.forEach(route => ids.add(route.id)));
    return ids;
  }, [buses]);

  const filteredAvailableRoutes = useMemo(() => {
    return availableRoutes.filter(route => !assignedRouteIds.has(route.id));
  }, [availableRoutes, assignedRouteIds]);

  const selectedRoute = useMemo(() => {
    if (!selectedRouteId) return null;
    const allRoutes = [
      ...buses.flatMap((bus) => bus.routes || []),
      ...(transferRoutes || []),
      ...(availableRoutes || []),
    ];
    return allRoutes.find((route) => String(route?.id) === String(selectedRouteId)) || null;
  }, [selectedRouteId, buses, transferRoutes, availableRoutes]);

  const listRowsBase = useMemo(() => {
    const rows = [];
    const orderedBuses = sortBusesById(displayedBuses);

    orderedBuses.forEach((bus) => {
      const orderedRoutes = sortRoutesByTime(bus.routes || []);
      orderedRoutes.forEach((route, index) => {
        const previousRoute = orderedRoutes[index - 1] || null;
        const durationMinutes = Math.max(0, toMinutesSafe(route.endTime) - toMinutesSafe(route.startTime));
        const windowMinutes = previousRoute
          ? Math.max(0, toMinutesSafe(route.startTime) - toMinutesSafe(previousRoute.endTime))
          : null;
        const realPositioningMinutes = previousRoute ? extractPositioningMinutes(route) : null;
        const marginMinutes = (windowMinutes != null && realPositioningMinutes != null)
          ? windowMinutes - realPositioningMinutes
          : null;
        const typeLabel = route.type === 'entry' ? 'ENTRADA' : 'SALIDA';
        const seats = Number(route.capacityNeeded || 0);

        rows.push({
          key: `${bus.id}-${route.id}-${index}`,
          busId: bus.id,
          order: index + 1,
          route,
          routeCode: route.code || route.id || '-',
          type: typeLabel,
          startTime: route.startTime || '--:--',
          endTime: route.endTime || '--:--',
          durationMinutes,
          windowMinutes,
          realPositioningMinutes,
          marginMinutes,
          origin: route.origin || '-',
          destination: route.destination || '-',
          school: route.school || '-',
          contract: extractContractFromRoute(route),
          seats: seats > 0 ? seats : null,
        });
      });
    });

    return rows;
  }, [displayedBuses]);

  const listRows = useMemo(() => {
    const sorted = [...listRowsBase];
    const directionFactor = listSort.direction === 'asc' ? 1 : -1;

    const compareText = (a, b) => String(a || '').localeCompare(String(b || ''), 'es', { sensitivity: 'base' });
    const compareNumber = (a, b) => {
      const numA = Number.isFinite(Number(a)) ? Number(a) : Number.MAX_SAFE_INTEGER;
      const numB = Number.isFinite(Number(b)) ? Number(b) : Number.MAX_SAFE_INTEGER;
      return numA - numB;
    };
    const compareBus = (a, b) => {
      const diff = getBusOrderValue(normalizeBusId(a.busId), Number.MAX_SAFE_INTEGER) - getBusOrderValue(normalizeBusId(b.busId), Number.MAX_SAFE_INTEGER);
      if (diff !== 0) return diff;
      return compareText(a.busId, b.busId);
    };

    sorted.sort((a, b) => {
      let diff = 0;
      switch (listSort.key) {
        case 'route':
          diff = compareText(a.contract, b.contract);
          if (diff !== 0) break;
          diff = compareText(a.routeCode, b.routeCode);
          break;
        case 'contract':
          diff = compareText(a.contract, b.contract);
          if (diff !== 0) break;
          diff = compareText(a.routeCode, b.routeCode);
          break;
        case 'bus':
          diff = compareBus(a, b);
          if (diff !== 0) break;
          diff = compareNumber(toMinutesSafe(a.startTime), toMinutesSafe(b.startTime));
          break;
        case 'order':
          diff = compareBus(a, b);
          if (diff !== 0) break;
          diff = compareNumber(a.order, b.order);
          break;
        case 'type':
          diff = compareText(a.type, b.type);
          break;
        case 'start':
          diff = compareNumber(toMinutesSafe(a.startTime), toMinutesSafe(b.startTime));
          break;
        case 'end':
          diff = compareNumber(toMinutesSafe(a.endTime), toMinutesSafe(b.endTime));
          break;
        case 'duration':
          diff = compareNumber(a.durationMinutes, b.durationMinutes);
          break;
        case 'positioning':
          diff = compareNumber(a.realPositioningMinutes, b.realPositioningMinutes);
          break;
        case 'window':
          diff = compareNumber(a.windowMinutes, b.windowMinutes);
          break;
        case 'margin':
          diff = compareNumber(a.marginMinutes, b.marginMinutes);
          break;
        case 'seats':
          diff = compareNumber(a.seats, b.seats);
          break;
        case 'origin':
          diff = compareText(a.origin, b.origin);
          break;
        case 'destination':
          diff = compareText(a.destination, b.destination);
          break;
        case 'school':
          diff = compareText(a.school, b.school);
          if (diff !== 0) break;
          diff = compareNumber(toMinutesSafe(a.startTime), toMinutesSafe(b.startTime));
          break;
        case 'bus_time':
        default:
          diff = compareBus(a, b);
          if (diff !== 0) break;
          diff = compareNumber(toMinutesSafe(a.startTime), toMinutesSafe(b.startTime));
          if (diff !== 0) break;
          diff = compareText(a.routeCode, b.routeCode);
      }

      if (diff === 0) {
        const tie = compareBus(a, b) || compareNumber(toMinutesSafe(a.startTime), toMinutesSafe(b.startTime)) || compareText(a.routeCode, b.routeCode);
        return tie * directionFactor;
      }
      return diff * directionFactor;
    });

    return sorted;
  }, [listRowsBase, listSort]);

  const groupedListRows = useMemo(() => {
    const shouldGroupBySchool = listSort.key === 'school';
    const shouldGroupByContract = listSort.key === 'contract' || listSort.key === 'route';
    if (!shouldGroupBySchool && !shouldGroupByContract) {
      return listRows.map((row) => ({ type: 'row', row }));
    }

    let currentGroup = null;
    const grouped = [];

    listRows.forEach((row) => {
      const label = shouldGroupBySchool ? row.school : row.contract;
      const normalizedLabel = String(label || 'Sin datos');
      if (normalizedLabel !== currentGroup) {
        currentGroup = normalizedLabel;
        grouped.push({
          type: 'group',
          key: `${shouldGroupBySchool ? 'school' : 'contract'}-${normalizedLabel}`,
          label: normalizedLabel,
        });
      }
      grouped.push({ type: 'row', row });
    });

    return grouped;
  }, [listRows, listSort.key]);

  // Actualizar availableRoutes cuando cambian las rutas de entrada
  useEffect(() => {
    if (transformRoutes.length > 0) {
      setAvailableRoutes(prev => {
        // Mantener las ya asignadas, agregar nuevas
        const existingIds = new Set(prev.map(r => r.id));
        const newRoutes = transformRoutes.filter(r => !existingIds.has(r.id));
        return [...prev, ...newRoutes];
      });
    }
  }, [transformRoutes]);

  // Auto-guardar borrador
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY_DRAFT, JSON.stringify(buses));
      localStorage.setItem(STORAGE_KEY_STATUS, JSON.stringify({ 
        mode, 
        activeDay, 
        lastSaved: new Date().toISOString() 
      }));
      setHasUnsavedChanges(true);
    }
  }, [buses, mode, activeDay]);

  // Validar horario en tiempo real
  useEffect(() => {
    const validations = {};
    buses.forEach(bus => {
      const busValidations = { errors: [], warnings: [], routes: {} };
      bus.routes.forEach((route, index) => {
        const routeKey = String(route?.id || route?.route_id || '');
        if (routeKey && !busValidations.routes[routeKey]) {
          busValidations.routes[routeKey] = { errors: [], warnings: [] };
        }

        if (index === 0) return;
        const prevRoute = bus.routes[index - 1];
        const [endHour, endMin] = prevRoute.endTime.split(':').map(Number);
        const [startHour, startMin] = route.startTime.split(':').map(Number);
        const endTime = endHour * 60 + endMin;
        const startTime = startHour * 60 + startMin;
        const buffer = startTime - endTime;
        const positioningMinutes = extractPositioningMinutes(route);
        const realMargin = buffer - positioningMinutes;
        
        if (buffer < 0) {
          const issue = {
            type: 'overlap',
            message: `Solapamiento entre ${prevRoute.code} y ${route.code}`,
            routeIndex: index,
            routeId: routeKey,
            prevRouteId: String(prevRoute?.id || prevRoute?.route_id || ''),
          };
          busValidations.errors.push(issue);
          if (routeKey) busValidations.routes[routeKey].errors.push(issue);
        } else if (positioningMinutes > 0 && realMargin < 0) {
          const issue = {
            type: 'positioning_infeasible',
            message: `No llega a tiempo: R ${positioningMinutes}m > V ${buffer}m (${realMargin}m)`,
            routeIndex: index,
            routeId: routeKey,
            prevRouteId: String(prevRoute?.id || prevRoute?.route_id || ''),
            windowMinutes: buffer,
            positioningMinutes,
            marginMinutes: realMargin,
          };
          busValidations.errors.push(issue);
          if (routeKey) busValidations.routes[routeKey].errors.push(issue);
        } else if (positioningMinutes > 0 && realMargin <= 5) {
          const issue = {
            type: 'positioning_tight',
            message: `Margen de posicionamiento ajustado: ${realMargin}m`,
            routeIndex: index,
            routeId: routeKey,
            prevRouteId: String(prevRoute?.id || prevRoute?.route_id || ''),
            windowMinutes: buffer,
            positioningMinutes,
            marginMinutes: realMargin,
          };
          busValidations.warnings.push(issue);
          if (routeKey) busValidations.routes[routeKey].warnings.push(issue);
        } else if (buffer < 10) {
          const issue = {
            type: 'short_buffer',
            message: `Buffer corto (${buffer}min)`,
            routeIndex: index,
            routeId: routeKey,
            prevRouteId: String(prevRoute?.id || prevRoute?.route_id || ''),
          };
          busValidations.warnings.push(issue);
          if (routeKey) busValidations.routes[routeKey].warnings.push(issue);
        }
      });
      validations[bus.id] = busValidations;
    });
    setValidationResults(validations);
  }, [buses]);

  // Sensores DnD - Configuracion optimizada para mejor UX
  const sensors = useSensors(
    // Pointer: Menor distancia para activar drag mas rapido
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    // Touch: Menor delay para respuesta mas rapida en movil
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    // Keyboard: Navegacion con teclado
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  // Handlers
  const generateBusId = useCallback(() => {
    const existingNumbers = buses
      .map((b) => getBusOrderValue(normalizeBusId(b.id), NaN))
      .filter(n => !isNaN(n));
    const maxNum = Math.max(0, ...existingNumbers);
    return `B${String(maxNum + 1).padStart(3, '0')}`;
  }, [buses]);

  const handleAddBus = useCallback(() => {
    const newId = generateBusId();
    setBuses(prev => [...prev, { id: newId, routes: [], type: 'standard' }]);
    notifications.success('Bus anadido', `Bus ${newId} creado`);
  }, [generateBusId]);

  const handleRemoveBus = useCallback((busId) => {
    if (!confirm(`Eliminar el bus ${busId}?`)) return;
    setBuses(prev => prev.filter(b => b.id !== busId));
    if (selectedBusId === busId) updateSelectedBus(null);
  }, [selectedBusId, updateSelectedBus]);

  const handleDragStart = useCallback((event) => {
    const data = event.active.data.current;
    setActiveDragItem(data);
    if (data?.type === 'route') {
      setIsDraggingRoute(true);
    }
  }, []);

  const handleDragOver = useCallback((event) => {
    setIsOverWorkspace(!!event.over);
  }, []);

  const handleListSort = useCallback((key) => {
    setListSort((prev) => {
      if (prev.key === key) {
        return {
          key,
          direction: prev.direction === 'asc' ? 'desc' : 'asc',
        };
      }
      return {
        key,
        direction: 'asc',
      };
    });
  }, []);

  const handleTimelineMouseDown = useCallback((event) => {
    if (viewMode !== 'timeline') return;
    if (event.button !== 0) return;

    const target = event.target;
    if (
      target?.closest?.('[data-no-timeline-pan]') ||
      target?.closest?.('button') ||
      target?.closest?.('input') ||
      target?.closest?.('select') ||
      target?.closest?.('textarea') ||
      target?.closest?.('a')
    ) {
      return;
    }

    const viewport = timelineViewportRef.current;
    if (!viewport) return;
    if (viewport.scrollWidth <= viewport.clientWidth + 1) return;

    timelinePanRef.current = {
      active: true,
      startX: event.clientX,
      startScrollLeft: viewport.scrollLeft,
    };
    setIsTimelinePanning(true);
    event.preventDefault();
  }, [viewMode]);

  // Helper: convertir hora "HH:MM" a minutos
  const timeToMinutes = (timeStr) => {
    if (!timeStr) return 0;
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
  };

  // Helper: verificar solapamiento entre dos rangos de tiempo
  const checkOverlap = (startA, endA, startB, endB) => {
    const sA = timeToMinutes(startA);
    const eA = timeToMinutes(endA);
    const sB = timeToMinutes(startB);
    const eB = timeToMinutes(endB);
    
    // Hay solapamiento si los rangos se intersectan
    // Consideramos solapamiento si comparten al menos 1 minuto
    return sA < eB && eA > sB;
  };

  const getCriticalReassignTargets = useCallback((reportOverride = null, includeLocal = true) => {
    const targets = new Map();

    const pushTarget = ({
      busId = '',
      routeId = '',
      fallbackRouteId = '',
      prevRouteId = '',
      source = 'local',
      issueType = '',
      reason = '',
    }) => {
      const normalizedBus = String(busId || '').trim();
      const normalizedRoute = String(routeId || '').trim();
      if (!normalizedBus || !normalizedRoute) return;
      const key = `${normalizedBus}|${normalizedRoute}`;
      if (targets.has(key)) return;
      targets.set(key, {
        busId: normalizedBus,
        routeId: normalizedRoute,
        fallbackRouteId: String(fallbackRouteId || '').trim() || null,
        prevRouteId: String(prevRouteId || '').trim() || null,
        source,
        issueType: String(issueType || '').trim(),
        reason: String(reason || '').trim(),
      });
    };

    const report = reportOverride || globalValidationReport;
    const incidents = Array.isArray(report?.incidents) ? report.incidents : [];
    incidents.forEach((incident) => {
      const severity = String(incident?.severity || '').toLowerCase();
      if (severity !== 'error') return;
      if (incident?.day && String(incident.day).trim() !== String(activeDay).trim()) return;

      const issueType = String(incident?.issue_type || '').toUpperCase();
      if (!CRITICAL_GLOBAL_ISSUE_TYPES.has(issueType)) return;

      pushTarget({
        busId: incident?.bus_id,
        routeId: incident?.route_b,
        fallbackRouteId: incident?.route_a,
        prevRouteId: incident?.route_a,
        source: 'global',
        issueType,
        reason: incident?.message,
      });
    });

    if (includeLocal) {
      Object.entries(validationResults || {}).forEach(([busId, busValidation]) => {
        const errors = Array.isArray(busValidation?.errors) ? busValidation.errors : [];
        errors.forEach((error) => {
          const issueType = String(error?.type || '').toLowerCase();
          if (!CRITICAL_LOCAL_ISSUE_TYPES.has(issueType)) return;
          pushTarget({
            busId,
            routeId: error?.routeId,
            fallbackRouteId: error?.prevRouteId,
            prevRouteId: error?.prevRouteId,
            source: 'local',
            issueType,
            reason: error?.message,
          });
        });
      });
    }

    return Array.from(targets.values());
  }, [activeDay, globalValidationReport, validationResults]);

  const routeOverlapsBus = useCallback((route, busRoutes = []) => (
    (busRoutes || []).some((existingRoute) => (
      checkOverlap(
        route?.startTime || route?.start_time,
        route?.endTime || route?.end_time,
        existingRoute?.startTime || existingRoute?.start_time,
        existingRoute?.endTime || existingRoute?.end_time,
      )
    ))
  ), []);

  const evaluatePlacementScore = useCallback((route, targetRoutes = []) => {
    const simulated = sortRoutesByTime([...(targetRoutes || []), route]);
    const idx = simulated.findIndex((item) => routeMatchesId(item, getRouteId(route)));
    if (idx < 0) return -9999;

    const prev = idx > 0 ? simulated[idx - 1] : null;
    const next = idx < simulated.length - 1 ? simulated[idx + 1] : null;

    const beforeWindow = prev
      ? Math.max(0, toMinutesSafe(route?.startTime || route?.start_time) - toMinutesSafe(prev?.endTime || prev?.end_time))
      : 999;
    const afterWindow = next
      ? Math.max(0, toMinutesSafe(next?.startTime || next?.start_time) - toMinutesSafe(route?.endTime || route?.end_time))
      : 999;

    const slack = Math.min(beforeWindow, afterWindow);
    const loadPenalty = (targetRoutes?.length || 0) * 0.35;
    return slack - loadPenalty;
  }, []);

  const runCriticalReassignment = useCallback(async ({
    trigger = 'manual',
    silent = false,
    reportOverride = null,
    includeLocal = true,
  } = {}) => {
    if (reassignRunning) {
      return null;
    }

    if (!wsConnected) {
      if (!silent) {
        notifications.warning('OSRM no conectado', 'La reasignacion requiere validacion OSRM activa');
      }
      return { moved: 0, created: 0, unresolved: 0, skipped: 0, unresolvedItems: [] };
    }

    const targets = getCriticalReassignTargets(reportOverride, includeLocal);
    if (!targets.length) {
      if (!silent) {
        notifications.info('Sin incidencias criticas', 'No hay errores que requieran reasignacion');
      }
      return { moved: 0, created: 0, unresolved: 0, skipped: 0, unresolvedItems: [] };
    }

    setReassignRunning(true);

    try {
      const workingBuses = (busesRef.current || []).map((bus) => ({
        ...bus,
        routes: [...(bus?.routes || [])],
      }));

      const movedRouteIds = new Set();
      const affectedBusIds = new Set();
      const movedItems = [];
      const unresolvedItems = [];
      let createdBuses = 0;

      for (const target of targets) {
        const sourceBus = workingBuses.find((bus) => String(bus?.id || '').trim() === target.busId);
        if (!sourceBus || !Array.isArray(sourceBus.routes) || sourceBus.routes.length === 0) {
          unresolvedItems.push({ ...target, reason: 'Bus origen no encontrado' });
          continue;
        }

        const routeIdx = sourceBus.routes.findIndex((route) => (
          routeMatchesId(route, target.routeId) || routeMatchesId(route, target.fallbackRouteId)
        ));

        if (routeIdx < 0) {
          unresolvedItems.push({ ...target, reason: 'Ruta conflictiva no encontrada en bus origen' });
          continue;
        }

        const route = sourceBus.routes[routeIdx];
        const routeId = getRouteId(route);
        if (!routeId || movedRouteIds.has(routeId)) {
          continue;
        }

        let bestPlacement = null;

        for (const candidateBus of workingBuses) {
          if (String(candidateBus?.id || '').trim() === String(sourceBus?.id || '').trim()) continue;
          if ((candidateBus?.routes || []).some((candidateRoute) => routeMatchesId(candidateRoute, routeId))) continue;
          if (routeOverlapsBus(route, candidateBus?.routes || [])) continue;

          let feasibility = null;
          try {
            feasibility = await canAssignRoute(route, candidateBus?.routes || []);
          } catch (error) {
            console.warn('[Workspace] Reassign feasibility check failed', {
              route_id: routeId,
              source_bus: sourceBus?.id,
              candidate_bus: candidateBus?.id,
              error: error?.message || String(error),
            });
            continue;
          }

          if (!feasibility?.feasible) continue;

          const score = evaluatePlacementScore(route, candidateBus?.routes || []);
          if (!bestPlacement || score > bestPlacement.score) {
            bestPlacement = {
              busId: candidateBus.id,
              score,
              created: false,
            };
          }
        }

        if (!bestPlacement) {
          const newBusId = generateNextBusIdFromList(workingBuses);
          bestPlacement = {
            busId: newBusId,
            score: -1000,
            created: true,
          };
        }

        const [movedRoute] = sourceBus.routes.splice(routeIdx, 1);
        let destinationBus = workingBuses.find((bus) => String(bus?.id || '').trim() === String(bestPlacement.busId));
        if (!destinationBus) {
          destinationBus = {
            id: bestPlacement.busId,
            routes: [],
            type: 'standard',
          };
          workingBuses.push(destinationBus);
        }

        destinationBus.routes = sortRoutesByTime([...(destinationBus.routes || []), movedRoute]);
        sourceBus.routes = sortRoutesByTime(sourceBus.routes || []);

        movedRouteIds.add(routeId);
        affectedBusIds.add(String(sourceBus.id));
        affectedBusIds.add(String(destinationBus.id));
        if (bestPlacement.created) createdBuses += 1;

        movedItems.push({
          routeId,
          routeCode: movedRoute?.code || routeId,
          fromBus: String(sourceBus.id),
          toBus: String(destinationBus.id),
          issueType: target.issueType || 'critical_incident',
        });
      }

      const normalizedBuses = sortBusesById(ensureUniqueBusIds(
        workingBuses.map((bus) => ({
          ...bus,
          routes: sortRoutesByTime(bus?.routes || []),
        })),
      ));

      if (movedItems.length > 0) {
        setBuses(normalizedBuses);
        setHasUnsavedChanges(true);
        requestPositioningRefresh(Array.from(affectedBusIds), 0);
      }

      let postIncidentsTotal = null;
      if (movedItems.length > 0) {
        try {
          const revalidationPayload = buildValidationDaysPayload(normalizedBuses);
          const postReport = await validateAllBuses(revalidationPayload, false);
          setGlobalValidationReport(postReport);
          if (typeof onValidationReportChange === 'function') {
            onValidationReportChange(postReport);
          }
          postIncidentsTotal = Number(postReport?.summary?.incidents_total || 0);
        } catch (error) {
          console.warn('[Workspace] Post-reassignment global validation failed', error);
        }
      }

      const summary = {
        moved: movedItems.length,
        created: createdBuses,
        unresolved: unresolvedItems.length,
        skipped: targets.length - movedItems.length - unresolvedItems.length,
        trigger,
        postIncidentsTotal,
        movedItems,
        unresolvedItems,
      };

      setLastReassignSummary(summary);

      if (!silent) {
        if (movedItems.length > 0) {
          const postLabel = Number.isFinite(postIncidentsTotal)
            ? ` | incidencias tras reasignacion: ${postIncidentsTotal}`
            : '';
          notifications.success(
            'Reasignacion aplicada',
            `${movedItems.length} movimiento(s), ${createdBuses} bus(es) nuevo(s), ${unresolvedItems.length} pendiente(s)${postLabel}`,
          );
        } else {
          notifications.warning(
            'Sin movimientos aplicados',
            `No se encontro una reasignacion viable para ${targets.length} incidencia(s) critica(s)`,
          );
        }
      }

      return summary;
    } catch (error) {
      console.error('[Workspace] runCriticalReassignment failed', error);
      if (!silent) {
        notifications.error('Error al reasignar', error?.message || 'No se pudo completar la reasignacion');
      }
      return null;
    } finally {
      setReassignRunning(false);
    }
  }, [
    reassignRunning,
    wsConnected,
    getCriticalReassignTargets,
    canAssignRoute,
    routeOverlapsBus,
    evaluatePlacementScore,
    requestPositioningRefresh,
    buildValidationDaysPayload,
    validateAllBuses,
    onValidationReportChange,
  ]);

  // handleDropRoute con insercion por horario y validacion de solapamiento
  const handleDropRoute = useCallback(async (route, busId) => {
    const targetBus = buses.find((b) => b.id === busId);
    if (!targetBus) {
      return { success: false, reason: 'Bus no encontrado' };
    }

    // Validar si ya existe
    const exists = targetBus.routes.some((r) => r.id === route.id);
    if (exists) {
      notifications.warning('Ruta duplicada', 'Esta ruta ya esta asignada a este bus');
      return { success: false, reason: 'Ruta duplicada' };
    }

    // Verificar solapamiento con rutas existentes
    const hasOverlap = targetBus.routes.some((existingRoute) =>
      checkOverlap(route.startTime, route.endTime, existingRoute.startTime, existingRoute.endTime)
    );

    if (hasOverlap) {
      notifications.error(
        'Solapamiento de horario',
        `La ruta ${route.code} se solapa con otra ruta en ${busId}. No se puede asignar.`
      );
      return { success: false, reason: 'Solapamiento de horario' };
    }

    // Calcular posicion de insercion por horario (orden cronologico)
    const routeStartMinutes = timeToMinutes(route.startTime);
    let insertPosition = targetBus.routes.length;

    for (let i = 0; i < targetBus.routes.length; i++) {
      const existingStartMinutes = timeToMinutes(targetBus.routes[i].startTime);
      if (routeStartMinutes < existingStartMinutes) {
        insertPosition = i;
        break;
      }
    }

    // Validacion OSRM: si no es viable no se mueve y la ruta debe permanecer en origen.
    setPendingValidations((prev) => new Set(prev).add(route.id));

    try {
      const result = await canAssignRoute(route, targetBus.routes);

      if (!result.feasible) {
        notifications.error(
          'Ruta incompatible',
          result.reason || 'No hay margen suficiente para posicionamiento entre rutas'
        );
        return { success: false, reason: result.reason || 'Ruta incompatible' };
      }

      // Insertar la ruta en la posicion calculada
      setBuses((prev) => prev.map((bus) => {
        if (bus.id !== busId) return bus;

        const newRoutes = [...bus.routes];
        newRoutes.splice(insertPosition, 0, route);
        return { ...bus, routes: newRoutes };
      }));
      requestPositioningRefresh([busId]);

      notifications.success('Ruta asignada', `${route.code} -> ${busId} (posicion ${insertPosition + 1})`);
      return { success: true };
    } catch (error) {
      console.error('Validation error:', error);
      notifications.error(
        'Error de validacion',
        'No se pudo validar la compatibilidad. La ruta se mantiene en su origen.'
      );
      return { success: false, reason: error?.message || 'Error de validacion' };
    } finally {
      setPendingValidations((prev) => {
        const next = new Set(prev);
        next.delete(route.id);
        return next;
      });
    }
  }, [buses, canAssignRoute, requestPositioningRefresh]);

  // handleDragEnd definido DESPUES de handleDropRoute
  const handleDragEnd = useCallback(async (event) => {
    const { active, over } = event;
    setActiveDragItem(null);
    setIsDraggingRoute(false);
    setIsOverWorkspace(false);
    
    // Si no hay over, significa que se solto fuera de cualquier zona
    if (!over) {
      notifications.info('Suelta en una zona valida', 'Arrastra a un bus, al workspace o a la zona de transferencia');
      return;
    }

    const activeData = active.data.current;
    const overId = over.id;
    const overData = over.data.current;

    if (activeData?.type === 'route') {
      const route = activeData.route;
      const source = activeData.source; // 'bus', 'transfer', 'palette'
      const sourceBusId = activeData.busId;
      
      console.log('[DnD] Drag end:', { 
        routeId: route.id, 
        source, 
        sourceBusId, 
        overId, 
        overType: overData?.type 
      });
      
      // ========== SOLTAR EN ZONA DE TRANSFERENCIA ==========
      if (overId === 'transfer-zone' || overData?.type === 'transfer-zone') {
        // Si ya esta en transferencia, no hacer nada
        if (source === 'transfer') {
          notifications.info('Ruta ya en transferencia', `${route.code} esta listo para mover`);
          return;
        }

        // Anadir a zona de transferencia si no esta ya
        setTransferRoutes((prev) => {
          if (prev.some(r => r.id === route.id)) return prev;
          return [...prev, route];
        });

        // Si viene de un bus, quitarlo solo despues de agregar en transferencia
        if (source === 'bus' && sourceBusId) {
          setBuses((prev) => prev.map((bus) => {
            if (bus.id !== sourceBusId) return bus;
            return { ...bus, routes: bus.routes.filter((r) => r.id !== route.id) };
          }));
        }
        notifications.success('Ruta en transferencia', `${route.code} listo para mover`);
        return;
      }
      
      // ========== SOLTAR EN UN BUS ==========
      if ((typeof overId === 'string' && overId.startsWith('bus-')) || overData?.type === 'bus') {
        const busId = (typeof overId === 'string' && overId.startsWith('bus-')) ? overId.replace('bus-', '') : overId;
        
        // No hacer nada si se suelta en el mismo bus
        if (source === 'bus' && sourceBusId === busId) {
          return;
        }

        const dropResult = await handleDropRoute(route, busId);
        if (!dropResult?.success) {
          return;
        }

        // Solo quitamos del origen cuando el destino ya acepto la ruta.
        if (source === 'transfer') {
          setTransferRoutes((prev) => prev.filter((r) => r.id !== route.id));
        } else if (source === 'bus' && sourceBusId) {
          setBuses((prev) => prev.map((bus) => {
            if (bus.id !== sourceBusId) return bus;
            return { ...bus, routes: bus.routes.filter((r) => r.id !== route.id) };
          }));
          requestPositioningRefresh([sourceBusId]);
        }
        requestPositioningRefresh([busId]);
        return;
      } 
      
      // ========== SOLTAR EN WORKSPACE (nuevo bus) ==========
      if (overId === 'workspace' || overData?.type === 'workspace') {
        const newId = generateBusId();
        setBuses((prev) => [...prev, { id: newId, routes: [route], type: 'standard' }]);
        requestPositioningRefresh([newId]);

        // Solo removemos origen despues de crear destino.
        if (source === 'transfer') {
          setTransferRoutes((prev) => prev.filter((r) => r.id !== route.id));
        } else if (source === 'bus' && sourceBusId) {
          setBuses((prev) => prev.map((bus) => {
            if (bus.id !== sourceBusId) return bus;
            return { ...bus, routes: bus.routes.filter((r) => r.id !== route.id) };
          }));
          requestPositioningRefresh([sourceBusId]);
        }

        notifications.success('Nuevo bus creado', `${route.code} asignado a ${newId}`);
        return;
      }
      
      // Si llegamos aqui, no se reconocio la zona de drop
      console.warn('[DnD] Zona de drop no reconocida:', overId, overData);
    }
  }, [generateBusId, handleDropRoute, requestPositioningRefresh]);

  const handleRemoveRoute = useCallback((busId, routeId) => {
    setBuses(prev => prev.map(bus => {
      if (bus.id !== busId) return bus;
      return { ...bus, routes: bus.routes.filter(r => r.id !== routeId) };
    }));
    requestPositioningRefresh([busId]);
  }, [requestPositioningRefresh]);

  const handleClearAll = useCallback(() => {
    if (!confirm('Limpiar todo el horario?')) return;
    setBuses(prev => prev.map(bus => ({ ...bus, routes: [] })));
    notifications.info('Horario limpiado');
  }, []);

  const buildScheduleData = useCallback(() => ({
    day: activeDay,
    mode,
    buses: buses.map((bus) => ({
      bus_id: bus.id,
      items: bus.routes.map((route, index) => {
        const positioningMinutes = extractPositioningMinutes(route);
        const startLocation = Array.isArray(route.start_location)
          ? route.start_location
          : (Array.isArray(route.start_loc) ? route.start_loc : (
            Array.isArray(route?.rawRoute?.start_location)
              ? route.rawRoute.start_location
              : (Array.isArray(route?.rawRoute?.start_loc) ? route.rawRoute.start_loc : null)
          ));
        const endLocation = Array.isArray(route.end_location)
          ? route.end_location
          : (Array.isArray(route.end_loc) ? route.end_loc : (
            Array.isArray(route?.rawRoute?.end_location)
              ? route.rawRoute.end_location
              : (Array.isArray(route?.rawRoute?.end_loc) ? route.rawRoute.end_loc : null)
          ));

        return {
          route_id: route.id,
          route_code: route.code,
          start_time: route.startTime,
          end_time: route.endTime,
          origin: route.origin,
          destination: route.destination,
          type: route.type,
          order: index,
          school_name: route.school || route.school_name || route?.rawRoute?.school_name || null,
          stops: Array.isArray(route.stops) ? route.stops : [],
          start_location: startLocation,
          end_location: endLocation,
          time_shift_minutes: Number(
            route.timeShift ??
            route.time_shift_minutes ??
            route?.rawRoute?.time_shift_minutes ??
            0
          ) || 0,
          deadhead_minutes: positioningMinutes,
          positioning_minutes: positioningMinutes,
          capacity_needed: getItemCapacityNeeded(route, routeCapacityById),
          vehicle_capacity_min: route.vehicle_capacity_min ?? route.vehicleCapacityMin ?? null,
          vehicle_capacity_max: route.vehicle_capacity_max ?? route.vehicleCapacityMax ?? null,
          vehicle_capacity_range: route.vehicle_capacity_range ?? route.vehicleCapacityRange ?? null,
          contract_id: route.contract_id ?? route.contractId ?? route?.rawRoute?.contract_id ?? null,
          is_locked: Boolean(route.is_locked ?? route.isLocked ?? route?.rawRoute?.is_locked),
        };
      }),
    })),
    stats: {
      total_buses: buses.length,
      total_routes: buses.reduce((sum, b) => sum + b.routes.length, 0),
    },
  }), [activeDay, buses, mode, routeCapacityById]);

  useEffect(() => {
    if (typeof onLiveScheduleChange !== 'function') return;
    try {
      onLiveScheduleChange(buildScheduleData().buses);
    } catch {
      // no-op: live map preview must not break workspace interactions
    }
  }, [buildScheduleData, onLiveScheduleChange]);

  const handleSaveDraft = useCallback(async () => {
    setIsSaving(true);
    const loadingToast = notifications.loading('Guardando borrador...');
    try {
      localStorage.setItem(STORAGE_KEY_DRAFT, JSON.stringify(buses));
      localStorage.setItem(STORAGE_KEY_STATUS, JSON.stringify({
        mode,
        activeDay,
        lastSaved: new Date().toISOString(),
      }));

      if (onSave) {
        await onSave(buildScheduleData());
      }

      setHasUnsavedChanges(false);
      notifications.dismiss(loadingToast);
      notifications.success('Borrador guardado', 'Cambios guardados localmente y en el sistema');
    } catch (error) {
      console.error('Error saving draft:', error);
      notifications.dismiss(loadingToast);
      notifications.error('Error al guardar', error.message || 'No se pudo guardar el borrador');
    } finally {
      setIsSaving(false);
    }
  }, [activeDay, buses, buildScheduleData, mode, onSave]);

  const handlePublish = useCallback(async () => {
    const hasErrors = Object.values(validationResults).some(v => v.errors?.length > 0);
    if (hasErrors) {
      notifications.error('No se puede publicar', 'Corrige los errores primero');
      return;
    }

    setIsPublishing(true);
    const loadingToast = notifications.loading('Publicando horario...');

    try {
      const scheduleData = buildScheduleData();

      if (onPublish) {
        await onPublish(scheduleData);
      } else if (onSave) {
        await onSave(scheduleData);
      }

      setHasUnsavedChanges(false);
      notifications.dismiss(loadingToast);
      notifications.success('Horario publicado', 'El horario ha sido guardado correctamente');
    } catch (error) {
      console.error('Error publishing:', error);
      notifications.dismiss(loadingToast);
      notifications.error('Error al publicar', error.message);
    } finally {
      setIsPublishing(false);
    }
  }, [buildScheduleData, onPublish, onSave, validationResults]);

  const handleExportPdf = useCallback(() => {
    if (typeof onExport !== 'function') {
      notifications.warning('Exportacion no disponible', 'No hay handler de exportacion configurado');
      return;
    }
    onExport({
      schedule: buildScheduleData().buses,
      day: activeDay,
      source: 'workspace',
    });
  }, [activeDay, buildScheduleData, onExport]);

  const hasErrors = Object.values(validationResults).some(v => v.errors?.length > 0);
  const hasRoutesAssigned = buses.some((bus) => Array.isArray(bus?.routes) && bus.routes.length > 0);

  const dropAnimation = {
    sideEffects: defaultDropAnimationSideEffects({ styles: { active: { opacity: '0.5' } } }),
  };

  const renderDragOverlay = useCallback((item) => {
    if (!item || item.type !== 'route') return null;

    const route = item.route;
    const isEntry = route.type === 'entry';
    const locationLabel = route.school || route.school_name || route.destination || route.origin || 'Colegio';

    return (
      <div className="scale-[1.02] shadow-2xl">
        <div className="min-w-[220px] rounded-md border border-[#37526a] bg-[#0f1a27]/95 px-3 py-2 shadow-[0_14px_40px_rgba(1,8,14,0.65)] backdrop-blur-sm">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] font-semibold text-slate-100 truncate data-mono tracking-[0.04em]">
              {route.code}
            </div>
            <span className={`px-1.5 py-0.5 rounded-sm border text-[9px] font-semibold uppercase tracking-[0.12em] data-mono ${
              isEntry
                ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-200'
                : 'border-amber-500/40 bg-amber-500/10 text-amber-200'
            }`}>
              {isEntry ? 'ENTRADA' : 'SALIDA'}
            </span>
          </div>
          <div className="mt-1 text-[11px] text-slate-300 truncate">
            {locationLabel}
          </div>
          <div className="mt-1.5 border-t border-[#2c4258] pt-1.5 text-[10px] text-slate-400 data-mono">
            {route.startTime} | {route.endTime}
          </div>
        </div>
      </div>
    );
  }, []);

  // ============================================================================
  // HANDLERS DE EDICIIN DE RUTAS
  // ============================================================================
  
  const handleOpenCreateRoute = useCallback(() => {
    setRouteEditModal({
      isOpen: true,
      mode: 'create',
      route: null,
    });
  }, []);

  const handleOpenEditRoute = useCallback((route) => {
    setRouteEditModal({
      isOpen: true,
      mode: 'edit',
      route: route,
    });
  }, []);

  const handleOpenDuplicateRoute = useCallback((route) => {
    setRouteEditModal({
      isOpen: true,
      mode: 'duplicate',
      route: { ...route, id: `ROUTE_${Date.now()}`, code: `${route.code}_copy` },
    });
  }, []);

  const handleCloseRouteModal = useCallback(() => {
    setRouteEditModal(prev => ({ ...prev, isOpen: false }));
  }, []);

  const handleSaveRoute = useCallback((savedRoute) => {
    const routeData = {
      id: savedRoute.id,
      code: savedRoute.code,
      startTime: savedRoute.startTime,
      endTime: savedRoute.endTime,
      origin: savedRoute.origin,
      destination: savedRoute.destination,
      type: savedRoute.type,
      stops: savedRoute.stops,
      school: savedRoute.school,
      duration: savedRoute.duration,
      capacityNeeded: savedRoute.capacityNeeded ?? 0,
      vehicle_capacity_min: savedRoute.vehicle_capacity_min ?? savedRoute.vehicleCapacityMin ?? null,
      vehicle_capacity_max: savedRoute.vehicle_capacity_max ?? savedRoute.vehicleCapacityMax ?? null,
      vehicle_capacity_range: savedRoute.vehicle_capacity_range ?? savedRoute.vehicleCapacityRange ?? null,
      start_location: savedRoute.start_location ?? savedRoute.startLocation ?? null,
      end_location: savedRoute.end_location ?? savedRoute.endLocation ?? null,
      contract_id: savedRoute.contract_id ?? savedRoute.contractId ?? null,
      rawRoute: {
        ...(savedRoute.rawRoute || {}),
        route_id: savedRoute.id,
        start_time: savedRoute.startTime,
        end_time: savedRoute.endTime,
        capacity_needed: savedRoute.capacityNeeded ?? 0,
        vehicle_capacity_min: savedRoute.vehicle_capacity_min ?? savedRoute.vehicleCapacityMin ?? null,
        vehicle_capacity_max: savedRoute.vehicle_capacity_max ?? savedRoute.vehicleCapacityMax ?? null,
        vehicle_capacity_range: savedRoute.vehicle_capacity_range ?? savedRoute.vehicleCapacityRange ?? null,
        contract_id: savedRoute.contract_id ?? savedRoute.contractId ?? null,
      },
    };

    if (routeEditModal.mode === 'create' || routeEditModal.mode === 'duplicate') {
      // Agregar nueva ruta a availableRoutes
      setAvailableRoutes(prev => [...prev, routeData]);
      notifications.success(
        routeEditModal.mode === 'create' ? 'Ruta creada' : 'Ruta duplicada',
        `La ruta ${savedRoute.code} ha sido anadida`
      );
    } else {
      // Actualizar ruta existente
      setAvailableRoutes(prev => 
        prev.map(r => r.id === savedRoute.id ? routeData : r)
      );
      setTransferRoutes(prev =>
        prev.map(r => r.id === savedRoute.id ? { ...r, ...routeData } : r)
      );
      // Tambien actualizar en buses si esta asignada
      setBuses(prev => 
        prev.map(bus => ({
          ...bus,
          routes: sortRoutesByTime(bus.routes.map(r => 
            r.id === savedRoute.id ? { ...r, ...routeData } : r
          ))
        }))
      );
      requestPositioningRefresh();
      notifications.success('Ruta actualizada', `La ruta ${savedRoute.code} ha sido modificada`);
    }
    setHasUnsavedChanges(true);
  }, [requestPositioningRefresh, routeEditModal.mode]);

  const normalizeTime = useCallback((value) => {
    if (!value) return '00:00';
    if (typeof value === 'string') {
      const parts = value.split(':');
      if (parts.length >= 2) {
        return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
      }
    }
    if (typeof value === 'object' && typeof value.hour === 'number' && typeof value.minute === 'number') {
      return `${String(value.hour).padStart(2, '0')}:${String(value.minute).padStart(2, '0')}`;
    }
    return '00:00';
  }, []);

  const extractItemLocations = useCallback((item, fallbackRoute = null) => {
    const fallbackStart = fallbackRoute?.start_location || [0, 0];
    const fallbackEnd = fallbackRoute?.end_location || [0, 0];
    const stops = Array.isArray(item?.stops) ? item.stops : [];
    if (stops.length > 0) {
      const first = stops[0];
      const last = stops[stops.length - 1];
      const firstLat = first?.lat ?? first?.latitude;
      const firstLon = first?.lon ?? first?.lng ?? first?.longitude;
      const lastLat = last?.lat ?? last?.latitude;
      const lastLon = last?.lon ?? last?.lng ?? last?.longitude;
      if ([firstLat, firstLon, lastLat, lastLon].every((n) => Number.isFinite(n))) {
        return {
          start_location: [firstLat, firstLon],
          end_location: [lastLat, lastLon],
        };
      }
    }
    return {
      start_location: fallbackStart,
      end_location: fallbackEnd,
    };
  }, []);

  const buildValidationDaysPayload = useCallback((overrideActiveDayBuses = null) => {
    const activeDayBuses = Array.isArray(overrideActiveDayBuses) ? overrideActiveDayBuses : buses;

    if (scheduleByDay && typeof scheduleByDay === 'object') {
      return ALL_DAYS.map((day) => {
        const shouldUseLiveWorkspace = day === activeDay;
        const daySchedule = shouldUseLiveWorkspace
          ? activeDayBuses.map((bus) => ({
            bus_id: bus.id,
            items: bus.routes.map((route) => ({
              route_id: route.route_id || route.id,
              id: route.id || route.route_id,
              start_time: normalizeTime(route.startTime || route.start_time),
              end_time: normalizeTime(route.endTime || route.end_time),
              type: route.type || 'entry',
              school_name: route.school || route.school_name || null,
              start_location: route.start_location || route.start_loc || route?.rawRoute?.start_location || route?.rawRoute?.start_loc || [0, 0],
              end_location: route.end_location || route.end_loc || route?.rawRoute?.end_location || route?.rawRoute?.end_loc || [0, 0],
              stops: Array.isArray(route.stops) ? route.stops : [],
            })),
          }))
          : (scheduleByDay?.[day]?.schedule || []);
        const busesPayload = daySchedule.map((bus) => {
          const busId = bus.bus_id || bus.id || 'unknown';
          const items = Array.isArray(bus.items) ? bus.items : (bus.routes || []);
          const routesPayload = items.map((item) => {
            const fallbackRoute = transformRoutes.find((r) => r.id === (item.route_id || item.id));
            const locations = extractItemLocations(item, fallbackRoute);
            return {
              id: item.route_id || item.id,
              route_id: item.route_id || item.id,
              start_time: normalizeTime(item.start_time || item.startTime),
              end_time: normalizeTime(item.end_time || item.endTime),
              type: item.type || 'entry',
              school_name: item.school_name || item.school || null,
              ...locations,
            };
          });
          return { bus_id: busId, routes: routesPayload };
        });
        return { day, buses: busesPayload };
      });
    }

    return [{
      day: activeDay,
      buses: activeDayBuses.map((bus) => ({
        bus_id: bus.id,
        routes: bus.routes.map((route) => ({
          id: route.id || route.route_id,
          route_id: route.route_id || route.id,
          start_time: normalizeTime(route.startTime || route.start_time),
          end_time: normalizeTime(route.endTime || route.end_time),
          type: route.type || 'entry',
          school_name: route.school || route.school_name || null,
          start_location: route.start_location || route.start_loc || [0, 0],
          end_location: route.end_location || route.end_loc || [0, 0],
        })),
      })),
    }];
  }, [scheduleByDay, activeDay, buses, normalizeTime, transformRoutes, extractItemLocations]);

  const handleValidateAllBuses = useCallback(async () => {
    if (globalValidationRunning || reassignRunning) return;
    setGlobalValidationRunning(true);
    try {
      const daysPayload = buildValidationDaysPayload();
      const result = await validateAllBuses(daysPayload, false);
      setGlobalValidationReport(result);
      if (onValidationReportChange) {
        onValidationReportChange(result);
      }
      const refreshResult = await refreshPositioningMinutes();
      const summary = result?.summary || {};
      let autoSummary = null;
      if (autoReassignCritical && Number(summary.incidents_error || 0) > 0) {
        autoSummary = await runCriticalReassignment({
          trigger: 'auto',
          silent: true,
          reportOverride: result,
          includeLocal: false,
        });
      }

      const autoText = autoSummary && autoSummary.moved > 0
        ? ` | auto-reasignadas ${autoSummary.moved} incidencia(s)`
        : '';

      notifications.success(
        'Validacion global completada',
        `${summary.incidents_total || 0} incidencias en ${summary.total_buses || 0} buses | Pos. OSRM actualizada en ${refreshResult?.updated || 0} buses${autoText}`
      );
    } catch (error) {
      notifications.error('Error de validacion global', error.message || 'No se pudo validar todo');
    } finally {
      setGlobalValidationRunning(false);
    }
  }, [
    globalValidationRunning,
    reassignRunning,
    buildValidationDaysPayload,
    validateAllBuses,
    onValidationReportChange,
    refreshPositioningMinutes,
    autoReassignCritical,
    runCriticalReassignment,
  ]);

  const incidents = useMemo(() => (
    Array.isArray(globalValidationReport?.incidents) ? globalValidationReport.incidents : []
  ), [globalValidationReport]);

  const filteredIncidents = useMemo(() => {
    return incidents.filter((incident) => {
      if (globalFilter.severity !== 'all' && incident.severity !== globalFilter.severity) return false;
      if (globalFilter.day !== 'all' && incident.day !== globalFilter.day) return false;
      if (globalFilter.bus !== 'all' && incident.bus_id !== globalFilter.bus) return false;
      if (globalFilter.query) {
        const haystack = [
          incident.route_a,
          incident.route_b,
          incident.issue_type,
          incident.message,
          incident.suggestion,
        ].join(' ').toLowerCase();
        if (!haystack.includes(globalFilter.query.toLowerCase())) return false;
      }
      return true;
    });
  }, [incidents, globalFilter]);

  const availableIncidentDays = useMemo(() => (
    [...new Set(incidents.map((incident) => incident.day).filter(Boolean))]
  ), [incidents]);

  const availableIncidentBuses = useMemo(() => (
    [...new Set(incidents.map((incident) => incident.bus_id).filter(Boolean))]
  ), [incidents]);

  const handleExportIncidents = useCallback(() => {
    if (!globalValidationReport) {
      notifications.warning('Sin reporte', 'Ejecuta primero la validacion global');
      return;
    }
    downloadIncidentsAsCsv(globalValidationReport);
    downloadIncidentsAsJson(globalValidationReport);
    notifications.success('Incidencias descargadas', 'Se descargaron CSV y JSON');
  }, [globalValidationReport]);

  const handleManualReassign = useCallback(async () => {
    await runCriticalReassignment({
      trigger: 'manual',
      silent: false,
      reportOverride: globalValidationReport,
    });
  }, [runCriticalReassignment, globalValidationReport]);

  const getListSortIndicator = useCallback((key) => {
    if (listSort.key !== key) return '↕';
    return listSort.direction === 'asc' ? '↑' : '↓';
  }, [listSort]);

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={pointerWithin}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="control-panel flex flex-col h-full rounded-[10px] border border-[#2b4055]">
        {/* Toolbar consolidada */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[#2a3f54] bg-[#0d1723]/95 backdrop-blur-sm">
          {/* Izquierda: Estado, dias y vista */}
          <div className="flex items-center gap-3">
            {/* Modo */}
            <StatusBadge 
              mode={mode} 
              isDirty={hasUnsavedChanges}
              hasErrors={hasErrors}
              hasUnsavedChanges={hasUnsavedChanges}
            />
            
            {/* Selector de dia */}
            <div className="flex items-center gap-0.5 bg-[#101a26] rounded-md p-0.5 border border-[#2b4056]">
              {ALL_DAYS.map(day => (
                <button
                  key={day}
                  onClick={() => setActiveDay(day)}
                  className={`
                    px-2 py-0.5 rounded-sm text-[10px] font-semibold tracking-wide transition-all
                    ${activeDay === day 
                      ? 'bg-[#214a63] text-[#d8edf8] border border-cyan-400/30' : 'text-slate-500 hover:text-slate-200 hover:bg-[#1a2837]'
                    }
                  `}
                  title={DAY_LABELS[day]}
                >
                  {day}
                </button>
              ))}
            </div>

            <div className="w-px h-5 bg-slate-700" />

            {/* Toggle Vista Timeline/Lista */}
            <div className="flex bg-[#101a26] rounded-md p-0.5 border border-[#2b4056]">
              <button
                onClick={() => setViewMode('timeline')}
                className={`px-2.5 py-1 rounded text-[10px] font-medium transition-all ${
                  viewMode === 'timeline' 
                    ? 'bg-[#214a63] text-[#d8edf8] border border-cyan-400/30' : 'text-slate-500 hover:text-slate-200'
                }`}
              >
                Timeline
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`px-2.5 py-1 rounded text-[10px] font-medium transition-all ${
                  viewMode === 'list' 
                    ? 'bg-[#214a63] text-[#d8edf8] border border-cyan-400/30' : 'text-slate-500 hover:text-slate-200'
                }`}
              >
                Lista
              </button>
            </div>

            {/* Stats */}
            <div className="flex items-center gap-2 text-[10px] text-slate-500 uppercase tracking-[0.12em] data-mono">
              <span><strong className="text-slate-200 tabular-nums">{displayedBuses.length}</strong> buses</span>
              <span className="text-slate-600">|</span>
              <span><strong className="text-slate-200 tabular-nums">{displayedBuses.reduce((s, b) => s + b.routes.length, 0)}</strong> rutas</span>
              {isBusFilterActive && (
                <>
                  <span className="text-slate-600">|</span>
                  <span className="text-slate-400">filtrados</span>
                </>
              )}
            </div>
          </div>

          {/* Derecha: Acciones */}
          <div className="flex items-center gap-1.5 data-mono">
            {/* OSRM */}
            <div 
              className={`flex items-center gap-1 px-1.5 py-1 rounded-sm border text-[9px] font-semibold tracking-wider ${
                osrmBadgeState === 'connected'
                  ? 'bg-cyan-500/10 text-cyan-300 border-cyan-400/30'
                  : osrmBadgeState === 'reconnecting'
                    ? 'bg-amber-500/10 text-amber-300 border-amber-400/30'
                    : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
              }`}
              title={
                osrmBadgeState === 'connected'
                  ? 'Validacion OSRM activa'
                  : osrmBadgeState === 'reconnecting'
                    ? 'Reconectando validacion OSRM'
                    : 'Sin conexion'
              }
            >
              {osrmBadgeState === 'connected' ? (
                <Wifi className="w-2.5 h-2.5" />
              ) : (
                <WifiOff className={`w-2.5 h-2.5 ${osrmBadgeState === 'reconnecting' ? 'animate-pulse' : ''}`} />
              )}
              <span className="hidden sm:inline">OSRM</span>
            </div>

            <button
              onClick={handleValidateAllBuses}
              disabled={globalValidationRunning || reassignRunning || buses.length === 0}
              className="px-2.5 py-1.5 control-btn disabled:opacity-50 rounded-md text-[10px] font-semibold uppercase tracking-[0.08em] transition-colors flex items-center gap-1"
              title="Validar toda la planificacion por dia"
            >
              {globalValidationRunning ? (
                <div className="w-3 h-3 border-2 border-slate-500 border-t-cyan-300 rounded-full animate-spin" />
              ) : (
                <CheckCircle className="w-3 h-3" />
              )}
              Comprobar todo
            </button>

            <button
              onClick={handleManualReassign}
              disabled={globalValidationRunning || reassignRunning || buses.length === 0}
              className="px-2.5 py-1.5 control-btn disabled:opacity-50 rounded-md text-[10px] font-semibold uppercase tracking-[0.08em] transition-colors flex items-center gap-1"
              title="Reasignar automaticamente incidencias criticas detectadas"
            >
              {reassignRunning ? (
                <div className="w-3 h-3 border-2 border-slate-500 border-t-cyan-300 rounded-full animate-spin" />
              ) : (
                <GitBranch className="w-3 h-3" />
              )}
              Reasignar
            </button>

            <label
              className="px-2 py-1 rounded-sm border border-[#2b4056] bg-[#101a26] text-[9px] font-semibold uppercase tracking-[0.08em] text-slate-300 flex items-center gap-1.5 cursor-pointer select-none"
              title="Si esta activo, al comprobar todo el sistema reasigna automaticamente errores criticos"
            >
              <input
                type="checkbox"
                checked={autoReassignCritical}
                onChange={(event) => setAutoReassignCritical(Boolean(event.target.checked))}
                className="accent-cyan-400"
              />
              Auto critico
            </label>

            {positioningRefreshRunning && (
              <div
                className="px-2 py-1 rounded-sm border border-cyan-400/30 bg-cyan-500/10 text-cyan-200 text-[9px] font-semibold tracking-[0.08em] uppercase flex items-center gap-1"
                title="Actualizando tiempos reales de posicionamiento con OSRM"
              >
                <div className="w-2.5 h-2.5 border border-cyan-300/50 border-t-cyan-200 rounded-full animate-spin" />
                R OSRM {positioningRefreshStats.done}/{positioningRefreshStats.total || '?'}
              </div>
            )}

            <button
              onClick={handleExportIncidents}
              disabled={!globalValidationReport}
              className="px-2.5 py-1.5 control-btn disabled:opacity-50 rounded-md text-[10px] font-semibold uppercase tracking-[0.08em] transition-colors flex items-center gap-1"
              title="Descargar incidencias en CSV y JSON"
            >
              <Download className="w-3 h-3" />
              Incidencias
            </button>

            <button
              onClick={handleExportPdf}
              disabled={!hasRoutesAssigned}
              className="px-2.5 py-1.5 control-btn disabled:opacity-50 rounded-md text-[10px] font-semibold uppercase tracking-[0.08em] transition-colors flex items-center gap-1"
              title="Exportar PDF del horario actual (estado vivo)"
            >
              <Download className="w-3 h-3" />
              Exportar PDF
            </button>

            <div className="w-px h-5 bg-slate-700 mx-0.5" />

            <button
              onClick={handleOpenCreateRoute}
              className="px-2 py-1.5 control-btn rounded-md text-[10px] font-semibold transition-colors flex items-center gap-1"
              title="Crear ruta manual"
            >
              <Plus className="w-3 h-3" />
              Ruta
            </button>

            <button
              onClick={() => selectedRoute && handleOpenEditRoute(selectedRoute)}
              disabled={!selectedRoute}
              className="px-2 py-1.5 control-btn disabled:opacity-50 rounded-md text-[10px] font-semibold transition-colors flex items-center gap-1"
              title={selectedRoute ? `Editar ${selectedRoute.code}` : 'Selecciona una ruta para editarla'}
            >
              <Edit3 className="w-3 h-3" />
              Editar
            </button>

            <button
              onClick={() => selectedRoute && handleOpenDuplicateRoute(selectedRoute)}
              disabled={!selectedRoute}
              className="px-2 py-1.5 control-btn disabled:opacity-50 rounded-md text-[10px] font-semibold transition-colors flex items-center gap-1"
              title={selectedRoute ? `Duplicar ${selectedRoute.code}` : 'Selecciona una ruta para duplicarla'}
            >
              <Copy className="w-3 h-3" />
              Duplicar
            </button>

            {/* Acciones compactas */}
            <button
              onClick={handleClearAll}
              disabled={buses.every(b => b.routes.length === 0)}
              className="px-2 py-1.5 control-btn disabled:opacity-50 rounded-md text-[10px] font-semibold transition-colors"
              title="Limpiar"
            >
              <Trash2 className="w-3 h-3" />
            </button>
            
            <button
              onClick={handleAddBus}
              className="px-2 py-1.5 control-btn rounded-md text-[10px] font-semibold transition-colors flex items-center gap-1"
            >
              <Plus className="w-3 h-3" />
              Bus
            </button>
            
            <button
              onClick={handleSaveDraft}
              disabled={isSaving || !hasUnsavedChanges}
              className="px-2.5 py-1.5 control-btn disabled:opacity-50 rounded-md text-[10px] font-semibold uppercase tracking-[0.08em] transition-colors flex items-center gap-1"
            >
              {isSaving ? (
                <div className="w-3 h-3 border-2 border-[#9aa6b6]/35 border-t-[#9aa6b6] rounded-full animate-spin" />
              ) : (
                <Save className="w-3 h-3" />
              )}
              {isSaving ? 'Guardando...' : 'Guardar'}
            </button>
            
            <button
              onClick={handlePublish}
              disabled={isPublishing || hasErrors || buses.every(b => b.routes.length === 0)}
              className="px-3 py-1.5 control-btn-primary disabled:opacity-50 disabled:cursor-not-allowed rounded-md text-[10px] font-bold tracking-[0.14em] uppercase transition-colors flex items-center gap-1"
            >
              {isPublishing ? (
                <div className="w-3 h-3 border-2 border-[#051018]/40 border-t-[#051018] rounded-full animate-spin" />
              ) : (
                <Upload className="w-3 h-3" />
              )}
              Publicar
            </button>
          </div>
        </div>

        {/* Contenido principal */}
        <div className="flex-1 flex overflow-hidden" style={{ minHeight: 0 }}>
          {/* Panel izquierdo: Zona de Transferencia */}
          <div 
            className={`
              flex-shrink-0 flex flex-col border-r border-[#2a3f54] bg-[#0b141f] transition-all duration-300
              ${transferRoutes.length > 0 ? 'w-56' : 'w-16'}
            `}
          >
            <div className="flex-1 overflow-y-auto p-2">
              <TransferZone 
                routes={transferRoutes}
                isDragging={isDraggingRoute}
                onRouteRemove={(routeId) => {
                  setTransferRoutes(prev => prev.filter(r => r.id !== routeId));
                }}
              />
            </div>
          </div>

          {/* Area central: Workspace */}
          <div className="flex-1 p-3 overflow-hidden relative" style={{ minWidth: 0 }}>
              <WorkspaceArea isOverWorkspace={isOverWorkspace}>
                {isBusFilterActive && displayedBuses.length === 0 ? (
                  <div className="h-full flex items-center justify-center rounded-md border border-[#2a3f54] bg-[#0d1622]">
                    <div className="text-center px-6">
                      <div className="text-[12px] uppercase tracking-[0.12em] text-cyan-300 data-mono font-semibold">
                        Mixto filtrado por pines
                      </div>
                      <p className="mt-2 text-[12px] text-slate-400">
                        No hay buses pineados en este dia. Pinea buses en Mapa o Workspace para mostrarlos aqui.
                      </p>
                    </div>
                  </div>
                ) : displayedBuses.length === 0 || displayedBuses.every(b => b.routes.length === 0) ? (
                  <EmptyWorkspace onAddBus={handleAddBus} />
                ) : viewMode === 'timeline' ? (
                  /* Modo Timeline */
                  <div
                    ref={timelineViewportRef}
                    onMouseDown={handleTimelineMouseDown}
                    className={`bg-[#0a131e] rounded-md border border-[#2a3f54] overflow-x-auto overflow-y-hidden ${isTimelinePanning ? 'cursor-grabbing' : 'cursor-grab'}`}
                  >
                    <div style={{ minWidth: 'max-content' }}>
                    {/* Controles de zoom y rango */}
                    <div data-no-timeline-pan>
                    <TimelineControls
                      zoom={timelineZoom}
                      onZoomChange={setTimelineZoom}
                      onReset={() => {
                        setTimelineZoom(140);
                      }}
                    />
                    </div>
                    
                    {/* Escala de tiempo - sticky */}
                    <div className="sticky top-0 z-10 bg-[#0f141d]" data-no-timeline-pan>
                      <TimelineScale 
                        minHour={timelineRange.min}
                        maxHour={timelineRange.max}
                        pixelsPerHour={effectiveTimelineZoom}
                        segments={compressedSegments}
                        leftOffset={TIMELINE_BUS_INFO_WIDTH}
                      />
                    </div>
                    
                    {/* Filas de buses */}
                    <div className="py-2 border-t border-[#2a4056]/60">
                      {displayedBuses.map((bus) => (
                        <div 
                          key={bus.id} 
                          className={`relative group ${selectedBusId === bus.id ? 'ring-1 ring-cyan-400/40 rounded-md' : ''}`}
                          onClick={() => updateSelectedBus(bus.id)}
                        >
                          <TimelineBusRow
                            bus={bus}
                            routes={bus.routes}
                            validations={validationResults[bus.id]}
                            onRemoveRoute={(routeId) => handleRemoveRoute(bus.id, routeId)}
                            onSelectRoute={(routeId) => updateSelectedRoute(routeId === selectedRouteId ? null : routeId)}
                            isActive={selectedBusId === bus.id}
                            minHour={timelineRange.min}
                            maxHour={timelineRange.max}
                            pixelsPerHour={effectiveTimelineZoom}
                            segments={compressedSegments}
                            selectedRouteId={selectedRouteId}
                            onValidateBus={handleValidateBus}
                            isPinned={pinnedBusIdSet.has(String(bus.id || ''))}
                            onTogglePin={onTogglePinBus}
                          />
                          
                          <button
                            onClick={(e) => { e.stopPropagation(); handleRemoveBus(bus.id); }}
                            className="absolute left-[124px] top-1/2 -translate-y-1/2 w-4 h-4 rounded-sm border border-rose-500/40 bg-[#1b1f2a] text-rose-300 opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center text-[10px] font-bold hover:bg-rose-500/20 z-10"
                            title="Eliminar bus"
                          >
                            -
                          </button>
                        </div>
                      ))}
                    </div>
                    </div>
                  </div>
                ) : (
                  /* Modo Lista */
                  <div className="bg-[#0a131e] rounded-md border border-[#2a3f54] h-full overflow-auto">
                    <table className="w-full min-w-[1600px] text-[11px] data-mono">
                      <thead className="sticky top-0 z-20 bg-[#0f1621] border-b border-[#2a3f54] uppercase tracking-[0.08em] text-[10px] text-slate-400">
                        <tr>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('bus')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Bus <span className="text-[9px] text-slate-500">{getListSortIndicator('bus')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('order')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              # <span className="text-[9px] text-slate-500">{getListSortIndicator('order')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('route')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Ruta <span className="text-[9px] text-slate-500">{getListSortIndicator('route')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('contract')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Contrato <span className="text-[9px] text-slate-500">{getListSortIndicator('contract')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('type')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Tipo <span className="text-[9px] text-slate-500">{getListSortIndicator('type')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('start')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Inicio <span className="text-[9px] text-slate-500">{getListSortIndicator('start')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('end')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Fin <span className="text-[9px] text-slate-500">{getListSortIndicator('end')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('duration')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Dur <span className="text-[9px] text-slate-500">{getListSortIndicator('duration')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('positioning')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Pos. real <span className="text-[9px] text-slate-500">{getListSortIndicator('positioning')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('window')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Ventana <span className="text-[9px] text-slate-500">{getListSortIndicator('window')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('margin')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Margen <span className="text-[9px] text-slate-500">{getListSortIndicator('margin')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('seats')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Plazas <span className="text-[9px] text-slate-500">{getListSortIndicator('seats')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('origin')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Origen <span className="text-[9px] text-slate-500">{getListSortIndicator('origin')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('destination')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Destino <span className="text-[9px] text-slate-500">{getListSortIndicator('destination')}</span>
                            </button>
                          </th>
                          <th className="px-2 py-2 text-left">
                            <button onClick={() => handleListSort('school')} className="flex items-center gap-1 hover:text-cyan-300 transition-colors">
                              Colegio <span className="text-[9px] text-slate-500">{getListSortIndicator('school')}</span>
                            </button>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {groupedListRows.map((entry) => {
                          if (entry.type === 'group') {
                            return (
                              <tr key={entry.key} className="bg-[#112235] border-b border-[#2a3f54]">
                                <td colSpan={15} className="px-2 py-1.5 text-[10px] uppercase tracking-[0.12em] text-cyan-300 font-semibold">
                                  {entry.label}
                                </td>
                              </tr>
                            );
                          }

                          const row = entry.row;
                          const isSelected = selectedRouteId && String(selectedRouteId) === String(row.route.id);
                          return (
                            <tr
                              key={row.key}
                              className={`border-b border-[#203246] cursor-pointer transition-colors ${
                                isSelected ? 'bg-cyan-500/10' : 'hover:bg-[#112335]/50'
                              }`}
                              onClick={() => {
                                updateSelectedBus(row.busId);
                                updateSelectedRoute(row.route.id);
                              }}
                            >
                              <td className="px-2 py-2 font-semibold text-cyan-300">{row.busId}</td>
                              <td className="px-2 py-2 text-slate-300 tabular-nums">{row.order}</td>
                              <td className="px-2 py-2 text-slate-100 font-semibold">{row.routeCode}</td>
                              <td className="px-2 py-2 text-cyan-200">{row.contract}</td>
                              <td className="px-2 py-2">
                                <span className={`px-1.5 py-0.5 rounded-sm border text-[10px] font-semibold ${
                                  row.route.type === 'entry'
                                    ? 'border-cyan-500/35 text-cyan-300 bg-cyan-500/10'
                                    : 'border-amber-500/35 text-amber-300 bg-amber-500/10'
                                }`}>
                                  {row.type}
                                </span>
                              </td>
                              <td className="px-2 py-2 text-slate-200 tabular-nums">{row.startTime}</td>
                              <td className="px-2 py-2 text-slate-200 tabular-nums">{row.endTime}</td>
                              <td className="px-2 py-2 text-slate-300 tabular-nums">{row.durationMinutes}m</td>
                              <td className="px-2 py-2 text-slate-300 tabular-nums">
                                {row.realPositioningMinutes == null ? '--' : `${row.realPositioningMinutes}m`}
                              </td>
                              <td className="px-2 py-2 text-slate-300 tabular-nums">
                                {row.windowMinutes == null ? '--' : `${row.windowMinutes}m`}
                              </td>
                              <td className={`px-2 py-2 tabular-nums font-semibold ${
                                row.marginMinutes == null
                                  ? 'text-slate-500'
                                  : row.marginMinutes < 0
                                    ? 'text-rose-300'
                                    : row.marginMinutes < 6
                                      ? 'text-amber-300'
                                      : 'text-cyan-300'
                              }`}>
                                {row.marginMinutes == null ? '--' : `${row.marginMinutes > 0 ? '+' : ''}${row.marginMinutes}m`}
                              </td>
                              <td className="px-2 py-2 text-slate-200 tabular-nums">
                                {row.seats != null ? `${row.seats}P` : '--'}
                              </td>
                              <td className="px-2 py-2 text-slate-300 max-w-[230px] truncate" title={row.origin}>{row.origin}</td>
                              <td className="px-2 py-2 text-slate-300 max-w-[230px] truncate" title={row.destination}>{row.destination}</td>
                              <td className="px-2 py-2 text-slate-400 max-w-[220px] truncate" title={row.school}>{row.school}</td>
                            </tr>
                          );
                        })}
                        {listRows.length === 0 && (
                          <tr>
                            <td colSpan={15} className="px-2 py-8 text-center text-slate-500 uppercase tracking-[0.12em]">
                              Sin rutas asignadas
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </WorkspaceArea>

              {/* Panel de validacion */}
              {buses.length > 0 && (
                <div className="mt-3 flex-shrink-0">
                  <ValidationSummary buses={buses} validations={validationResults} />
                </div>
              )}

              {globalValidationReport && (
                <div className="mt-3 control-card rounded-md border border-[#2b4056]">
                  <div className="px-3 py-2 border-b border-slate-700/40 flex items-center justify-between">
                    <div className="text-[11px] uppercase tracking-wider text-slate-300 font-semibold">
                      Panel Global de Incidencias OSRM
                    </div>
                    <div className="text-[10px] font-mono text-slate-400 text-right">
                      <div>{globalValidationReport?.summary?.incidents_total || 0} incidencias | {globalValidationReport?.summary?.total_buses || 0} buses</div>
                      {lastReassignSummary && (
                        <div className="text-[9px] text-cyan-300">
                          Reasignacion: {lastReassignSummary.moved} mov. | {lastReassignSummary.unresolved} pendientes
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="px-3 py-2 border-b border-slate-700/40 grid grid-cols-1 md:grid-cols-4 gap-2 data-mono">
                    <select
                      value={globalFilter.severity}
                      onChange={(e) => setGlobalFilter((prev) => ({ ...prev, severity: e.target.value }))}
                      className="bg-[#101a26] border border-[#2b4056] rounded px-2 py-1 text-[11px] text-slate-200 data-mono"
                    >
                      <option value="all">Todas severidades</option>
                      <option value="error">Error</option>
                      <option value="warning">Warning</option>
                      <option value="info">Info</option>
                    </select>

                    <select
                      value={globalFilter.day}
                      onChange={(e) => setGlobalFilter((prev) => ({ ...prev, day: e.target.value }))}
                      className="bg-[#101a26] border border-[#2b4056] rounded px-2 py-1 text-[11px] text-slate-200 data-mono"
                    >
                      <option value="all">Todos dias</option>
                      {availableIncidentDays.map((day) => (
                        <option key={day} value={day}>{day}</option>
                      ))}
                    </select>

                    <select
                      value={globalFilter.bus}
                      onChange={(e) => setGlobalFilter((prev) => ({ ...prev, bus: e.target.value }))}
                      className="bg-[#101a26] border border-[#2b4056] rounded px-2 py-1 text-[11px] text-slate-200 data-mono"
                    >
                      <option value="all">Todos buses</option>
                      {availableIncidentBuses.map((busId) => (
                        <option key={busId} value={busId}>{busId}</option>
                      ))}
                    </select>

                    <div className="flex items-center gap-1 bg-[#101a26] border border-[#2b4056] rounded px-2">
                      <Search className="w-3 h-3 text-slate-500" />
                      <input
                        value={globalFilter.query}
                        onChange={(e) => setGlobalFilter((prev) => ({ ...prev, query: e.target.value }))}
                        placeholder="Buscar ruta, motivo o accion"
                        className="w-full bg-transparent outline-none py-1 text-[11px] text-slate-200 placeholder:text-slate-500"
                      />
                    </div>
                  </div>

                  <div className="max-h-64 overflow-auto">
                    <table className="w-full text-[11px] data-mono">
                      <thead className="sticky top-0 bg-[#111725] text-slate-400 uppercase tracking-wider text-[10px]">
                        <tr>
                          <th className="px-2 py-1 text-left">Dia</th>
                          <th className="px-2 py-1 text-left">Bus</th>
                          <th className="px-2 py-1 text-left">Ruta A</th>
                          <th className="px-2 py-1 text-left">Ruta B</th>
                          <th className="px-2 py-1 text-left">Tipo</th>
                          <th className="px-2 py-1 text-left">Sev</th>
                          <th className="px-2 py-1 text-left">Disp</th>
                          <th className="px-2 py-1 text-left">Viaje</th>
                          <th className="px-2 py-1 text-left">Buffer</th>
                          <th className="px-2 py-1 text-left">Motivo</th>
                          <th className="px-2 py-1 text-left">Accion</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredIncidents.map((incident, idx) => (
                          <tr
                            key={`${incident.day}-${incident.bus_id}-${incident.route_a}-${incident.route_b}-${idx}`}
                            className="border-b border-slate-800/60 hover:bg-slate-800/30 cursor-pointer"
                            onClick={() => {
                              if (incident.bus_id) updateSelectedBus(incident.bus_id);
                              if (incident.route_a) updateSelectedRoute(incident.route_a);
                            }}
                          >
                            <td className="px-2 py-1 text-slate-300">{incident.day || '-'}</td>
                            <td className="px-2 py-1 text-cyan-300">{incident.bus_id || '-'}</td>
                            <td className="px-2 py-1 text-slate-200">{incident.route_a || '-'}</td>
                            <td className="px-2 py-1 text-slate-200">{incident.route_b || '-'}</td>
                            <td className="px-2 py-1 text-slate-400">{incident.issue_type || '-'}</td>
                            <td className={`px-2 py-1 ${incident.severity === 'error' ? 'text-rose-300' : incident.severity === 'warning' ? 'text-amber-300' : 'text-slate-300'}`}>{incident.severity || '-'}</td>
                            <td className="px-2 py-1 text-slate-300">{incident.time_available ?? '-'}</td>
                            <td className="px-2 py-1 text-slate-300">{incident.travel_time ?? '-'}</td>
                            <td className="px-2 py-1 text-slate-300">{incident.buffer_minutes ?? '-'}</td>
                            <td className="px-2 py-1 text-slate-200 max-w-[240px] truncate" title={incident.message || ''}>{incident.message || '-'}</td>
                            <td className="px-2 py-1 text-slate-400 max-w-[240px] truncate" title={incident.suggestion || ''}>{incident.suggestion || '-'}</td>
                          </tr>
                        ))}
                        {filteredIncidents.length === 0 && (
                          <tr>
                            <td colSpan={11} className="px-2 py-3 text-center text-slate-500">
                              No hay incidencias para los filtros activos
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

      <DragOverlay dropAnimation={dropAnimation}>
        {activeDragItem && renderDragOverlay(activeDragItem)}
      </DragOverlay>

      {/* Modal de edicion de rutas */}
      <RouteEditModal
        isOpen={routeEditModal.isOpen}
        onClose={handleCloseRouteModal}
        route={routeEditModal.route}
        mode={routeEditModal.mode}
        onSave={handleSaveRoute}
      />
    </DndContext>
  );
}

export default UnifiedWorkspace;
