import React, { useCallback, useEffect, useRef, useState } from 'react';
import Layout from './components/Layout';
import Sidebar from './components/Sidebar';
import { CompareView } from './components/CompareView';
import OptimizationStudio from './components/OptimizationStudio';
import OptimizationProgress from './components/OptimizationProgress';
import StudioErrorBoundary from './components/StudioErrorBoundary';
import ControlHubPage from './pages/ControlHubPage';
import { notifications } from './services/notifications';
import { clearGeometryCache } from './services/RouteService';
import { buildRouteCapacityMap, getItemCapacityNeeded } from './utils/capacity';
import {
  archiveWorkspace,
  createWorkspace,
  deleteWorkspace,
  getWorkspace,
  getWorkspaceOptimizationOptions,
  getWorkspacePreferences,
  listWorkspaces,
  migrateLegacyWorkspaces,
  optimizeWorkspacePipeline,
  publishWorkspaceVersion,
  restoreWorkspace,
  saveWorkspaceVersion,
  setWorkspaceOptimizationOptions,
  setLastOpenWorkspace,
} from './services/workspaceService';
import { useWorkspaceStudioStore } from './stores/workspaceStudioStore';

const DAY_LABELS = { L: 'Lunes', M: 'Martes', Mc: 'Miercoles', X: 'Jueves', V: 'Viernes' };
const ALL_DAYS = ['L', 'M', 'Mc', 'X', 'V'];
const DEFAULT_OPTIMIZATION_OPTIONS = {
  balance_load: true,
  load_balance_hard_spread_limit: 2,
  load_balance_target_band: 1,
  route_load_constraints: [],
};

const createEmptyRouteLoadConstraint = () => ({
  start_time: '07:30',
  end_time: '09:30',
  max_routes: 3,
  enabled: true,
  label: '',
});

const normalizeOptimizationOptions = (raw) => {
  const source = raw && typeof raw === 'object' ? raw : {};
  const toInt = (value, fallback) => {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  };
  const constraints = Array.isArray(source.route_load_constraints)
    ? source.route_load_constraints
      .filter((item) => item && typeof item === 'object')
      .map((item) => ({
        start_time: String(item.start_time || item.start || '').trim(),
        end_time: String(item.end_time || item.end || '').trim(),
        max_routes: Math.max(1, toInt(item.max_routes, 1)),
        enabled: item.enabled !== false,
        label: String(item.label || '').trim(),
      }))
      .filter((item) => item.start_time && item.end_time)
    : [];

  return {
    balance_load: source.balance_load !== false,
    load_balance_hard_spread_limit: Math.max(1, Math.min(12, toInt(source.load_balance_hard_spread_limit, 2))),
    load_balance_target_band: Math.max(0, Math.min(6, toInt(source.load_balance_target_band, 1))),
    route_load_constraints: constraints,
  };
};
const createEmptyScheduleByDay = () => (
  ALL_DAYS.reduce((acc, day) => {
    acc[day] = { schedule: [], stats: null };
    return acc;
  }, {})
);
const createEmptyPinnedBusesByDay = () => (
  ALL_DAYS.reduce((acc, day) => {
    acc[day] = [];
    return acc;
  }, {})
);

const getBusItems = (bus) => {
  if (Array.isArray(bus?.items)) return bus.items;
  if (Array.isArray(bus?.routes)) return bus.routes;
  return [];
};

const buildScheduleStats = (buses = []) => {
  const totalBuses = Array.isArray(buses) ? buses.length : 0;
  const allItems = (buses || []).flatMap((bus) => getBusItems(bus));
  const totalRoutes = allItems.length;
  const totalEntries = allItems.filter((item) => item?.type === 'entry').length;
  const totalExits = allItems.filter((item) => item?.type === 'exit').length;
  const routesPerBus = (buses || [])
    .map((bus) => getBusItems(bus).length)
    .filter((count) => Number.isFinite(count) && count > 0);
  const avgRoutesPerBus = totalBuses > 0
    ? Math.round((totalRoutes / totalBuses) * 10) / 10
    : 0;
  const sortedCounts = [...routesPerBus].sort((a, b) => a - b);
  const minRoutes = sortedCounts.length > 0 ? sortedCounts[0] : 0;
  const maxRoutes = sortedCounts.length > 0 ? sortedCounts[sortedCounts.length - 1] : 0;
  const spread = Math.max(0, maxRoutes - minRoutes);
  const mid = Math.floor(sortedCounts.length / 2);
  const medianRoutes = sortedCounts.length === 0
    ? 0
    : (
        sortedCounts.length % 2 === 0
          ? (sortedCounts[mid - 1] + sortedCounts[mid]) / 2
          : sortedCounts[mid]
      );
  const absDev = sortedCounts.length === 0
    ? 0
    : sortedCounts.reduce((sum, value) => sum + Math.abs(value - medianRoutes), 0);

  return {
    total_buses: totalBuses,
    total_entries: totalEntries,
    total_exits: totalExits,
    avg_routes_per_bus: avgRoutesPerBus,
    median_routes_per_bus: Number(medianRoutes.toFixed(2)),
    min_routes_per_bus: minRoutes,
    max_routes_per_bus: maxRoutes,
    load_spread_routes: spread,
    load_abs_dev_sum: Number(absDev.toFixed(2)),
    load_balanced: spread <= 2,
  };
};

const buildDayScheduleData = ({ buses = [], metadata = null, unassignedRoutes = [] } = {}) => ({
  schedule: Array.isArray(buses) ? buses : [],
  stats: buildScheduleStats(buses),
  metadata: metadata || {},
  unassigned_routes: Array.isArray(unassignedRoutes) ? unassignedRoutes : [],
});

const normalizeWorkspaceScheduleByDay = (scheduleByDay) => {
  const base = createEmptyScheduleByDay();
  if (!scheduleByDay || typeof scheduleByDay !== 'object') return base;

  for (const day of ALL_DAYS) {
    const dayPayload = scheduleByDay?.[day];
    if (!dayPayload) continue;
    const buses = Array.isArray(dayPayload?.schedule)
      ? dayPayload.schedule
      : (Array.isArray(dayPayload?.buses) ? dayPayload.buses : []);
    base[day] = {
      ...buildDayScheduleData({
        buses,
        metadata: dayPayload?.metadata || {},
        unassignedRoutes: dayPayload?.unassigned_routes || [],
      }),
      stats: dayPayload?.stats || buildScheduleStats(buses),
    };
  }
  return base;
};

const blobToBase64Payload = (blob) => (
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      if (typeof reader.result !== 'string') {
        reject(new Error('No se pudo convertir el archivo PDF'));
        return;
      }
      const commaIndex = reader.result.indexOf(',');
      resolve(commaIndex >= 0 ? reader.result.slice(commaIndex + 1) : reader.result);
    };
    reader.onerror = () => reject(new Error('Error leyendo el archivo PDF'));
    reader.readAsDataURL(blob);
  })
);

const savePdfWithDesktopDialog = async (blob, filename) => {
  const desktopApi = typeof window !== 'undefined' ? window.pywebview?.api : null;
  if (!desktopApi || typeof desktopApi.save_pdf_file !== 'function') {
    return { handled: false };
  }

  const base64Payload = await blobToBase64Payload(blob);
  const result = await desktopApi.save_pdf_file(base64Payload, filename);

  if (result?.cancelled) {
    return { handled: true, cancelled: true };
  }

  if (!result?.success) {
    throw new Error(result?.error || 'No se pudo guardar el PDF');
  }

  return { handled: true, path: result?.path || '' };
};

