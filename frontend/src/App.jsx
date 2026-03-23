import React, { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import Layout from './components/Layout';
import Sidebar from './components/Sidebar';
import OptimizationProgress from './components/OptimizationProgress';
import StudioErrorBoundary from './components/StudioErrorBoundary';
import FleetConflictModal from './components/FleetConflictModal';
import FleetReconciliationModal from './components/FleetReconciliationModal';
import FleetScopeChoiceModal from './components/FleetScopeChoiceModal';
import LoadOptionsModal from './components/LoadOptionsModal';
import PreOptimizeRestrictionsModal from './components/PreOptimizeRestrictionsModal';
import ConfirmDialog from './components/ui/ConfirmDialog';
import TextInputDialog from './components/ui/TextInputDialog';
import { createUTE, listFleetCompanies, listUTEs } from './services/fleetService';
import { notifications } from './services/notifications';
import { clearGeometryCache } from './services/RouteService';
import { buildRouteCapacityMap, getItemCapacityNeeded } from './utils/capacity';
import { ALL_DAYS, DAY_LABELS } from './utils/days';
import {
  buildDayScheduleData,
  buildScheduleStats,
  createEmptyPinnedBusesByDay,
  createEmptyScheduleByDay,
  normalizeWorkspaceScheduleByDay,
} from './utils/workspaceSchedule';
import { DEFAULT_OPTIMIZATION_OPTIONS, normalizeOptimizationOptions } from './utils/optimizationOptions';
import { buildFleetReconciliationModalData, createFleetReconciliationModalState } from './utils/fleetReconciliation';
import {
  applyWorkspaceFleetReconciliation,
  archiveWorkspace,
  createWorkspace,
  deleteWorkspace,
  getWorkspace,
  getWorkspaceFleetPreview,
  getWorkspaceFleetReconciliation,
  getWorkspaceOptimizationOptions,
  getWorkspacePreferences,
  listWorkspaces,
  migrateLegacyWorkspaces,
  optimizeWorkspacePipeline,
  previewWorkspaceFleetReconciliationPlan,
  publishWorkspaceVersion,
  restoreWorkspace,
  saveWorkspaceVersion,
  setWorkspaceOptimizationOptions,
  setLastOpenWorkspace,
  updateWorkspaceCompany,
} from './services/workspaceService';
import { useWorkspaceStudioStore } from './stores/workspaceStudioStore';
import { useConfirmPrompt, useTextInputPrompt } from './hooks';

const CompareView = lazy(() => import('./components/CompareView').then((module) => ({ default: module.CompareView })));
const OptimizationStudio = lazy(() => import('./components/OptimizationStudio'));
const ControlHubPage = lazy(() => import('./pages/ControlHubPage'));
const FleetPage = lazy(() => import('./pages/FleetPage'));

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

function ScreenLoader({ label = 'Cargando...' }) {
  return (
    <div className="flex h-full min-h-[240px] items-center justify-center rounded-[18px] border border-[#304a62] bg-[#0d1623]/95 p-6">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-cyan-400/25 border-t-cyan-300" />
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-cyan-300/90 data-mono">Cargando</p>
          <p className="mt-1 text-[13px] font-semibold text-slate-100">{label}</p>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [routes, setRoutes] = useState([]);
  const [parseReport, setParseReport] = useState(null);
  const [scheduleByDay, setScheduleByDay] = useState(createEmptyScheduleByDay());
  const [studioLiveScheduleByDay, setStudioLiveScheduleByDay] = useState({});
  const [previousScheduleByDay, setPreviousScheduleByDay] = useState(null);
  const [validationReport, setValidationReport] = useState(null);
  const [activeDay, setActiveDay] = useState('L');
  const [optimizing, setOptimizing] = useState(false);
  const [showComparison, setShowComparison] = useState(false);
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
  const [activeWorkspaceDetail, setActiveWorkspaceDetail] = useState(null);

  const [activeTab, setActiveTab] = useState('upload');
  const [viewMode, setViewMode] = useState('dashboard'); // 'dashboard' | 'studio' | 'fleet'
  const [workspaceMode, setWorkspaceMode] = useState('create'); // 'create' | 'edit' | 'optimize'
  const [selectedBusId, setSelectedBusId] = useState(null);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [pinnedBusesByDay, setPinnedBusesByDay] = useState(createEmptyPinnedBusesByDay());
  const [ingestionPanelOpen, setIngestionPanelOpen] = useState(false);
  const [createFlowMode, setCreateFlowMode] = useState(false);
  const [optimizationOptionsByWorkspace, setOptimizationOptionsByWorkspace] = useState({});
  const [uteOptions, setUteOptions] = useState([]);
  const [fleetCompanies, setFleetCompanies] = useState([]);
  const [workspaceCompanyChanging, setWorkspaceCompanyChanging] = useState(false);
  const [activeOptimizationOptions, setActiveOptimizationOptions] = useState(
    normalizeOptimizationOptions(DEFAULT_OPTIMIZATION_OPTIONS)
  );
  const [loadOptionsModal, setLoadOptionsModal] = useState({
    open: false,
    workspaceId: null,
    title: 'Reglas de optimizacion',
  });
  const [preOptimizeModal, setPreOptimizeModal] = useState({
    open: false,
    workspaceName: '',
    request: null,
  });
  const [fleetConflictModal, setFleetConflictModal] = useState({
    open: false,
    conflicts: [],
  });
  const [fleetReconciliationModal, setFleetReconciliationModal] = useState(createFleetReconciliationModalState);
  const [fleetScopeChoiceModal, setFleetScopeChoiceModal] = useState({
    open: false,
    busId: null,
    applying: false,
  });
  const workspaceCompanyId = useMemo(
    () => String(activeWorkspaceDetail?.company_id || '').trim() || '',
    [activeWorkspaceDetail?.company_id]
  );
  const [pendingOptimizationRequest, setPendingOptimizationRequest] = useState(null);

  const [pipelineJobId, setPipelineJobId] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState('idle');
  const [pipelineEvents, setPipelineEvents] = useState([]);
  const [pipelineMetrics, setPipelineMetrics] = useState(null);
  const {
    textInputModal,
    openTextInputModal,
    closeTextInputModal,
    setTextInputValue,
  } = useTextInputPrompt();
  const {
    confirmModal,
    openConfirmModal,
    closeConfirmModal,
  } = useConfirmPrompt();

  const studioSetWorkspaceId = useWorkspaceStudioStore((state) => state.setActiveWorkspaceId);
  const studioSetRoutes = useWorkspaceStudioStore((state) => state.setRoutes);
  const studioSetScheduleByDay = useWorkspaceStudioStore((state) => state.setScheduleByDay);
  const studioSetActiveDay = useWorkspaceStudioStore((state) => state.setActiveDay);
  const studioSetSelectedBusId = useWorkspaceStudioStore((state) => state.setSelectedBusId);
  const studioSetSelectedRouteId = useWorkspaceStudioStore((state) => state.setSelectedRouteId);
  const studioSetDirty = useWorkspaceStudioStore((state) => state.setDirty);
  const studioMarkSaved = useWorkspaceStudioStore((state) => state.markSaved);
  const studioReset = useWorkspaceStudioStore((state) => state.resetStudio);

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

  const refreshUTEOptions = useCallback(async () => {
    try {
      const items = await listUTEs({ activeOnly: true });
      const normalized = Array.isArray(items) ? items : [];
      setUteOptions(normalized);
      return normalized;
    } catch {
      setUteOptions([]);
      return [];
    }
  }, []);

  const createWorkspaceFleetUte = useCallback(async () => {
    const workspaceCompany = Array.isArray(fleetCompanies)
      ? fleetCompanies.find((company) => String(company.id) === workspaceCompanyId)
      : null;
    if (!workspaceCompany?.id) {
      throw new Error('No hay empresa principal valida para crear la UTE');
    }
    const memberCompanyIds = (Array.isArray(fleetCompanies) ? fleetCompanies : [])
      .map((company) => String(company?.id || '').trim())
      .filter(Boolean);
    if (memberCompanyIds.length < 2) {
      throw new Error('Hace falta al menos una empresa socia adicional para crear la UTE');
    }
    const ute = await createUTE({
      name: `UTE ${workspaceCompany.name}`,
      owner_company_id: String(workspaceCompany.id),
      member_company_ids: memberCompanyIds,
    });
    await refreshUTEOptions();
    return ute;
  }, [fleetCompanies, refreshUTEOptions, workspaceCompanyId]);

  const refreshFleetCompanies = useCallback(async () => {
    try {
      const items = await listFleetCompanies();
      const normalized = Array.isArray(items) ? items : [];
      setFleetCompanies(normalized);
      return normalized;
    } catch {
      setFleetCompanies([]);
      return [];
    }
  }, []);

  const openLoadOptionsModal = useCallback(async ({ workspaceId = null, workspaceName = '' } = {}) => {
    const normalizedName = String(workspaceName || '').trim();
    const title = workspaceId
      ? `Reglas - ${normalizedName || 'Optimizacion'}`
      : 'Reglas por defecto';
    if (workspaceId) {
      const loaded = await fetchAndStoreWorkspaceOptions(workspaceId);
      setActiveOptimizationOptions(loaded);
    }
    await Promise.all([refreshUTEOptions(), refreshFleetCompanies()]);
    setLoadOptionsModal({
      open: true,
      workspaceId: workspaceId || null,
      title,
    });
  }, [fetchAndStoreWorkspaceOptions, refreshFleetCompanies, refreshUTEOptions]);

  const closeLoadOptionsModal = useCallback(() => {
    setLoadOptionsModal({ open: false, workspaceId: null, title: 'Reglas de optimizacion' });
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
      notifications.success('Reglas guardadas', 'Se aplicaran en la siguiente optimizacion');
    } else {
      setActiveOptimizationOptions(nextOptions);
      notifications.success('Reglas por defecto', 'Configuracion lista para la siguiente corrida');
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

  const handleWorkspaceCompanyChange = useCallback(async (companyId) => {
    const workspaceId = loadOptionsModal.workspaceId || activeWorkspaceId;
    const normalizedCompanyId = String(companyId || '').trim();
    if (!workspaceId || !normalizedCompanyId) return;
    try {
      setWorkspaceCompanyChanging(true);
      const detail = await updateWorkspaceCompany(workspaceId, normalizedCompanyId);
      setActiveWorkspaceDetail(detail);
      setWorkspaces((prev) => prev.map((item) => (
        String(item.id) === String(workspaceId)
          ? { ...item, company_id: detail.company_id, scope_summary: detail.scope_summary, readiness_summary: detail.readiness_summary }
          : item
      )));
      notifications.success('Empresa principal actualizada', 'La optimizacion ya usara esa empresa en modo Empresa');
    } catch (error) {
      notifications.error('No se pudo cambiar la empresa', error?.message || 'Error actualizando el workspace');
    } finally {
      setWorkspaceCompanyChanging(false);
    }
  }, [activeWorkspaceId, loadOptionsModal.workspaceId]);

  const refreshWorkspaces = useCallback(async () => {
    const data = await listWorkspaces().catch(() => ({ items: [] }));
    const items = Array.isArray(data?.items) ? data.items : [];
    setWorkspaces(items);
    return items;
  }, []);

  useEffect(() => {
    refreshFleetCompanies().catch(() => {});
  }, [refreshFleetCompanies]);

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
    setStudioLiveScheduleByDay({});
    setValidationReport(workingVersion?.validation_report || null);
    setActiveDay(preferredDay);
    setWorkspaceMode(detail?.status === 'active' ? 'edit' : 'optimize');
    setActiveWorkspaceDetail(detail || null);
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

  const buildEffectiveScheduleByDay = useCallback((baseScheduleByDay = {}, liveOverrides = {}) => {
    const normalizedBase = normalizeWorkspaceScheduleByDay(baseScheduleByDay);
    const nextScheduleByDay = { ...normalizedBase };

    for (const day of ALL_DAYS) {
      const overrideBuses = liveOverrides?.[day];
      if (!Array.isArray(overrideBuses)) continue;
      const currentDay = normalizedBase?.[day] || buildDayScheduleData();
      nextScheduleByDay[day] = buildDayScheduleData({
        buses: overrideBuses,
        metadata: currentDay?.metadata || {},
        unassignedRoutes: currentDay?.unassigned_routes || [],
      });
    }

    return nextScheduleByDay;
  }, []);

  const effectiveScheduleByDay = useMemo(
    () => buildEffectiveScheduleByDay(scheduleByDay, studioLiveScheduleByDay),
    [buildEffectiveScheduleByDay, scheduleByDay, studioLiveScheduleByDay]
  );

  // Current day's data
  const currentDayData = effectiveScheduleByDay?.[activeDay] || null;
  const schedule = currentDayData?.schedule || [];
  const optimizationStats = currentDayData?.stats || null;

  useEffect(() => {
    studioSetWorkspaceId(activeWorkspaceId);
  }, [activeWorkspaceId, studioSetWorkspaceId]);

  useEffect(() => {
    studioSetRoutes(routes);
  }, [routes, studioSetRoutes]);

  useEffect(() => {
    studioSetScheduleByDay(effectiveScheduleByDay);
  }, [effectiveScheduleByDay, studioSetScheduleByDay]);

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
    setStudioLiveScheduleByDay({});
    setValidationReport(pipelineResult?.validation_report || null);
    setPipelineMetrics(pipelineResult?.summary_metrics || null);
    setActiveWorkspaceDetail((prev) => (
      prev
        ? {
            ...prev,
            summary_metrics: pipelineResult?.summary_metrics || prev.summary_metrics || null,
          }
        : prev
    ));
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

    const loadingToast = notifications.loading('Iniciando planificacion automatica...');
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
            objective: String(resolvedOptions.objective || 'min_buses_viability'),
            max_duration_sec: 300,
            max_iterations: 2,
            preferred_solver: String(resolvedOptions.preferred_solver || 'auto'),
            invalid_rows_dropped: Number(parseReportInput?.rows_dropped_invalid || 0),
            balance_load: Boolean(resolvedOptions.balance_load),
            load_balance_hard_spread_limit: Number(resolvedOptions.load_balance_hard_spread_limit || 2),
            load_balance_target_band: Number(resolvedOptions.load_balance_target_band || 1),
            route_load_constraints: Array.isArray(resolvedOptions.route_load_constraints)
              ? resolvedOptions.route_load_constraints
              : [],
            enable_greedy_warm_start: resolvedOptions.enable_greedy_warm_start !== false,
            time_limit_seconds: resolvedOptions.time_limit_seconds == null
              ? null
              : Number(resolvedOptions.time_limit_seconds),
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
              objective: String(resolvedOptions.objective || 'min_buses_viability'),
              max_duration_sec: 300,
              max_iterations: 2,
              preferred_solver: String(resolvedOptions.preferred_solver || 'auto'),
              invalid_rows_dropped: Number(parseReportInput?.rows_dropped_invalid || 0),
              balance_load: Boolean(resolvedOptions.balance_load),
              load_balance_hard_spread_limit: Number(resolvedOptions.load_balance_hard_spread_limit || 2),
              load_balance_target_band: Number(resolvedOptions.load_balance_target_band || 1),
              route_load_constraints: Array.isArray(resolvedOptions.route_load_constraints)
                ? resolvedOptions.route_load_constraints
                : [],
              enable_greedy_warm_start: resolvedOptions.enable_greedy_warm_start !== false,
              time_limit_seconds: resolvedOptions.time_limit_seconds == null
                ? null
                : Number(resolvedOptions.time_limit_seconds),
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
        notifications.success('Planificacion completada', 'Resultado final disponible en Horario');
        refreshWorkspaces().catch(() => {});
        return { status: 'completed', jobId: null };
      } else {
        setPipelineJobId(data.job_id || null);
        setPipelineStatus(data.status || 'queued');
        notifications.info('Planificacion en curso', 'Mostrando progreso en tiempo real');
        return { status: data.status || 'queued', jobId: data.job_id || null };
      }
    } catch (error) {
      console.error('Error optimizing:', error);
      notifications.dismiss(loadingToast);
      notifications.error(
        'Error al generar la planificacion',
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
    setStudioLiveScheduleByDay({});
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
      const confirmation = await openConfirmModal({
        title: 'Se detectaron filas invalidas',
        description: `Calidad de datos ha descartado ${droppedRows} filas invalidas de ${rowsTotal} filas totales.

Puedes continuar con la optimizacion usando solo las filas validas, o detenerte aqui para revisar la importacion.`,
        tone: 'warning',
        confirmLabel: 'Continuar',
        cancelLabel: 'Revisar datos',
      });
      if (!confirmation?.confirmed) {
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
      'Pulsa "Generar plan operativo". Antes te preguntaremos si quieres revisar las reglas.'
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

  const handleReset = async () => {
    const confirmation = await openConfirmModal({
      title: 'Borrar datos de esta corrida',
      description: 'Se vaciaran las rutas cargadas, el horario generado, la comparativa y el estado temporal del estudio.\n\nLa optimizacion guardada seguira existiendo si ya estaba creada.',
      tone: 'danger',
      confirmLabel: 'Borrar',
      cancelLabel: 'Cancelar',
    });
    if (!confirmation?.confirmed) return;

    setRoutes([]);
    setParseReport(null);
    setScheduleByDay(createEmptyScheduleByDay());
    setStudioLiveScheduleByDay({});
    setPreviousScheduleByDay(null);
    setValidationReport(null);
    setShowComparison(false);
    setSelectedBusId(null);
    setSelectedRouteId(null);
    setPipelineJobId(null);
    setPipelineStatus('idle');
    setPipelineEvents([]);
    setPipelineMetrics(null);
    setActiveWorkspaceDetail(null);
    setViewMode('dashboard');
    setWorkspaceMode('create');
    setIngestionPanelOpen(false);
    setCreateFlowMode(false);
    studioReset();
    clearGeometryCache();
    notifications.info('Datos borrados', 'Puedes empezar de nuevo');
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

  const handleStudioLiveScheduleChange = useCallback((day, buses) => {
    const normalizedDay = ALL_DAYS.includes(day) ? day : activeDay;
    const safeBuses = Array.isArray(buses) ? buses : [];
    setStudioLiveScheduleByDay((prev) => ({
      ...prev,
      [normalizedDay]: safeBuses,
    }));
  }, [activeDay]);

  const publishWorkspaceSnapshot = useCallback(async (
    snapshotPayload,
    {
      previewDay = activeDay,
      successTitle = 'Version publicada',
      successMessage = 'La planificacion ya esta activa en Panel',
      skipReconciliationPrompt = false,
    } = {},
  ) => {
    if (!activeWorkspaceId) {
      throw new Error('No hay workspace activo para publicar');
    }

    const fleetPreview = await getWorkspaceFleetPreview(activeWorkspaceId, previewDay).catch(() => null);
    if (fleetPreview?.blocked && Array.isArray(fleetPreview?.conflicts) && fleetPreview.conflicts.length > 0) {
      setFleetConflictModal({
        open: true,
        conflicts: fleetPreview.conflicts,
      });
      throw new Error('Publicacion bloqueada por conflictos de flota');
    }

    const pendingVirtualCount = Number(fleetPreview?.virtual_created || 0);
    if (!skipReconciliationPrompt && pendingVirtualCount > 0) {
      const reconciliationData = await getWorkspaceFleetReconciliation(activeWorkspaceId, previewDay).catch(() => null);
      if (reconciliationData && typeof reconciliationData === 'object') {
        setFleetReconciliationModal(
          buildFleetReconciliationModalData({
            data: reconciliationData,
            activeDay: previewDay,
            dayLabels: DAY_LABELS,
            intent: 'publish',
            pendingPublishPayload: snapshotPayload,
            publishSuccessTitle: successTitle,
            publishSuccessMessage: successMessage,
          })
        );
        notifications.info(
          'Selecciona la flota antes de publicar',
          'Puedes dejar la propuesta automatica o ajustar buses aptos desde el Garage.'
        );
        return false;
      }
    }

    const resolvedPolicy = String(
      fleetPreview?.virtual_publish_policy
      || activeOptimizationOptions?.virtual_bus_publish_policy
      || 'allow'
    ).toLowerCase();

    if (
      resolvedPolicy === 'block'
      && Number(fleetPreview?.virtual_created || 0) > 0
    ) {
      const pendingItems = Array.isArray(fleetPreview?.reconciliation?.items)
        ? fleetPreview.reconciliation.items
        : [];
      setFleetReconciliationModal((prev) => ({
        ...createFleetReconciliationModalState(),
        ...prev,
        open: true,
        items: pendingItems,
        companyMix: fleetPreview?.reconciliation?.company_mix || null,
        requiredBusCount: Number(fleetPreview?.reconciliation?.required_bus_count || pendingItems.length || 0),
        realBoundCount: Number(fleetPreview?.reconciliation?.real_bound_count || 0),
        pendingRealReconciliationCount: Number(fleetPreview?.reconciliation?.pending_real_reconciliation_count || pendingItems.length || 0),
        availableRealVehicleCount: Number(fleetPreview?.scope_vehicle_count || 0),
        companiesAvailable: Number(fleetPreview?.reconciliation?.company_mix?.companies_with_options || 0),
        estimatedVirtualRemaining: Number(fleetPreview?.reconciliation?.company_mix?.uncovered_buses || 0),
        reconciliationSnapshot: fleetPreview?.reconciliation_snapshot || null,
        dayLabel: DAY_LABELS[previewDay] || previewDay,
        scopeLabel: fleetPreview?.scope_label || '',
        scopeVehicleCount: Number(fleetPreview?.scope_vehicle_count || 0),
        scopeMode: String(fleetPreview?.scope_mode || 'company'),
        intent: 'publish',
        pendingPublishPayload: snapshotPayload,
        previewDay,
        publishSuccessTitle: successTitle,
        publishSuccessMessage: successMessage,
        }));
      throw new Error('Publicacion bloqueada: hay buses ficticios pendientes de reconciliar');
    }

    try {
      await publishWorkspaceVersion(activeWorkspaceId, snapshotPayload);
    } catch (error) {
      const detail = error?.payload?.detail;
      const publication = detail?.fleet_publication;
      const isReconciliationBlocked = String(
        detail?.reason
        || publication?.reason
        || ''
      ).toLowerCase() === 'virtual_reconciliation_required';
      if (isReconciliationBlocked) {
        setFleetReconciliationModal({
          ...createFleetReconciliationModalState(),
          open: true,
          items: Array.isArray(publication?.reconciliation?.items)
            ? publication.reconciliation.items
            : [],
          companyMix: publication?.reconciliation?.company_mix || null,
          requiredBusCount: Number(publication?.reconciliation?.required_bus_count || 0),
          realBoundCount: Number(publication?.reconciliation?.real_bound_count || 0),
          pendingRealReconciliationCount: Number(publication?.reconciliation?.pending_real_reconciliation_count || 0),
          availableRealVehicleCount: Number(publication?.scope_vehicle_count || 0),
          companiesAvailable: Number(publication?.reconciliation?.company_mix?.companies_with_options || 0),
          estimatedVirtualRemaining: Number(publication?.reconciliation?.company_mix?.uncovered_buses || 0),
          reconciliationSnapshot: publication?.reconciliation_snapshot || null,
          dayLabel: DAY_LABELS[previewDay] || previewDay,
          scopeLabel: publication?.scope_label || '',
          scopeVehicleCount: Number(publication?.scope_vehicle_count || 0),
          scopeMode: String(publication?.scope_mode || 'company'),
          intent: 'publish',
          pendingPublishPayload: snapshotPayload,
          previewDay,
          publishSuccessTitle: successTitle,
          publishSuccessMessage: successMessage,
        });
      } else if (publication?.blocked) {
        setFleetConflictModal({
          open: true,
          conflicts: Array.isArray(publication?.conflicts) ? publication.conflicts : [],
        });
      }
      throw error;
    }

    notifications.success(successTitle, successMessage);
    return true;
  }, [activeDay, activeOptimizationOptions?.virtual_bus_publish_policy, activeWorkspaceId]);

  const handleSaveManualSchedule = async (scheduleData, intent = 'save') => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const payload = {
      day: scheduleData?.day,
      buses: scheduleData?.buses || [],
      unassigned_routes: scheduleData?.unassigned_routes || [],
      workspace_id: activeWorkspaceId || null,
      metadata: {
        mode: scheduleData?.mode || 'draft',
        workspace_id: activeWorkspaceId || null,
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

      const mergedScheduleByDay = buildEffectiveScheduleByDay(
        scheduleByDay,
        {
          [payload.day]: payload.buses,
        }
      );

      setScheduleByDay(mergedScheduleByDay);
      setStudioLiveScheduleByDay((prev) => ({
        ...prev,
        [payload.day]: payload.buses,
      }));
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
          const published = await publishWorkspaceSnapshot(snapshotPayload, {
            previewDay: payload.day || activeDay,
            successTitle: 'Version publicada',
            successMessage: 'La planificacion ya esta activa en Panel',
          });
          if (!published) {
            return data;
          }
        } else {
          await saveWorkspaceVersion(activeWorkspaceId, snapshotPayload);
          notifications.success('Dia guardado', `${DAY_LABELS[payload.day] || payload.day} guardado en la semana`);
        }
        await refreshWorkspaces();
        if (activeWorkspaceId) {
          const freshDetail = await getWorkspace(activeWorkspaceId).catch(() => null);
          if (freshDetail) {
            setActiveWorkspaceDetail(freshDetail);
          }
        }
        studioMarkSaved();
      }
      return data;
    }

    throw lastError || new Error('No se pudo guardar el horario manual');
  };

  const handlePublishWholeWorkspace = useCallback(async () => {
    if (!activeWorkspaceId) return;

    const effectiveWeekSchedule = buildEffectiveScheduleByDay(scheduleByDay, studioLiveScheduleByDay);
    const weekHasRoutes = ALL_DAYS.some((day) => Array.isArray(effectiveWeekSchedule?.[day]?.schedule) && effectiveWeekSchedule[day].schedule.length > 0);
    if (!weekHasRoutes) {
      notifications.warning('No hay nada que publicar', 'La semana no tiene buses asignados');
      return;
    }

    const promptResult = await openTextInputModal({
      title: 'Publicar semana completa',
      description: 'Opcional: nombre para esta publicacion de los 5 dias',
      placeholder: 'Ej: Operativo final semana 12',
      confirmLabel: 'Publicar semana',
      cancelLabel: 'Cancelar',
      allowEmpty: true,
      defaultValue: '',
    });
    if (!promptResult?.confirmed) return;

    const checkpointName = String(promptResult?.value || '').trim();
    const snapshotPayload = {
      checkpoint_name: checkpointName || `publish-week-${new Date().toISOString().slice(0, 19)}`,
      routes_payload: routes,
      schedule_by_day: effectiveWeekSchedule,
      parse_report: parseReport || null,
      validation_report: validationReport || null,
      summary_metrics: effectiveWeekSchedule?.[activeDay]?.stats || {},
    };

    const loadingToast = notifications.loading('Publicando semana completa...');
    try {
      const published = await publishWorkspaceSnapshot(snapshotPayload, {
        previewDay: activeDay,
        successTitle: 'Semana publicada',
        successMessage: 'Los 5 dias ya estan activos en Panel',
      });
      if (!published) {
        return;
      }
      setScheduleByDay(effectiveWeekSchedule);
      await refreshWorkspaces();
      const freshDetail = await getWorkspace(activeWorkspaceId).catch(() => null);
      if (freshDetail) {
        setActiveWorkspaceDetail(freshDetail);
      }
      studioMarkSaved();
    } catch (error) {
      notifications.error('No se pudo publicar la semana', error?.message || 'Error publicando la semana completa');
    } finally {
      notifications.dismiss(loadingToast);
    }
  }, [activeDay, activeWorkspaceId, buildEffectiveScheduleByDay, openTextInputModal, parseReport, publishWorkspaceSnapshot, refreshWorkspaces, routes, scheduleByDay, studioLiveScheduleByDay, studioMarkSaved, validationReport]);

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
      notifications.success('Planificacion completada', 'Resultado final cargado');
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
    notifications.error('Planificacion fallida', errorCode || 'Revisa logs del backend');
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
  const activeWorkspaceSummary = useMemo(() => {
    if (!activeWorkspaceId) return activeWorkspaceDetail || null;
    const listed = workspaces.find((workspace) => String(workspace.id) === String(activeWorkspaceId)) || null;
    if (!listed && !activeWorkspaceDetail) return null;
    return {
      ...(listed || {}),
      ...(activeWorkspaceDetail || {}),
      scope_summary: activeWorkspaceDetail?.scope_summary || listed?.scope_summary || null,
      summary_metrics: activeWorkspaceDetail?.summary_metrics || listed?.summary_metrics || null,
    };
  }, [activeWorkspaceDetail, activeWorkspaceId, workspaces]);

  const layoutWorkspaceContext = useMemo(() => (
    activeWorkspaceSummary
      ? {
          ...activeWorkspaceSummary,
          activeDayLabel: DAY_LABELS[activeDay] || activeDay,
        }
      : null
  ), [activeDay, activeWorkspaceSummary]);

  const openFleetReconciliationCenter = useCallback(async (busId = null) => {
    if (!activeWorkspaceId) return;
    setFleetScopeChoiceModal({
      open: true,
      busId: busId || null,
      applying: false,
    });
  }, [activeWorkspaceId]);

  const openFleetReconciliationForScope = useCallback(async ({ scopeMode, busId = null }) => {
    if (!activeWorkspaceId) return;
    const loadingToast = notifications.loading('Preparando reconciliacion de flota...');
    try {
      setFleetScopeChoiceModal({ open: false, busId: null, applying: false });
      const normalizedScopeMode = String(scopeMode || 'company') === 'ute' ? 'ute' : 'company';
      let availableUteOptions = Array.isArray(uteOptions) ? [...uteOptions] : [];
      if (
        normalizedScopeMode === 'ute'
        && availableUteOptions.length === 0
      ) {
        const createdUte = await createWorkspaceFleetUte();
        if (createdUte?.id) {
          notifications.success(
            'UTE lista',
            `${createdUte.name || 'La UTE'} se ha creado automaticamente con las empresas cargadas`
          );
          availableUteOptions = [createdUte];
        }
      }
      if (normalizedScopeMode === 'ute' && !availableUteOptions[0]?.id) {
        throw new Error('No se pudo preparar una UTE valida con las empresas cargadas');
      }
      let optionsToPersist = null;
      if (
        normalizedScopeMode !== String(activeOptimizationOptions?.fleet_scope_mode || 'company')
        || (
          normalizedScopeMode === 'ute'
          && !String(activeOptimizationOptions?.fleet_scope_ute_id || '').trim()
          && availableUteOptions[0]?.id
        )
      ) {
        optionsToPersist = normalizeOptimizationOptions({
          ...(activeOptimizationOptions || DEFAULT_OPTIMIZATION_OPTIONS),
          fleet_scope_mode: normalizedScopeMode,
          fleet_scope_ute_id: normalizedScopeMode === 'ute'
            ? (activeOptimizationOptions?.fleet_scope_ute_id || availableUteOptions[0]?.id || null)
            : null,
        });
        const persisted = await setWorkspaceOptimizationOptions(activeWorkspaceId, optionsToPersist);
        const normalizedPersisted = normalizeOptimizationOptions(persisted);
        setActiveOptimizationOptions(normalizedPersisted);
        setOptimizationOptionsByWorkspace((prev) => ({
          ...prev,
          [String(activeWorkspaceId)]: normalizedPersisted,
        }));
      }
      const data = await getWorkspaceFleetReconciliation(activeWorkspaceId, activeDay);
      if (!data || typeof data !== 'object') {
        throw new Error('La reconciliacion no devolvio datos validos');
      }
      setFleetReconciliationModal(
        buildFleetReconciliationModalData({
          data,
          activeDay,
          busId,
          dayLabels: DAY_LABELS,
        })
      );
    } catch (error) {
      notifications.error('No se pudo abrir la reconciliacion', error?.message || 'Error cargando sugerencias');
    } finally {
      notifications.dismiss(loadingToast);
    }
  }, [activeDay, activeOptimizationOptions, activeWorkspaceId, createWorkspaceFleetUte, uteOptions]);

  const previewFleetReconciliationProposal = useCallback(async (companyAllocations = [], busSelections = []) => {
    if (!activeWorkspaceId) return null;
    const modalContext = fleetReconciliationModal;
    return previewWorkspaceFleetReconciliationPlan(activeWorkspaceId, {
      day: modalContext.previewDay || activeDay,
      allocation_mode: 'pending_only',
      autofill_remaining: true,
      bus_ids: modalContext.busId ? [modalContext.busId] : [],
      company_allocations: Array.isArray(companyAllocations) ? companyAllocations : [],
      bus_selections: Array.isArray(busSelections) ? busSelections : [],
    });
  }, [activeDay, activeWorkspaceId, fleetReconciliationModal]);

  const applyFleetReconciliationProposal = useCallback(async (companyAllocations = [], busSelections = []) => {
    if (!activeWorkspaceId) return;
    const modalContext = fleetReconciliationModal;
    try {
      setFleetReconciliationModal((prev) => ({ ...prev, applying: true }));
      const result = await applyWorkspaceFleetReconciliation(activeWorkspaceId, {
        day: modalContext.previewDay || activeDay,
        allocation_mode: 'pending_only',
        autofill_remaining: true,
        bus_ids: modalContext.busId ? [modalContext.busId] : [],
        company_allocations: Array.isArray(companyAllocations) ? companyAllocations : [],
        bus_selections: Array.isArray(busSelections) ? busSelections : [],
      });

      if (result?.schedule_by_day && typeof result.schedule_by_day === 'object') {
        setScheduleByDay(normalizeWorkspaceScheduleByDay(result.schedule_by_day));
        setStudioLiveScheduleByDay({});
      }
      await refreshWorkspaces();
      const freshDetail = await getWorkspace(activeWorkspaceId).catch(() => null);
      if (freshDetail) {
        setActiveWorkspaceDetail(freshDetail);
      }

      if (modalContext.intent === 'publish' && modalContext.pendingPublishPayload) {
        const published = await publishWorkspaceSnapshot(
          {
            ...modalContext.pendingPublishPayload,
            schedule_by_day: (
              result?.schedule_by_day
              && typeof result.schedule_by_day === 'object'
            )
              ? result.schedule_by_day
              : (modalContext.pendingPublishPayload?.schedule_by_day || {}),
          },
          {
            previewDay: modalContext.previewDay || activeDay,
            successTitle: modalContext.publishSuccessTitle || 'Version publicada',
            successMessage: modalContext.publishSuccessMessage || 'La planificacion ya esta activa en Panel',
            skipReconciliationPrompt: true,
          }
        );
        if (published) {
          await refreshWorkspaces();
          const publishedDetail = await getWorkspace(activeWorkspaceId).catch(() => null);
          if (publishedDetail) {
            setActiveWorkspaceDetail(publishedDetail);
          }
          setFleetReconciliationModal(createFleetReconciliationModalState());
          return;
        }
      }

      setFleetReconciliationModal(createFleetReconciliationModalState());

      notifications.success(
        'Reconciliacion aplicada',
        `${Number(result?.applied_count || 0)} bus(es) asignados a flota real`
      );

      if (Number(result?.remaining_pending || 0) > 0) {
        notifications.info(
          'Aun quedan buses provisionales',
          `${Number(result?.remaining_pending || 0)} siguen pendientes de asignacion real`
        );
      }
    } catch (error) {
      setFleetReconciliationModal((prev) => ({ ...prev, applying: false }));
      notifications.error(
        'No se pudo aplicar la reconciliacion',
        error?.message || 'Error guardando la reasignacion de flota'
      );
    }
  }, [activeDay, activeWorkspaceId, fleetReconciliationModal, publishWorkspaceSnapshot, refreshWorkspaces]);

  return (
    <Layout
      stats={calculateStats()}
      scheduleByDay={effectiveScheduleByDay}
      activeDay={activeDay}
      onDayChange={handleDayChange}
      viewMode={viewMode}
      setViewMode={setViewMode}
      hasStudioAccess={Boolean(activeWorkspaceId)}
      workspaceContext={layoutWorkspaceContext}
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
                Planificacion en curso
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
            <Suspense fallback={<ScreenLoader label="Cargando vista operativa..." />}>
              {viewMode === 'dashboard' && (
                <ControlHubPage
                  workspaces={workspaces}
                  activeWorkspaceId={activeWorkspaceId}
                  onOpenWorkspace={async (workspaceId) => {
                    await openWorkspaceById(workspaceId, { switchToStudio: true });
                  }}
                  onCreateWorkspace={startNewWorkspaceFlow}
                  onOpenFleet={() => setViewMode('fleet')}
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
                      setActiveWorkspaceDetail(null);
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
              {viewMode === 'fleet' && (
                <FleetPage />
              )}
              {viewMode === 'studio' && (
                <div className="h-full min-h-0 flex flex-col">
                  <div className="flex-1 min-h-0">
                    <StudioErrorBoundary
                      resetKey={`${activeWorkspaceId || ''}:${activeDay}:${routes.length}:${schedule.length}`}
                      onBackToControl={() => setViewMode('dashboard')}
                    >
                      <OptimizationStudio
                        workspaceMode={workspaceMode}
                        routes={routes}
                        scheduleByDay={scheduleByDay}
                        activeDay={activeDay}
                        onDayChange={handleDayChange}
                        validationReport={validationReport}
                        onValidationReportChange={setValidationReport}
                        onSave={async (data) => {
                          const promptResult = await openTextInputModal({
                            title: `Guardar ${DAY_LABELS[activeDay] || activeDay}`,
                            description: 'Opcional: nombre para el guardado del dia activo',
                            placeholder: 'Ej: Ajuste buses lunes',
                            confirmLabel: 'Guardar dia',
                            cancelLabel: 'Cancelar',
                            allowEmpty: true,
                            defaultValue: '',
                          });
                          if (!promptResult?.confirmed) return;
                          const checkpointName = String(promptResult?.value || '').trim();
                          await handleSaveManualSchedule({ ...data, checkpoint_name: checkpointName || undefined }, 'save');
                        }}
                        selectedBusId={selectedBusId}
                        selectedRouteId={selectedRouteId}
                        onBusSelect={handleBusSelect}
                        onRouteSelect={handleRouteSelect}
                        onExport={handleExport}
                        pinnedBusIds={pinnedBusesByDay?.[activeDay] || []}
                        onTogglePinBus={handleTogglePinBus}
                        onOpenReconciliation={openFleetReconciliationCenter}
                        onStudioLiveScheduleChange={handleStudioLiveScheduleChange}
                        workspace={activeWorkspaceSummary}
                        stats={calculateStats()}
                        onOpenRules={() => openLoadOptionsModal({
                          workspaceId: activeWorkspaceId,
                          workspaceName: activeWorkspaceSummary?.name || '',
                        })}
                        onPublishWeek={handlePublishWholeWorkspace}
                        publishDisabled={!activeWorkspaceId || !ALL_DAYS.some((day) => Array.isArray(effectiveScheduleByDay?.[day]?.schedule) && effectiveScheduleByDay[day].schedule.length > 0)}
                        optimizationOptions={activeOptimizationOptions}
                        workspaceCompanies={fleetCompanies}
                      />
                    </StudioErrorBoundary>
                  </div>
                </div>
              )}
            </Suspense>
          </div>

          {/* Comparacion de Optimizacion */}
          {showComparison && previousScheduleByDay && scheduleByDay && (
            <div className="p-4 bg-[#0b141f] border-t border-[#253a4f]">
              <Suspense fallback={<ScreenLoader label="Cargando comparativa..." />}>
                <CompareView
                  before={previousScheduleByDay[activeDay]?.schedule || []}
                  after={scheduleByDay[activeDay]?.schedule || []}
                />
              </Suspense>
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
        uteOptions={uteOptions}
        workspaceCompanies={fleetCompanies}
        workspaceCompanyId={
          loadOptionsModal.workspaceId
            ? (
                (String(activeWorkspaceDetail?.id || '') === String(loadOptionsModal.workspaceId)
                  ? activeWorkspaceDetail?.company_id
                  : workspaces.find((item) => String(item.id) === String(loadOptionsModal.workspaceId))?.company_id)
                || ''
              )
            : ''
        }
        workspaceCompanyChanging={workspaceCompanyChanging}
        onWorkspaceCompanyChange={handleWorkspaceCompanyChange}
        routeCount={Array.isArray(routes) ? routes.length : null}
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

      <TextInputDialog
        open={textInputModal.open}
        title={textInputModal.title}
        description={textInputModal.description}
        value={textInputModal.value}
        placeholder={textInputModal.placeholder}
        confirmLabel={textInputModal.confirmLabel}
        cancelLabel={textInputModal.cancelLabel}
        allowEmpty={textInputModal.allowEmpty}
        onChange={setTextInputValue}
        onCancel={() => closeTextInputModal({ confirmed: false, value: '' })}
        onConfirm={() => closeTextInputModal({ confirmed: true, value: textInputModal.value })}
      />

      <ConfirmDialog
        open={confirmModal.open}
        title={confirmModal.title}
        description={confirmModal.description}
        tone={confirmModal.tone}
        confirmLabel={confirmModal.confirmLabel}
        cancelLabel={confirmModal.cancelLabel}
        onCancel={() => closeConfirmModal({ confirmed: false })}
        onConfirm={() => closeConfirmModal({ confirmed: true })}
      />

      <FleetConflictModal
        open={fleetConflictModal.open}
        conflicts={fleetConflictModal.conflicts}
        onClose={() => setFleetConflictModal({ open: false, conflicts: [] })}
      />
      <FleetReconciliationModal
        open={fleetReconciliationModal.open}
        items={fleetReconciliationModal.items}
        companyMix={fleetReconciliationModal.companyMix}
        requiredBusCount={fleetReconciliationModal.requiredBusCount}
        realBoundCount={fleetReconciliationModal.realBoundCount}
        pendingRealReconciliationCount={fleetReconciliationModal.pendingRealReconciliationCount}
        availableRealVehicleCount={fleetReconciliationModal.availableRealVehicleCount}
        companiesAvailable={fleetReconciliationModal.companiesAvailable}
        estimatedVirtualRemaining={fleetReconciliationModal.estimatedVirtualRemaining}
        reconciliationSnapshot={fleetReconciliationModal.reconciliationSnapshot}
        dayLabel={fleetReconciliationModal.dayLabel}
        scopeLabel={fleetReconciliationModal.scopeLabel}
        scopeVehicleCount={fleetReconciliationModal.scopeVehicleCount}
        scopeMode={fleetReconciliationModal.scopeMode}
        busId={fleetReconciliationModal.busId}
        operationalSummary={fleetReconciliationModal.operationalSummary}
        candidateRejectionReasons={fleetReconciliationModal.candidateRejectionReasons}
        applying={fleetReconciliationModal.applying}
        intent={fleetReconciliationModal.intent}
        onApply={applyFleetReconciliationProposal}
        onPreviewPlan={previewFleetReconciliationProposal}
        onClose={() => setFleetReconciliationModal(createFleetReconciliationModalState())}
      />
      <FleetScopeChoiceModal
        open={fleetScopeChoiceModal.open}
        workspaceCompany={Array.isArray(fleetCompanies)
          ? fleetCompanies.find((company) => String(company.id) === String(activeWorkspaceDetail?.company_id || activeWorkspaceSummary?.company_id || ''))
          : null}
        fleetCompanies={fleetCompanies}
        uteOptions={uteOptions}
        applying={fleetScopeChoiceModal.applying}
        onChooseCompany={() => openFleetReconciliationForScope({ scopeMode: 'company', busId: fleetScopeChoiceModal.busId })}
        onChooseUte={() => openFleetReconciliationForScope({ scopeMode: 'ute', busId: fleetScopeChoiceModal.busId })}
        onClose={() => setFleetScopeChoiceModal({ open: false, busId: null, applying: false })}
      />
    </Layout>
  );
}

export default App;




