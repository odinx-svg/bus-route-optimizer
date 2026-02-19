import React, { useCallback, useEffect, useRef, useState } from 'react';
import Layout from './components/Layout';
import Sidebar from './components/Sidebar';
import { CompareView } from './components/CompareView';
import OptimizationStudio from './components/OptimizationStudio';
import OptimizationProgress from './components/OptimizationProgress';
import ControlHubPage from './pages/ControlHubPage';
import { notifications } from './services/notifications';
import { clearGeometryCache } from './services/RouteService';
import { buildRouteCapacityMap, getItemCapacityNeeded } from './utils/capacity';
import {
  archiveWorkspace,
  createWorkspace,
  getWorkspace,
  getWorkspacePreferences,
  listWorkspaces,
  migrateLegacyWorkspaces,
  optimizeWorkspacePipeline,
  publishWorkspaceVersion,
  restoreWorkspace,
  saveWorkspaceVersion,
  setLastOpenWorkspace,
} from './services/workspaceService';
import { useWorkspaceStudioStore } from './stores/workspaceStudioStore';

const DAY_LABELS = { L: 'Lunes', M: 'Martes', Mc: 'Miercoles', X: 'Jueves', V: 'Viernes' };
const ALL_DAYS = ['L', 'M', 'Mc', 'X', 'V'];
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
  const avgRoutesPerBus = totalBuses > 0
    ? Math.round((totalRoutes / totalBuses) * 10) / 10
    : 0;

  return {
    total_buses: totalBuses,
    total_entries: totalEntries,
    total_exits: totalExits,
    avg_routes_per_bus: avgRoutesPerBus,
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
    setActiveWorkspaceId(workspaceId);
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
  }, [hydrateWorkspaceDetail, studioMarkSaved, studioSetWorkspaceId]);

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
        `Calidad de datos detectó ${droppedRows} filas inválidas descartadas de ${rowsTotal} filas.\n\n¿Quieres continuar igualmente con el pipeline automático?`
      );
      if (!shouldContinue) {
        notifications.info(
          'Pipeline pausado',
          'Revisa el panel de calidad de datos antes de optimizar'
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
      await refreshWorkspaces();
    }

    const pipelineStart = await startAutoPipeline(uploadedRoutes, uploadReport, workspaceId);
    setCreateFlowMode(false);
    if (pipelineStart?.status === 'completed') {
      setIngestionPanelOpen(false);
    }
  };

  const handleOptimize = async () => {
    await startAutoPipeline(routes, parseReport, activeWorkspaceId);
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

  const handleExport = async () => {
    if (schedule.length === 0) {
      notifications.warning('No hay resultados', 'Optimiza las rutas primero');
      return;
    }

    const loadingToast = notifications.loading('Generando PDF...');

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const dayName = DAY_LABELS[activeDay] || activeDay;
      const routeCapacityById = buildRouteCapacityMap(routes);
      const scheduleForPdf = (schedule || []).map((bus) => ({
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
  };

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
              />
            )}
            {viewMode === 'studio' && (
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