function TextInputModal({
  open = false,
  title = '',
  description = '',
  value = '',
  placeholder = '',
  confirmLabel = 'Aceptar',
  cancelLabel = 'Cancelar',
  allowEmpty = true,
  onChange,
  onCancel,
  onConfirm,
}) {
  if (!open) return null;

  const normalizedValue = String(value || '');
  const disabled = !allowEmpty && normalizedValue.trim().length === 0;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/80 backdrop-blur-[2px]" onClick={onCancel} />
      <div className="relative w-full max-w-md rounded-xl border border-[#253a4f] bg-[#0b141f] p-4 shadow-2xl">
        <h3 className="text-[15px] font-semibold text-white">{title}</h3>
        {description ? (
          <p className="mt-1 text-[12px] text-[#8ba3bd]">{description}</p>
        ) : null}
        <input
          type="text"
          autoFocus
          value={normalizedValue}
          placeholder={placeholder}
          onChange={(event) => onChange?.(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              onCancel?.();
              return;
            }
            if (event.key === 'Enter' && !disabled) {
              event.preventDefault();
              onConfirm?.();
            }
          }}
          className="mt-3 w-full rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[13px] text-white outline-none transition focus:border-[#4ecbff]/70"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-[#2a4057] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9eb2c8] transition hover:bg-white/5"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={disabled}
            className="rounded-md bg-[#2ab5e8] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#03131f] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function LoadOptionsModal({
  open = false,
  title = 'Restricciones de carga',
  initialValue = DEFAULT_OPTIMIZATION_OPTIONS,
  onCancel,
  onSave,
}) {
  const [value, setValue] = useState(normalizeOptimizationOptions(initialValue));

  useEffect(() => {
    if (!open) return;
    setValue(normalizeOptimizationOptions(initialValue));
  }, [open, initialValue]);

  if (!open) return null;

  const updateConstraint = (index, patch) => {
    setValue((prev) => {
      const next = normalizeOptimizationOptions(prev);
      const rows = [...next.route_load_constraints];
      rows[index] = { ...rows[index], ...patch };
      return { ...next, route_load_constraints: rows };
    });
  };

  const removeConstraint = (index) => {
    setValue((prev) => {
      const next = normalizeOptimizationOptions(prev);
      return {
        ...next,
        route_load_constraints: next.route_load_constraints.filter((_, idx) => idx !== index),
      };
    });
  };

  const addConstraint = () => {
    setValue((prev) => {
      const next = normalizeOptimizationOptions(prev);
      return {
        ...next,
        route_load_constraints: [...next.route_load_constraints, createEmptyRouteLoadConstraint()],
      };
    });
  };

  return (
    <div className="fixed inset-0 z-[1200] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/85 backdrop-blur-[2px]" onClick={onCancel} />
      <div className="relative w-full max-w-2xl rounded-xl border border-[#2a4057] bg-[#0b141f] p-4 shadow-2xl">
        <h3 className="text-[16px] font-semibold text-white">{title}</h3>
        <p className="mt-1 text-[12px] text-[#8ba3bd]">
          Configura el reparto de rutas por bus. Se mantiene siempre el objetivo de minimo buses factibles.
        </p>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 flex items-center gap-2 text-[12px] text-slate-200">
            <input
              type="checkbox"
              checked={Boolean(value.balance_load)}
              onChange={(event) => setValue((prev) => ({ ...normalizeOptimizationOptions(prev), balance_load: event.target.checked }))}
            />
            Balancear carga
          </label>
          <label className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
            Spread max
            <input
              type="number"
              min={1}
              max={12}
              value={value.load_balance_hard_spread_limit}
              onChange={(event) => setValue((prev) => ({
                ...normalizeOptimizationOptions(prev),
                load_balance_hard_spread_limit: Number.parseInt(event.target.value || '2', 10),
              }))}
              className="mt-1 w-full rounded border border-[#35506a] bg-[#09101d] px-2 py-1 text-[12px] text-white"
            />
          </label>
          <label className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
            Banda mediana (+/-)
            <input
              type="number"
              min={0}
              max={6}
              value={value.load_balance_target_band}
              onChange={(event) => setValue((prev) => ({
                ...normalizeOptimizationOptions(prev),
                load_balance_target_band: Number.parseInt(event.target.value || '1', 10),
              }))}
              className="mt-1 w-full rounded border border-[#35506a] bg-[#09101d] px-2 py-1 text-[12px] text-white"
            />
          </label>
        </div>

        <div className="mt-4 rounded-lg border border-[#2a4057] bg-[#0a1324] p-3">
          <div className="flex items-center justify-between">
            <p className="text-[11px] uppercase tracking-[0.1em] text-cyan-300">Restricciones horarias</p>
            <button
              type="button"
              onClick={addConstraint}
              className="rounded border border-cyan-500/40 px-2 py-1 text-[10px] uppercase tracking-[0.08em] text-cyan-200 hover:bg-cyan-500/10"
            >
              + Anadir
            </button>
          </div>
          <div className="mt-2 max-h-[240px] overflow-auto space-y-2">
            {value.route_load_constraints.length === 0 && (
              <p className="text-[12px] text-slate-400">
                Sin restricciones horarias. Puedes usar por ejemplo 07:30-09:30 max 3 rutas.
              </p>
            )}
            {value.route_load_constraints.map((rule, index) => (
              <div key={`${rule.start_time}-${rule.end_time}-${index}`} className="grid grid-cols-12 gap-2 items-center rounded border border-[#35506a] bg-[#09101d] px-2 py-2">
                <label className="col-span-1 flex justify-center">
                  <input
                    type="checkbox"
                    checked={rule.enabled !== false}
                    onChange={(event) => updateConstraint(index, { enabled: event.target.checked })}
                  />
                </label>
                <input
                  type="time"
                  value={rule.start_time}
                  onChange={(event) => updateConstraint(index, { start_time: event.target.value })}
                  className="col-span-3 rounded border border-[#2f4861] bg-[#08101c] px-2 py-1 text-[12px] text-white"
                />
                <input
                  type="time"
                  value={rule.end_time}
                  onChange={(event) => updateConstraint(index, { end_time: event.target.value })}
                  className="col-span-3 rounded border border-[#2f4861] bg-[#08101c] px-2 py-1 text-[12px] text-white"
                />
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={rule.max_routes}
                  onChange={(event) => updateConstraint(index, { max_routes: Number.parseInt(event.target.value || '1', 10) })}
                  className="col-span-2 rounded border border-[#2f4861] bg-[#08101c] px-2 py-1 text-[12px] text-white"
                />
                <input
                  type="text"
                  value={rule.label || ''}
                  placeholder="Etiqueta"
                  onChange={(event) => updateConstraint(index, { label: event.target.value })}
                  className="col-span-2 rounded border border-[#2f4861] bg-[#08101c] px-2 py-1 text-[12px] text-white"
                />
                <button
                  type="button"
                  onClick={() => removeConstraint(index)}
                  className="col-span-1 rounded border border-rose-500/45 px-1 py-1 text-[10px] text-rose-200 hover:bg-rose-500/15"
                >
                  X
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-[#2a4057] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9eb2c8] transition hover:bg-white/5"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => onSave?.(normalizeOptimizationOptions(value))}
            className="rounded-md bg-[#2ab5e8] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#03131f] transition hover:brightness-110"
          >
            Guardar restricciones
          </button>
        </div>
      </div>
    </div>
  );
}

function PreOptimizeRestrictionsModal({
  open = false,
  workspaceName = '',
  onCancel,
  onConfigureRestrictions,
  onContinueWithoutChanges,
}) {
  if (!open) return null;

  const label = String(workspaceName || '').trim() || 'esta optimizacion';

  return (
    <div className="fixed inset-0 z-[1250] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/85 backdrop-blur-[2px]" onClick={onCancel} />
      <div className="relative w-full max-w-md rounded-xl border border-[#2a4057] bg-[#0b141f] p-4 shadow-2xl">
        <h3 className="text-[16px] font-semibold text-white">Antes de optimizar</h3>
        <p className="mt-2 text-[12px] text-[#8ba3bd]">
          Quieres anadir o ajustar restricciones para <span className="text-white font-semibold">{label}</span> antes de ejecutar el pipeline?
        </p>
        <p className="mt-1 text-[11px] text-slate-400">
          Si guardas restricciones ahora, esta corrida se ejecuta directamente con esas reglas.
        </p>

        <div className="mt-4 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-[#2a4057] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9eb2c8] transition hover:bg-white/5"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onContinueWithoutChanges}
            className="rounded-md border border-[#2f4d65] bg-[#0b1a2a] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-cyan-200 transition hover:bg-[#10243a]"
          >
            Optimizar ya
          </button>
          <button
            type="button"
            onClick={onConfigureRestrictions}
            className="rounded-md bg-[#2ab5e8] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#03131f] transition hover:brightness-110"
          >
            Anadir restricciones
          </button>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [routes, setRoutes] = useState([]);
  const [parseReport, setParseReport] = useState(null);
  const [scheduleByDay, setScheduleByDay] = useState(createEmptyScheduleByDay());
  const [previousScheduleByDay, setPreviousScheduleByDay] = useState(null);
  const [validationReport, setValidationReport] = useState(null);
  const [activeDay, setActiveDay] = useState('L');
  const [optimizing, setOptimizing] = useState(false);
  const [showComparison, setShowComparison] = useState(false);
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);

  const [activeTab, setActiveTab] = useState('upload');
  const [viewMode, setViewMode] = useState('dashboard'); // 'dashboard' | 'studio'
  const [workspaceMode, setWorkspaceMode] = useState('create'); // 'create' | 'edit' | 'optimize'
  const [selectedBusId, setSelectedBusId] = useState(null);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [pinnedBusesByDay, setPinnedBusesByDay] = useState(createEmptyPinnedBusesByDay());
  const [ingestionPanelOpen, setIngestionPanelOpen] = useState(false);
  const [createFlowMode, setCreateFlowMode] = useState(false);
  const [optimizationOptionsByWorkspace, setOptimizationOptionsByWorkspace] = useState({});
  const [activeOptimizationOptions, setActiveOptimizationOptions] = useState(
    normalizeOptimizationOptions(DEFAULT_OPTIMIZATION_OPTIONS)
  );
  const [loadOptionsModal, setLoadOptionsModal] = useState({
    open: false,
    workspaceId: null,
    title: 'Restricciones de carga',
  });
  const [preOptimizeModal, setPreOptimizeModal] = useState({
    open: false,
    workspaceName: '',
    request: null,
  });
  const [pendingOptimizationRequest, setPendingOptimizationRequest] = useState(null);

  const [pipelineJobId, setPipelineJobId] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState('idle');
  const [pipelineEvents, setPipelineEvents] = useState([]);
  const [pipelineMetrics, setPipelineMetrics] = useState(null);
  const [textInputModal, setTextInputModal] = useState({
    open: false,
    title: '',
    description: '',
    placeholder: '',
    confirmLabel: 'Aceptar',
    cancelLabel: 'Cancelar',
    allowEmpty: true,
    value: '',
  });
  const textInputResolverRef = useRef(null);

  const studioSetWorkspaceId = useWorkspaceStudioStore((state) => state.setActiveWorkspaceId);
  const studioSetRoutes = useWorkspaceStudioStore((state) => state.setRoutes);
  const studioSetScheduleByDay = useWorkspaceStudioStore((state) => state.setScheduleByDay);
  const studioSetActiveDay = useWorkspaceStudioStore((state) => state.setActiveDay);
  const studioSetSelectedBusId = useWorkspaceStudioStore((state) => state.setSelectedBusId);
  const studioSetSelectedRouteId = useWorkspaceStudioStore((state) => state.setSelectedRouteId);
  const studioSetDirty = useWorkspaceStudioStore((state) => state.setDirty);
  const studioMarkSaved = useWorkspaceStudioStore((state) => state.markSaved);
  const studioReset = useWorkspaceStudioStore((state) => state.resetStudio);

  const closeTextInputModal = useCallback((result = { confirmed: false, value: '' }) => {
    setTextInputModal((prev) => ({ ...prev, open: false }));
    const resolver = textInputResolverRef.current;
    textInputResolverRef.current = null;
    if (typeof resolver === 'function') {
      resolver(result);
    }
  }, []);

  const openTextInputModal = useCallback((config = {}) => (
    new Promise((resolve) => {
      textInputResolverRef.current = resolve;
      setTextInputModal({
        open: true,
        title: config.title || 'Introduce un valor',
        description: config.description || '',
        placeholder: config.placeholder || '',
        confirmLabel: config.confirmLabel || 'Aceptar',
        cancelLabel: config.cancelLabel || 'Cancelar',
        allowEmpty: Boolean(config.allowEmpty ?? true),
        value: String(config.defaultValue || ''),
      });
    })
  ), []);

  useEffect(() => () => {
    if (typeof textInputResolverRef.current === 'function') {
      textInputResolverRef.current({ confirmed: false, value: '' });
      textInputResolverRef.current = null;
    }
  }, []);

  const fetchAndStoreWorkspaceOptions = useCallback(async (workspaceId) => {
    if (!workspaceId) return normalizeOptimizationOptions(DEFAULT_OPTIMIZATION_OPTIONS);
    try {
      const options = await getWorkspaceOptimizationOptions(workspaceId);
      const normalized = normalizeOptimizationOptions(options);
      setOptimizationOptionsByWorkspace((prev) => ({
        ...prev,
        [workspaceId]: normalized,
      }));
      return normalized;
    } catch {
      const fallback = normalizeOptimizationOptions(DEFAULT_OPTIMIZATION_OPTIONS);
      setOptimizationOptionsByWorkspace((prev) => ({
        ...prev,
        [workspaceId]: fallback,
      }));
      return fallback;
    }
  }, []);

  const openLoadOptionsModal = useCallback(async ({ workspaceId = null, workspaceName = '' } = {}) => {
    const normalizedName = String(workspaceName || '').trim();
    const title = workspaceId
      ? `Restricciones - ${normalizedName || 'Optimizacion'}`
      : 'Restricciones por defecto';
    if (workspaceId) {
      const loaded = await fetchAndStoreWorkspaceOptions(workspaceId);
      setActiveOptimizationOptions(loaded);
    }
    setLoadOptionsModal({
      open: true,
      workspaceId: workspaceId || null,
      title,
    });
  }, [fetchAndStoreWorkspaceOptions]);

  const closeLoadOptionsModal = useCallback(() => {
    setLoadOptionsModal({ open: false, workspaceId: null, title: 'Restricciones de carga' });
    setPendingOptimizationRequest(null);
  }, []);

  const handleSaveLoadOptions = useCallback(async (nextOptionsRaw) => {
    const nextOptions = normalizeOptimizationOptions(nextOptionsRaw);
    const workspaceId = loadOptionsModal.workspaceId;
    if (workspaceId) {
      const persisted = await setWorkspaceOptimizationOptions(workspaceId, nextOptions);
      const normalizedPersisted = normalizeOptimizationOptions(persisted);
      setOptimizationOptionsByWorkspace((prev) => ({
        ...prev,
        [workspaceId]: normalizedPersisted,
      }));
      if (String(activeWorkspaceId || '') === String(workspaceId)) {
        setActiveOptimizationOptions(normalizedPersisted);
      }
      notifications.success('Restricciones guardadas', 'Se aplicaran en la siguiente optimizacion');
    } else {
      setActiveOptimizationOptions(nextOptions);
      notifications.success('Restricciones por defecto', 'Configuracion lista para la siguiente corrida');
    }
    closeLoadOptionsModal();
    if (pendingOptimizationRequest) {
      const request = pendingOptimizationRequest;
      setPendingOptimizationRequest(null);
      await startAutoPipeline(
        request.routesInput,
        request.parseReportInput,
        request.workspaceIdInput
      );
    }
  }, [activeWorkspaceId, closeLoadOptionsModal, loadOptionsModal.workspaceId, pendingOptimizationRequest]);

  const refreshWorkspaces = useCallback(async () => {
    const data = await listWorkspaces().catch(() => ({ items: [] }));
    const items = Array.isArray(data?.items) ? data.items : [];
    setWorkspaces(items);
    return items;
  }, []);

  const hydrateWorkspaceDetail = useCallback((detail) => {
    const workingVersion = detail?.working_version || detail?.published_version || null;
    const routePayload = Array.isArray(workingVersion?.routes_payload)
      ? workingVersion.routes_payload
      : (Array.isArray(workingVersion?.routes_payload?.routes) ? workingVersion.routes_payload.routes : []);
    const normalizedSchedule = normalizeWorkspaceScheduleByDay(workingVersion?.schedule_by_day || {});
    const preferredDay = ALL_DAYS.find((day) => (normalizedSchedule?.[day]?.schedule?.length || 0) > 0) || 'L';

    setRoutes(Array.isArray(routePayload) ? routePayload : []);
    setParseReport(workingVersion?.parse_report || null);
    setScheduleByDay(normalizedSchedule);
    setValidationReport(workingVersion?.validation_report || null);
    setActiveDay(preferredDay);
    setWorkspaceMode(detail?.status === 'active' ? 'edit' : 'optimize');
  }, []);

  const openWorkspaceById = useCallback(async (workspaceId, { switchToStudio = true } = {}) => {
    if (!workspaceId) return null;
    const detail = await getWorkspace(workspaceId);
    const options = await fetchAndStoreWorkspaceOptions(workspaceId);
    setActiveWorkspaceId(workspaceId);
    setActiveOptimizationOptions(options);
    studioSetWorkspaceId(workspaceId);
    hydrateWorkspaceDetail(detail);
    setLastOpenWorkspace(workspaceId).catch(() => {});
    if (switchToStudio) {
      setViewMode('studio');
    }
    setPinnedBusesByDay(createEmptyPinnedBusesByDay());
    setIngestionPanelOpen(false);
    setCreateFlowMode(false);
    studioMarkSaved();
    return detail;
  }, [fetchAndStoreWorkspaceOptions, hydrateWorkspaceDetail, studioMarkSaved, studioSetWorkspaceId]);

  const createWorkspaceAndOpen = useCallback(async (seed = {}) => {
    const suggestedName = seed?.name || `Optimizacion ${new Date().toLocaleDateString()}`;
    const promptResult = await openTextInputModal({
      title: 'Nueva optimizacion',
      description: 'Introduce un nombre para identificar esta optimizacion',
      placeholder: 'Ej: Vigo - Semana 12',
      confirmLabel: 'Crear',
      cancelLabel: 'Cancelar',
      allowEmpty: true,
      defaultValue: suggestedName,
    });
    if (!promptResult?.confirmed) {
      return { id: null, cancelled: true };
    }
    const normalizedName = String(promptResult?.value || '').trim() || suggestedName;
    const created = await createWorkspace({
      name: normalizedName,
      city_label: seed?.city_label || null,
      routes_payload: seed?.routes_payload || null,
      parse_report: seed?.parse_report || null,
      schedule_by_day: seed?.schedule_by_day || null,
      summary_metrics: seed?.summary_metrics || null,
    });
    await refreshWorkspaces();
    await openWorkspaceById(created?.id, { switchToStudio: true });
    return created;
  }, [openTextInputModal, openWorkspaceById, refreshWorkspaces]);

  const startNewWorkspaceFlow = useCallback(() => {
    setViewMode('dashboard');
    setIngestionPanelOpen(true);
    setCreateFlowMode(true);
    setActiveTab('upload');
    notifications.info('Nueva optimizacion', 'Sube excels para crear una optimizacion nueva');
  }, []);

  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      await migrateLegacyWorkspaces().catch(() => null);
      const [items, preferences] = await Promise.all([
        refreshWorkspaces(),
        getWorkspacePreferences().catch(() => ({})),
      ]);
      if (cancelled) return;
      const preferred = String(preferences?.last_open_workspace_id || '').trim();
      const preferredExists = preferred && items.some((item) => String(item.id) === preferred);
      const targetId = preferredExists ? preferred : (items[0]?.id || null);
      if (targetId) {
        await openWorkspaceById(targetId, { switchToStudio: false });
      }
    };
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [openWorkspaceById, refreshWorkspaces]);

  // Current day's data
  const currentDayData = scheduleByDay?.[activeDay] || null;
  const schedule = currentDayData?.schedule || [];
  const optimizationStats = currentDayData?.stats || null;

  useEffect(() => {
    studioSetWorkspaceId(activeWorkspaceId);
  }, [activeWorkspaceId, studioSetWorkspaceId]);

  useEffect(() => {
    studioSetRoutes(routes);
  }, [routes, studioSetRoutes]);

  useEffect(() => {
    studioSetScheduleByDay(scheduleByDay);
  }, [scheduleByDay, studioSetScheduleByDay]);

  useEffect(() => {
    studioSetActiveDay(activeDay);
  }, [activeDay, studioSetActiveDay]);

  useEffect(() => {
    studioSetSelectedBusId(selectedBusId);
  }, [selectedBusId, studioSetSelectedBusId]);

  useEffect(() => {
    studioSetSelectedRouteId(selectedRouteId);
  }, [selectedRouteId, studioSetSelectedRouteId]);

  const calculateStats = () => {
    if (!routes.length && !schedule.length) return null;

    let efficiency = 0;
    if (schedule.length > 0) {
      const totalItems = schedule.reduce((sum, bus) => sum + (bus.items?.length || 0), 0);
      const avg = totalItems / schedule.length;
      efficiency = Math.min(Math.round((avg / 7) * 100), 100);
    }

    return {
      routes: routes.length,
      buses: schedule.length,
      efficiency,
      ...optimizationStats,
    };
  };

  const applyPipelineResult = useCallback((pipelineResult) => {
    const scheduleResult = pipelineResult?.schedule_by_day || null;
    if (!scheduleResult) {
      throw new Error('El resultado del pipeline no contiene schedule_by_day');
    }
    const normalizedResult = normalizeWorkspaceScheduleByDay(scheduleResult);

    if (scheduleByDay) {
      setPreviousScheduleByDay(scheduleByDay);
    }

    setScheduleByDay(normalizedResult);
    setValidationReport(pipelineResult?.validation_report || null);
    setShowComparison(true);
    setViewMode('studio');
    setWorkspaceMode('optimize');
    studioSetDirty(true);

    let maxBuses = 0;
    let maxDay = 'L';
    for (const day of ALL_DAYS) {
      const dayBuses = normalizedResult[day]?.stats?.total_buses || 0;
      if (dayBuses > maxBuses) {
        maxBuses = dayBuses;
        maxDay = day;
      }
    }
    setActiveDay(maxDay);
  }, [scheduleByDay, studioSetDirty]);

  const startAutoPipeline = async (
    routesInput = routes,
    parseReportInput = parseReport,
    workspaceIdInput = activeWorkspaceId,
  ) => {
    if (!routesInput || routesInput.length === 0) {
      notifications.warning('No hay datos', 'Sube archivos Excel primero');
      return { status: 'empty' };
    }

    setOptimizing(true);
    setPipelineStatus('starting');
    setPipelineJobId(null);
    setPipelineEvents([]);
    setPipelineMetrics(null);
    setViewMode('studio');
    setWorkspaceMode('optimize');

    const loadingToast = notifications.loading('Iniciando pipeline automatico...');
    const resolvedOptions = normalizeOptimizationOptions(
      (workspaceIdInput && optimizationOptionsByWorkspace?.[workspaceIdInput])
        || activeOptimizationOptions
        || DEFAULT_OPTIMIZATION_OPTIONS
    );

    try {
      let data = null;
      if (workspaceIdInput) {
        data = await optimizeWorkspacePipeline(workspaceIdInput, {
          routes: routesInput,
          parse_report: parseReportInput || null,
          config: {
            auto_start: true,
            objective: 'min_buses_viability',
            max_duration_sec: 300,
            max_iterations: 2,
            invalid_rows_dropped: Number(parseReportInput?.rows_dropped_invalid || 0),
            balance_load: Boolean(resolvedOptions.balance_load),
            load_balance_hard_spread_limit: Number(resolvedOptions.load_balance_hard_spread_limit || 2),
            load_balance_target_band: Number(resolvedOptions.load_balance_target_band || 1),
            route_load_constraints: Array.isArray(resolvedOptions.route_load_constraints)
              ? resolvedOptions.route_load_constraints
              : [],
          },
        });
      } else {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/optimize-pipeline-by-day-async`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            routes: routesInput,
            config: {
              auto_start: true,
              objective: 'min_buses_viability',
              max_duration_sec: 300,
              max_iterations: 2,
              invalid_rows_dropped: Number(parseReportInput?.rows_dropped_invalid || 0),
              balance_load: Boolean(resolvedOptions.balance_load),
              load_balance_hard_spread_limit: Number(resolvedOptions.load_balance_hard_spread_limit || 2),
              load_balance_target_band: Number(resolvedOptions.load_balance_target_band || 1),
              route_load_constraints: Array.isArray(resolvedOptions.route_load_constraints)
                ? resolvedOptions.route_load_constraints
                : [],
            },
          }),
        });
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || `Error del servidor: ${response.status}`);
        }
        data = await response.json();
      }
      notifications.dismiss(loadingToast);

      if (data.status === 'completed' && data.result) {
        applyPipelineResult(data.result);
        setPipelineStatus('completed');
        setOptimizing(false);
        notifications.success('Pipeline completado', 'Resultado final disponible en Workspace');
        refreshWorkspaces().catch(() => {});
        return { status: 'completed', jobId: null };
      } else {
        setPipelineJobId(data.job_id || null);
        setPipelineStatus(data.status || 'queued');
        notifications.info('Pipeline en ejecucion', 'Mostrando progreso en tiempo real');
        return { status: data.status || 'queued', jobId: data.job_id || null };
      }
    } catch (error) {
      console.error('Error optimizing:', error);
      notifications.dismiss(loadingToast);
      notifications.error(
        'Error al ejecutar pipeline',
        error.message || 'Asegurate de que el backend este funcionando.'
      );
      setOptimizing(false);
      setPipelineStatus('error');
      return { status: 'error', error };
    }
  };

  const openPreOptimizeModal = useCallback((request) => {
    if (!request?.routesInput || request.routesInput.length === 0) {
      notifications.warning('No hay datos', 'Sube archivos Excel primero');
      return;
    }
    setPreOptimizeModal({
      open: true,
      workspaceName: String(request.workspaceName || '').trim(),
      request,
    });
  }, []);

  const closePreOptimizeModal = useCallback(() => {
    setPreOptimizeModal({ open: false, workspaceName: '', request: null });
  }, []);

  const handleUploadSuccess = async (payload) => {
    const uploadedRoutes = Array.isArray(payload) ? payload : (payload?.routes || []);
    const uploadReport = Array.isArray(payload) ? null : (payload?.parse_report || null);

    setRoutes(uploadedRoutes);
    setParseReport(uploadReport);
    setScheduleByDay(createEmptyScheduleByDay());
    setValidationReport(null);
    setSelectedBusId(null);
    setSelectedRouteId(null);
    studioSetDirty(true);

    const droppedRows = Number(uploadReport?.rows_dropped_invalid || 0);
    const rowsTotal = Number(uploadReport?.rows_total || 0);

    notifications.success(
      'Datos cargados correctamente',
      `${uploadedRoutes.length} rutas importadas`
    );

    if (droppedRows > 0) {
      const shouldContinue = window.confirm(
        `Calidad de datos detecto ${droppedRows} filas invalidas descartadas de ${rowsTotal} filas.\n\n¿Quieres continuar con estos datos para optimizar?`
      );
      if (!shouldContinue) {
        notifications.info(
          'Carga pausada',
          'Revisa el panel de calidad de datos antes de ejecutar la optimizacion'
        );
        return;
      }
    }

    let workspaceId = activeWorkspaceId;
    if (!workspaceId || createFlowMode) {
      try {
        const created = await createWorkspaceAndOpen({
          name: `Optimizacion ${new Date().toLocaleDateString()}`,
          routes_payload: uploadedRoutes,
          parse_report: uploadReport,
          schedule_by_day: createEmptyScheduleByDay(),
        });
        workspaceId = created?.id || null;
        if (created?.cancelled) {
          notifications.info(
            'Nombre omitido',
            'Seguimos sin guardado inicial para no bloquear la carga'
          );
        }
      } catch (_error) {
        workspaceId = null;
        notifications.warning(
          'No se pudo crear la optimizacion',
          'Continuamos la carga sin guardado inicial'
        );
      }
    } else {
      await saveWorkspaceVersion(workspaceId, {
        save_kind: 'save',
        checkpoint_name: 'upload-routes',
        routes_payload: uploadedRoutes,
        parse_report: uploadReport,
      }).catch(() => null);
    }

    if (workspaceId) {
      const optionsToPersist = normalizeOptimizationOptions(
        optimizationOptionsByWorkspace?.[workspaceId]
        || activeOptimizationOptions
        || DEFAULT_OPTIMIZATION_OPTIONS
      );
      await setWorkspaceOptimizationOptions(workspaceId, optionsToPersist).catch(() => null);
      setOptimizationOptionsByWorkspace((prev) => ({ ...prev, [workspaceId]: optionsToPersist }));
      setActiveOptimizationOptions(optionsToPersist);
      await refreshWorkspaces();
    }

    setCreateFlowMode(false);
    setIngestionPanelOpen(true);
    notifications.info(
      'Datos listos para optimizar',
      'Pulsa "Ejecutar Pipeline". Antes te preguntaremos si quieres añadir restricciones.'
    );
  };

  const handleOptimize = async () => {
    const workspaceName = workspaces.find((ws) => String(ws.id) === String(activeWorkspaceId))?.name || '';
    openPreOptimizeModal({
      routesInput: routes,
      parseReportInput: parseReport,
      workspaceIdInput: activeWorkspaceId,
      workspaceName,
    });
  };

  const handleReset = () => {
    if (confirm('Borrar todos los datos?')) {
      setRoutes([]);
      setParseReport(null);
      setScheduleByDay(createEmptyScheduleByDay());
      setPreviousScheduleByDay(null);
      setValidationReport(null);
      setShowComparison(false);
      setSelectedBusId(null);
      setSelectedRouteId(null);
      setPipelineJobId(null);
      setPipelineStatus('idle');
      setPipelineEvents([]);
      setPipelineMetrics(null);
      setViewMode('dashboard');
      setWorkspaceMode('create');
      setIngestionPanelOpen(false);
      setCreateFlowMode(false);
      studioReset();
      clearGeometryCache();
      notifications.info('Datos borrados', 'Puedes empezar de nuevo');
    }
  };

  const normalizeScheduleForExport = useCallback((scheduleInput = []) => {
    const safeSchedule = Array.isArray(scheduleInput) ? scheduleInput : [];
    return safeSchedule.map((bus, busIndex) => {
      const busId = bus?.bus_id || bus?.id || `B${String(busIndex + 1).padStart(3, '0')}`;
      const rawItems = Array.isArray(bus?.items)
        ? bus.items
        : (Array.isArray(bus?.routes) ? bus.routes : []);

      const normalizedItems = rawItems.map((item, itemIndex) => {
        const routeId = item?.route_id || item?.id || item?.code || `R${itemIndex + 1}`;
        const routeCode = item?.route_code || item?.code || routeId;
        const rawPositioning = Number(
          item?.positioning_minutes ??
          item?.positioningMinutes ??
          item?.deadhead_minutes ??
          item?.deadheadMinutes ??
          item?.deadhead ??
          0
        );
        const positioningMinutes = Number.isFinite(rawPositioning)
          ? Math.max(0, Math.round(rawPositioning))
          : 0;

        return {
          ...item,
          route_id: routeId,
          route_code: routeCode,
          start_time: item?.start_time || item?.startTime || '00:00',
          end_time: item?.end_time || item?.endTime || '00:00',
          origin: item?.origin || '',
          destination: item?.destination || '',
          school_name: item?.school_name || item?.school || null,
          type: item?.type || 'entry',
          stops: Array.isArray(item?.stops) ? item.stops : [],
          start_location: item?.start_location || item?.start_loc || item?.startLocation || item?.rawRoute?.start_location || null,
          end_location: item?.end_location || item?.end_loc || item?.endLocation || item?.rawRoute?.end_location || null,
          order: Number.isFinite(Number(item?.order)) ? Number(item.order) : itemIndex,
          positioning_minutes: positioningMinutes,
          deadhead_minutes: positioningMinutes,
        };
      });

      return {
        ...bus,
        bus_id: busId,
        items: normalizedItems,
      };
    });
  }, []);

  const handleExport = useCallback(async ({ schedule: scheduleOverride = null, day: dayOverride = null } = {}) => {
    const exportSchedule = Array.isArray(scheduleOverride) ? scheduleOverride : schedule;
    if (!Array.isArray(exportSchedule) || exportSchedule.length === 0) {
      notifications.warning('No hay resultados', 'Optimiza las rutas primero');
      return;
    }

    const loadingToast = notifications.loading('Generando PDF...');

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const dayCode = dayOverride || activeDay;
      const dayName = DAY_LABELS[dayCode] || dayCode;
      const routeCapacityById = buildRouteCapacityMap(routes);
      const normalizedSchedule = normalizeScheduleForExport(exportSchedule);
      const scheduleForPdf = normalizedSchedule.map((bus) => ({
        ...bus,
        items: (bus.items || []).map((item) => ({
          ...item,
          capacity_needed: getItemCapacityNeeded(item, routeCapacityById),
        })),
      }));
      const response = await fetch(`${apiUrl}/export_pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schedule: scheduleForPdf, day_name: dayName }),
      });

      if (!response.ok) {
        throw new Error(`Error del servidor: ${response.status}`);
      }

      const blob = await response.blob();
      const filename = `tutti_schedule_${dayName.toLowerCase()}.pdf`;
      const desktopSave = await savePdfWithDesktopDialog(blob, filename);

      if (!desktopSave.handled) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }

      notifications.dismiss(loadingToast);
      if (desktopSave.cancelled) {
        notifications.info('Exportacion cancelada', 'No se guardo ningun archivo');
      } else if (desktopSave.path) {
        notifications.success('PDF guardado', desktopSave.path);
      } else {
        notifications.success('PDF descargado', `Horario del ${dayName}`);
      }
    } catch (error) {
      console.error('Error exporting PDF:', error);
      notifications.dismiss(loadingToast);
      notifications.error('Error al exportar PDF', error.message);
    }
  }, [activeDay, normalizeScheduleForExport, routes, schedule]);

  const handleDayChange = useCallback((day) => {
    setActiveDay(day);
    setSelectedBusId(null);
    setSelectedRouteId(null);
  }, []);

  const handleBusSelect = useCallback((busId) => {
    setSelectedBusId(busId);
    setSelectedRouteId(null);
  }, []);

  const handleTogglePinBus = useCallback((busId) => {
    const normalized = String(busId || '').trim();
    if (!normalized) return;
    setPinnedBusesByDay((prev) => {
      const dayPins = Array.isArray(prev?.[activeDay]) ? prev[activeDay] : [];
      const alreadyPinned = dayPins.includes(normalized);
      const nextDayPins = alreadyPinned
        ? dayPins.filter((id) => id !== normalized)
        : [...dayPins, normalized];
      return {
        ...prev,
        [activeDay]: nextDayPins,
      };
    });
  }, [activeDay]);

  const handleRouteSelect = useCallback((routeId) => {
    setSelectedRouteId(routeId);
  }, []);

  const handleSaveManualSchedule = async (scheduleData, intent = 'save') => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const payload = {
      day: scheduleData?.day,
      buses: scheduleData?.buses || [],
      unassigned_routes: scheduleData?.unassigned_routes || [],
      metadata: {
        mode: scheduleData?.mode || 'draft',
        ...(scheduleData?.stats || {}),
      },
    };

    const endpoints = [
      `${apiUrl}/api/schedules/update`,
      `${apiUrl}/api/schedules/manual`,
    ];

    let lastError = null;

    for (const url of endpoints) {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        const message = error?.detail?.message || error?.detail || error?.message || `Error ${response.status}`;
        if (response.status === 404 || response.status === 405) {
          lastError = new Error(message);
          continue;
        }
        throw new Error(message);
      }

      const data = await response.json();
      if (data?.success === false) {
        const conflictCount = Array.isArray(data?.conflicts) ? data.conflicts.length : 0;
        const errorCount = Array.isArray(data?.errors) ? data.errors.length : 0;
        throw new Error(`Horario invalido (${conflictCount} conflictos, ${errorCount} errores).`);
      }

      const mergedScheduleByDay = {
        ...(scheduleByDay && typeof scheduleByDay === 'object' ? scheduleByDay : createEmptyScheduleByDay()),
        [payload.day]: buildDayScheduleData({
          buses: payload.buses,
          metadata: payload.metadata,
          unassignedRoutes: payload.unassigned_routes,
        }),
      };

      setScheduleByDay(mergedScheduleByDay);
      setActiveDay(payload.day || 'L');
      const requestedMode = payload?.metadata?.mode;
      const nextMode = requestedMode === 'optimize' ? 'optimize' : 'edit';
      setWorkspaceMode(nextMode);
      studioSetDirty(true);

      if (activeWorkspaceId) {
        const snapshotPayload = {
          checkpoint_name: scheduleData?.checkpoint_name || (
            intent === 'publish'
              ? `publish-${new Date().toISOString().slice(0, 19)}`
              : `save-${payload.day || 'L'}-${new Date().toISOString().slice(0, 19)}`
          ),
          routes_payload: routes,
          schedule_by_day: mergedScheduleByDay,
          parse_report: parseReport || null,
          validation_report: validationReport || null,
          summary_metrics: mergedScheduleByDay?.[payload.day]?.stats || {},
        };
        if (intent === 'publish') {
          await publishWorkspaceVersion(activeWorkspaceId, snapshotPayload);
          notifications.success('Version publicada', 'Optimizacion activa en Control Hub');
        } else {
          await saveWorkspaceVersion(activeWorkspaceId, snapshotPayload);
          notifications.success('Version guardada', 'Checkpoint guardado');
        }
        await refreshWorkspaces();
        studioMarkSaved();
      }
      return data;
    }

    throw lastError || new Error('No se pudo guardar el horario manual');
  };

  const handlePipelineProgress = useCallback((progressState) => {
    setPipelineStatus('running');

    setPipelineMetrics((prev) => {
      const next = progressState.metrics || null;
      if (prev === next) return prev;
      try {
        const prevKey = prev ? JSON.stringify(prev) : '';
        const nextKey = next ? JSON.stringify(next) : '';
        return prevKey === nextKey ? prev : next;
      } catch {
        return next;
      }
    });

    setPipelineEvents((prev) => {
      const nextEvent = {
        phase: progressState.phase,
        stage: progressState.stage,
        progress: progressState.progress,
        message: progressState.message,
        day: progressState.day,
        iteration: progressState.iteration,
        stream: progressState.stream,
        engine: progressState.engine,
        optimizerPhase: progressState.optimizerPhase,
        localProgress: progressState.localProgress,
      };

      const last = prev[prev.length - 1];
      if (
        last &&
        last.phase === nextEvent.phase &&
        last.stage === nextEvent.stage &&
        last.progress === nextEvent.progress &&
        last.message === nextEvent.message &&
        last.day === nextEvent.day &&
        last.iteration === nextEvent.iteration &&
        last.stream === nextEvent.stream &&
        last.optimizerPhase === nextEvent.optimizerPhase
      ) {
        return prev;
      }

      const next = [...prev, nextEvent];
      return next.length > 40 ? next.slice(next.length - 40) : next;
    });
  }, []);

  const handlePipelineComplete = useCallback(async (result) => {
    try {
      applyPipelineResult(result);
      setPipelineStatus('completed');
      setPipelineJobId(null);
      setOptimizing(false);
      if (activeWorkspaceId) {
        await refreshWorkspaces();
        await openWorkspaceById(activeWorkspaceId, { switchToStudio: false });
      }
      studioMarkSaved();
      setIngestionPanelOpen(false);
      setCreateFlowMode(false);
      notifications.success('Pipeline completado', 'Resultado final cargado');
    } catch (error) {
      notifications.error('Resultado invalido', error.message);
    }
  }, [activeWorkspaceId, applyPipelineResult, openWorkspaceById, refreshWorkspaces, studioMarkSaved]);

  const handlePipelineError = useCallback((errorCode) => {
    setPipelineStatus('error');
    setPipelineJobId(null);
    setOptimizing(false);
    if (String(errorCode || '') === 'NETWORK_UNSTABLE') {
      notifications.error(
        'Conexion perdida con backend',
        'No se pudo recuperar el estado de la optimizacion. Revisa logs y relanza.'
      );
      return;
    }
    notifications.error('Pipeline fallido', errorCode || 'Revisa logs del backend');
  }, []);

  const latestPipelineEvent = pipelineEvents.length > 0
    ? pipelineEvents[pipelineEvents.length - 1]
    : null;

  const isPipelineActive = Boolean(pipelineJobId) && ['starting', 'queued', 'running'].includes(pipelineStatus);
  const pipelineProgressValue = (() => {
    const eventProgress = Number(latestPipelineEvent?.progress);
    if (Number.isFinite(eventProgress)) {
      return Math.max(0, Math.min(100, Math.round(eventProgress)));
    }
    if (pipelineStatus === 'starting') return 5;
    if (pipelineStatus === 'queued') return 2;
    if (pipelineStatus === 'running') return 12;
    return 0;
  })();
  const pipelineStageText = String(
    latestPipelineEvent?.optimizerPhase
    || latestPipelineEvent?.stage
    || latestPipelineEvent?.phase
    || (pipelineStatus === 'starting' ? 'starting' : (pipelineStatus === 'queued' ? 'queued' : 'running'))
  );
  const pipelineMessageText = String(
    latestPipelineEvent?.message
    || (pipelineStatus === 'starting'
      ? 'Inicializando optimizacion...'
      : (pipelineStatus === 'queued'
        ? 'Trabajo en cola...'
        : 'Optimizando rutas...'))
  );

  return (
    <Layout
      stats={calculateStats()}
      scheduleByDay={scheduleByDay}
      activeDay={activeDay}
      onDayChange={handleDayChange}
      viewMode={viewMode}
      setViewMode={setViewMode}
      hasStudioAccess={Boolean(activeWorkspaceId)}
    >
      {pipelineJobId && !ingestionPanelOpen && (
        <div className="hidden" aria-hidden="true">
          <OptimizationProgress
            jobId={pipelineJobId}
            onProgress={handlePipelineProgress}
            onComplete={handlePipelineComplete}
            onError={handlePipelineError}
          />
        </div>
      )}

      {isPipelineActive && (
        <div className="fixed right-4 top-20 z-[900] w-[360px] max-w-[calc(100vw-2rem)] rounded-xl border border-[#2a4057] bg-[#081425]/95 p-3 shadow-2xl backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#58d5ff]">
                Optimizacion en curso
              </p>
              <p className="mt-0.5 truncate text-[12px] text-slate-200">
                {pipelineMessageText}
              </p>
              <p className="mt-1 text-[10px] font-mono text-slate-400">
                {pipelineStageText}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIngestionPanelOpen(true)}
              className="rounded-md border border-[#2a4057] px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-200 transition hover:bg-white/5"
            >
              Ver progreso
            </button>
          </div>
          <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-cyan-400 transition-all duration-300"
              style={{ width: `${pipelineProgressValue}%` }}
            />
          </div>
          <div className="mt-1.5 text-right text-[10px] font-mono text-slate-300">
            {pipelineProgressValue}%
          </div>
        </div>
      )}

      {ingestionPanelOpen && (
        <div className="m-3 h-full">
          <Sidebar
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            onUploadSuccess={handleUploadSuccess}
            routes={routes}
            parseReport={parseReport}
            schedule={schedule}
            onOptimize={handleOptimize}
            isOptimizing={optimizing}
            onReset={handleReset}
            optimizationStats={optimizationStats}
            scheduleByDay={scheduleByDay}
            forceUploadMode={createFlowMode}
            showCloseButton={true}
            onClose={() => {
              setIngestionPanelOpen(false);
              setCreateFlowMode(false);
            }}
            optimizationOptions={activeOptimizationOptions}
            onConfigureOptimizationOptions={() => openLoadOptionsModal({
              workspaceId: createFlowMode ? null : activeWorkspaceId,
              workspaceName: createFlowMode
                ? 'Nueva optimizacion'
                : (workspaces.find((ws) => String(ws.id) === String(activeWorkspaceId))?.name || ''),
            })}
          >
            {pipelineJobId && (
              <OptimizationProgress
                jobId={pipelineJobId}
                onProgress={handlePipelineProgress}
                onComplete={handlePipelineComplete}
                onError={handlePipelineError}
              />
            )}
            {!pipelineJobId && pipelineStatus === 'running' && (
              <div className="text-[10px] text-slate-500 data-mono px-1 uppercase tracking-[0.08em]">
                Eventos: {pipelineEvents.length} | metricas: {pipelineMetrics ? 'ok' : 'n/a'}
              </div>
            )}
          </Sidebar>
        </div>
      )}

      <section className="flex-1 relative m-3">
        <div className="absolute inset-0 flex flex-col">
          <div className="flex-1 relative overflow-auto">
            {viewMode === 'dashboard' && (
              <ControlHubPage
                workspaces={workspaces}
                activeWorkspaceId={activeWorkspaceId}
                onOpenWorkspace={async (workspaceId) => {
                  await openWorkspaceById(workspaceId, { switchToStudio: true });
                }}
                onCreateWorkspace={startNewWorkspaceFlow}
                onRefresh={refreshWorkspaces}
                onArchiveWorkspace={async (workspaceId) => {
                  await archiveWorkspace(workspaceId);
                  await refreshWorkspaces();
                }}
                onRestoreWorkspace={async (workspaceId) => {
                  await restoreWorkspace(workspaceId);
                  await refreshWorkspaces();
                }}
                onDeleteWorkspace={async (workspaceId, workspaceName) => {
                  await deleteWorkspace(workspaceId, workspaceName);
                  if (String(activeWorkspaceId || '') === String(workspaceId || '')) {
                    setActiveWorkspaceId(null);
                    setViewMode('dashboard');
                    setWorkspaceMode('create');
                    setSelectedBusId(null);
                    setSelectedRouteId(null);
                  }
                  await refreshWorkspaces();
                }}
                onConfigureWorkspaceOptions={async (workspaceId, workspaceName) => {
                  await openLoadOptionsModal({ workspaceId, workspaceName });
                }}
              />
            )}
            {viewMode === 'studio' && (
              <StudioErrorBoundary
                resetKey={`${activeWorkspaceId || ''}:${activeDay}:${routes.length}:${schedule.length}`}
                onBackToControl={() => setViewMode('dashboard')}
              >
                <OptimizationStudio
                  workspaceMode={workspaceMode}
                  routes={routes}
                  scheduleByDay={scheduleByDay}
                  activeDay={activeDay}
                  validationReport={validationReport}
                  onValidationReportChange={setValidationReport}
                  onSave={async (data) => {
                    const promptResult = await openTextInputModal({
                      title: 'Guardar version',
                      description: 'Opcional: nombre de este guardado',
                      placeholder: 'Ej: Ajuste buses lunes',
                      confirmLabel: 'Guardar',
                      cancelLabel: 'Cancelar',
                      allowEmpty: true,
                      defaultValue: '',
                    });
                    if (!promptResult?.confirmed) return;
                    const checkpointName = String(promptResult?.value || '').trim();
                    await handleSaveManualSchedule({ ...data, checkpoint_name: checkpointName || undefined }, 'save');
                  }}
                  onPublish={async (data) => {
                    const promptResult = await openTextInputModal({
                      title: 'Publicar version',
                      description: 'Opcional: nombre para esta publicacion',
                      placeholder: 'Ej: Operativo final semana',
                      confirmLabel: 'Publicar',
                      cancelLabel: 'Cancelar',
                      allowEmpty: true,
                      defaultValue: '',
                    });
                    if (!promptResult?.confirmed) return;
                    const checkpointName = String(promptResult?.value || '').trim();
                    await handleSaveManualSchedule({ ...data, checkpoint_name: checkpointName || undefined }, 'publish');
                  }}
                  selectedBusId={selectedBusId}
                  selectedRouteId={selectedRouteId}
                  onBusSelect={handleBusSelect}
                  onRouteSelect={handleRouteSelect}
                  onExport={handleExport}
                  pinnedBusIds={pinnedBusesByDay?.[activeDay] || []}
                  onTogglePinBus={handleTogglePinBus}
                />
              </StudioErrorBoundary>
            )}
          </div>

          {/* Comparacion de Optimizacion */}
          {showComparison && previousScheduleByDay && scheduleByDay && (
            <div className="p-4 bg-[#0b141f] border-t border-[#253a4f]">
              <CompareView
                before={previousScheduleByDay[activeDay]?.schedule || []}
                after={scheduleByDay[activeDay]?.schedule || []}
              />
              <button
                onClick={() => setShowComparison(false)}
                className="mt-4 px-3 py-1.5 control-btn rounded-md text-[11px] font-semibold uppercase tracking-[0.1em] transition-colors"
              >
                Ocultar comparativa
              </button>
            </div>
          )}
        </div>
      </section>

      <LoadOptionsModal
        open={loadOptionsModal.open}
        title={loadOptionsModal.title}
        initialValue={
          loadOptionsModal.workspaceId
            ? (optimizationOptionsByWorkspace?.[loadOptionsModal.workspaceId] || activeOptimizationOptions)
            : activeOptimizationOptions
        }
        onCancel={closeLoadOptionsModal}
        onSave={handleSaveLoadOptions}
      />

      <PreOptimizeRestrictionsModal
        open={preOptimizeModal.open}
        workspaceName={preOptimizeModal.workspaceName}
        onCancel={closePreOptimizeModal}
        onContinueWithoutChanges={async () => {
          const request = preOptimizeModal.request;
          closePreOptimizeModal();
          if (!request) return;
          await startAutoPipeline(
            request.routesInput,
            request.parseReportInput,
            request.workspaceIdInput
          );
        }}
        onConfigureRestrictions={async () => {
          const request = preOptimizeModal.request;
          closePreOptimizeModal();
          if (!request) return;
          setPendingOptimizationRequest(request);
          await openLoadOptionsModal({
            workspaceId: request.workspaceIdInput || null,
            workspaceName: request.workspaceName || '',
          });
        }}
      />

      <TextInputModal
        open={textInputModal.open}
        title={textInputModal.title}
        description={textInputModal.description}
        value={textInputModal.value}
        placeholder={textInputModal.placeholder}
        confirmLabel={textInputModal.confirmLabel}
        cancelLabel={textInputModal.cancelLabel}
        allowEmpty={textInputModal.allowEmpty}
        onChange={(value) => {
          setTextInputModal((prev) => ({ ...prev, value }));
        }}
        onCancel={() => closeTextInputModal({ confirmed: false, value: '' })}
        onConfirm={() => closeTextInputModal({ confirmed: true, value: textInputModal.value })}
      />
    </Layout>
  );
}

export default App;




