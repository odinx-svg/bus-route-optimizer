import React, { useCallback, useEffect, useState } from 'react';
import Layout from './components/Layout';
import Sidebar from './components/Sidebar';
import BusListPanel from './components/BusListPanel';
import MapView from './components/MapView';
import { CompareView } from './components/CompareView';
import { UnifiedWorkspace } from './components/workspace';
import { MonteCarloPanel } from './components/MonteCarloPanel';
import OptimizationProgress from './components/OptimizationProgress';
import FleetPage from './pages/FleetPage';
import OperationsDashboard from './pages/OperationsDashboard';
import { notifications } from './services/notifications';
import { clearGeometryCache } from './services/RouteService';
import { buildRouteCapacityMap, getItemCapacityNeeded } from './utils/capacity';
import { PanelLeftClose, PanelLeft } from 'lucide-react';

const DAY_LABELS = { L: 'Lunes', M: 'Martes', Mc: 'Miercoles', X: 'Jueves', V: 'Viernes' };
const ALL_DAYS = ['L', 'M', 'Mc', 'X', 'V'];
const createEmptyScheduleByDay = () => (
  ALL_DAYS.reduce((acc, day) => {
    acc[day] = { schedule: [], stats: null };
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

function App() {
  const [routes, setRoutes] = useState([]);
  const [parseReport, setParseReport] = useState(null);
  const [scheduleByDay, setScheduleByDay] = useState(null);
  const [previousScheduleByDay, setPreviousScheduleByDay] = useState(null);
  const [validationReport, setValidationReport] = useState(null);
  const [activeDay, setActiveDay] = useState('L');
  const [optimizing, setOptimizing] = useState(false);
  const [showComparison, setShowComparison] = useState(false);

  const [activeTab, setActiveTab] = useState('upload');
  const [viewMode, setViewMode] = useState('dashboard'); // 'dashboard' | 'map' | 'workspace' | 'fleet' | 'montecarlo'
  const [workspaceMode, setWorkspaceMode] = useState('create'); // 'create' | 'edit' | 'optimize'
  const [selectedBusId, setSelectedBusId] = useState(null);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [pipelineJobId, setPipelineJobId] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState('idle');
  const [pipelineEvents, setPipelineEvents] = useState([]);
  const [pipelineMetrics, setPipelineMetrics] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const loadPersistedSchedules = async () => {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const loadedByDay = {};

      await Promise.all(ALL_DAYS.map(async (day) => {
        try {
          const response = await fetch(`${apiUrl}/api/schedules/${day}`);
          if (response.status === 404) return;
          if (!response.ok) {
            throw new Error(`No se pudo cargar ${day} (${response.status})`);
          }

          const data = await response.json();
          const persisted = data?.schedule || {};
          const buses = Array.isArray(persisted?.buses)
            ? persisted.buses
            : (Array.isArray(persisted?.schedule) ? persisted.schedule : []);

          if (!Array.isArray(buses) || buses.length === 0) return;

          loadedByDay[day] = buildDayScheduleData({
            buses,
            metadata: persisted?.metadata || null,
            unassignedRoutes: persisted?.unassigned_routes || [],
          });
        } catch (error) {
          console.warn(`[persisted-schedule] ${day}:`, error);
        }
      }));

      if (cancelled) return;

      const loadedDays = ALL_DAYS.filter((day) => loadedByDay[day]?.schedule?.length > 0);
      if (loadedDays.length === 0) return;

      const hydratedSchedule = {
        ...createEmptyScheduleByDay(),
        ...loadedByDay,
      };

      setScheduleByDay((prev) => {
        const alreadyLoaded = prev && ALL_DAYS.some((day) => (prev?.[day]?.schedule?.length || 0) > 0);
        return alreadyLoaded ? prev : hydratedSchedule;
      });

      const defaultDay = loadedDays[0];
      const persistedMode = hydratedSchedule?.[defaultDay]?.metadata?.mode;
      const nextMode = persistedMode === 'optimize' ? 'optimize' : 'edit';
      setActiveDay(defaultDay);
      setWorkspaceMode(nextMode);
      setViewMode('workspace');
    };

    loadPersistedSchedules();
    return () => {
      cancelled = true;
    };
  }, []);

  // Current day's data
  const currentDayData = scheduleByDay?.[activeDay] || null;
  const schedule = currentDayData?.schedule || [];
  const optimizationStats = currentDayData?.stats || null;

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

    if (scheduleByDay) {
      setPreviousScheduleByDay(scheduleByDay);
    }

    setScheduleByDay(scheduleResult);
    setValidationReport(pipelineResult?.validation_report || null);
    setShowComparison(true);
    setViewMode('workspace');
    setWorkspaceMode('optimize');

    let maxBuses = 0;
    let maxDay = 'L';
    for (const day of ALL_DAYS) {
      const dayBuses = scheduleResult[day]?.stats?.total_buses || 0;
      if (dayBuses > maxBuses) {
        maxBuses = dayBuses;
        maxDay = day;
      }
    }
    setActiveDay(maxDay);
  }, [scheduleByDay]);

  const startAutoPipeline = async (routesInput = routes, parseReportInput = parseReport) => {
    if (!routesInput || routesInput.length === 0) {
      notifications.warning('No hay datos', 'Sube archivos Excel primero');
      return;
    }

    setOptimizing(true);
    setPipelineStatus('starting');
    setPipelineJobId(null);
    setPipelineEvents([]);
    setPipelineMetrics(null);
    setViewMode('workspace');
    setWorkspaceMode('optimize');

    const loadingToast = notifications.loading('Iniciando pipeline automatico...');

    try {
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

      const data = await response.json();
      notifications.dismiss(loadingToast);

      if (data.status === 'completed' && data.result) {
        applyPipelineResult(data.result);
        setPipelineStatus('completed');
        setOptimizing(false);
        notifications.success('Pipeline completado', 'Resultado final disponible en Workspace');
      } else {
        setPipelineJobId(data.job_id || null);
        setPipelineStatus(data.status || 'queued');
        notifications.info('Pipeline en ejecucion', 'Mostrando progreso en tiempo real');
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
    }
  };

  const handleUploadSuccess = (payload) => {
    const uploadedRoutes = Array.isArray(payload) ? payload : (payload?.routes || []);
    const uploadReport = Array.isArray(payload) ? null : (payload?.parse_report || null);

    setRoutes(uploadedRoutes);
    setParseReport(uploadReport);
    setScheduleByDay(null);
    setValidationReport(null);
    setSelectedBusId(null);
    setSelectedRouteId(null);

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

    startAutoPipeline(uploadedRoutes, uploadReport);
  };

  const handleOptimize = async () => {
    await startAutoPipeline(routes, parseReport);
  };

  const handleReset = () => {
    if (confirm('Borrar todos los datos?')) {
      setRoutes([]);
      setParseReport(null);
      setScheduleByDay(null);
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
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tutti_schedule_${dayName.toLowerCase()}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      notifications.dismiss(loadingToast);
      notifications.success('PDF descargado', `Horario del ${dayName}`);
    } catch (error) {
      console.error('Error exporting PDF:', error);
      notifications.dismiss(loadingToast);
      notifications.error('Error al exportar PDF', error.message);
    }
  };

  const handleDayChange = (day) => {
    setActiveDay(day);
    setSelectedBusId(null);
    setSelectedRouteId(null);
  };

  const handleBusSelect = (busId) => {
    setSelectedBusId(busId);
    setSelectedRouteId(null);
  };

  const handleRouteSelect = (routeId) => {
    setSelectedRouteId(routeId);
  };

  const handleSaveManualSchedule = async (scheduleData) => {
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

    // Endpoint correcto actual del backend editor.
    // Fallback legacy para compatibilidad con despliegues antiguos.
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
        // 404/405: probamos siguiente endpoint; otros errores sí son terminales.
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
        throw new Error(
          `Horario inválido (${conflictCount} conflictos, ${errorCount} errores).`
        );
      }
      setScheduleByDay((prev) => ({
        ...(prev && typeof prev === 'object' ? prev : createEmptyScheduleByDay()),
        [payload.day]: buildDayScheduleData({
          buses: payload.buses,
          metadata: payload.metadata,
          unassignedRoutes: payload.unassigned_routes,
        }),
      }));
      setActiveDay(payload.day || 'L');
      const requestedMode = payload?.metadata?.mode;
      const nextMode = requestedMode === 'optimize' ? 'optimize' : 'edit';
      setWorkspaceMode(nextMode);
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

  const handlePipelineComplete = useCallback((result) => {
    try {
      applyPipelineResult(result);
      setPipelineStatus('completed');
      setPipelineJobId(null);
      setOptimizing(false);
      notifications.success('Pipeline completado', 'Resultado final cargado');
    } catch (error) {
      notifications.error('Resultado invalido', error.message);
    }
  }, [applyPipelineResult]);

  const handlePipelineError = useCallback((errorCode) => {
    const transientNetworkErrors = new Set(['NETWORK_UNSTABLE']);
    if (transientNetworkErrors.has(String(errorCode || ''))) {
      setPipelineStatus('running');
      setOptimizing(true);
      notifications.warning(
        'Conexion inestable',
        'El backend puede seguir trabajando. Esperando reconexion de progreso.'
      );
      return;
    }

    setPipelineStatus('error');
    setPipelineJobId(null);
    setOptimizing(false);
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
    >
      {/* Sidebar colapsable */}
      <div className={`
        transition-all duration-300 ease-in-out overflow-hidden m-3 h-full
        ${sidebarCollapsed ? 'w-0 opacity-0' : 'w-80 opacity-100'}
      `}>
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

      {/* Boton toggle sidebar */}
      <button
        onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
        className="
          absolute left-0 top-1/2 -translate-y-1/2 z-50
          p-2 bg-[#101a26] border border-[#2c4359] rounded-r-md
          text-slate-400 hover:text-cyan-200 hover:border-cyan-500/40 hover:bg-[#162433]
          transition-all duration-300
          flex items-center justify-center
        "
        style={{
          marginLeft: sidebarCollapsed ? '12px' : '332px',
        }}
        title={sidebarCollapsed ? 'Expandir sidebar' : 'Colapsar sidebar'}
      >
        {sidebarCollapsed ? (
          <PanelLeft className="w-4 h-4" />
        ) : (
          <PanelLeftClose className="w-4 h-4" />
        )}
      </button>

      <section className="flex-1 relative m-3">
        <div className="absolute inset-0 flex flex-col">
          <div className="flex-1 relative overflow-auto">
            {viewMode === 'map' && (
              <>
                <MapView
                  routes={routes}
                  schedule={schedule}
                  selectedBusId={selectedBusId}
                  selectedRouteId={selectedRouteId}
                  onBusSelect={handleBusSelect}
                />

                {routes.length === 0 && (
                  <div className="absolute inset-0 bg-[#07101a]/86 backdrop-blur-sm flex items-center justify-center pointer-events-none rounded-[12px] border border-[#253a4f]">
                    <div className="text-center p-6 control-card rounded-md">
                      <p className="text-[14px] font-semibold text-slate-200 uppercase tracking-[0.12em] data-mono">Mapa Operativo</p>
                      <p className="text-[11px] text-slate-500 mt-1.5 max-w-[220px] uppercase tracking-[0.08em]">
                        Carga datasets para visualizar geometria y rutas
                      </p>
                    </div>
                  </div>
                )}
              </>
            )}
            {viewMode === 'dashboard' && (
              <OperationsDashboard
                routes={routes}
                scheduleByDay={scheduleByDay}
                activeDay={activeDay}
              />
            )}
            {viewMode === 'workspace' && (
              <UnifiedWorkspace
                mode={workspaceMode}
                routes={routes}
                initialSchedule={Array.isArray(schedule) && schedule.length > 0 ? schedule : null}
                scheduleByDay={scheduleByDay}
                activeDay={activeDay}
                validationReport={validationReport}
                onValidationReportChange={setValidationReport}
                onSave={handleSaveManualSchedule}
                onPublish={async (data) => {
                  await handleSaveManualSchedule(data);
                  notifications.success('Horario publicado', 'Los cambios han sido guardados correctamente');
                }}
              />
            )}
            {viewMode === 'fleet' && (
              <FleetPage />
            )}
            {viewMode === 'montecarlo' && (
              <MonteCarloPanel
                schedule={schedule}
                hasOptimizedSchedule={schedule.length > 0 && scheduleByDay !== null}
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

      {/* BusListPanel visible en mapa y montecarlo */}
      {(viewMode === 'map' || viewMode === 'montecarlo') && (
        <div className="my-3 mr-3 min-h-0 flex">
          <BusListPanel
            schedule={schedule}
            routes={routes}
            selectedBusId={selectedBusId}
            selectedRouteId={selectedRouteId}
            onBusSelect={handleBusSelect}
            onRouteSelect={handleRouteSelect}
            onExport={handleExport}
            activeDay={activeDay}
          />
        </div>
      )}
    </Layout>
  );
}

export default App;


