import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Layout from './components/Layout';
import Sidebar from './components/Sidebar';
import { CompareView } from './components/CompareView';
import OptimizationStudio from './components/OptimizationStudio';
import OptimizationProgress from './components/OptimizationProgress';
import StudioErrorBoundary from './components/StudioErrorBoundary';
import ControlHubPage from './pages/ControlHubPage';
import FleetPage from './pages/FleetPage';
import { createUTE, listFleetCompanies, listUTEs } from './services/fleetService';
import { notifications } from './services/notifications';
import { clearGeometryCache } from './services/RouteService';
import { buildRouteCapacityMap, getItemCapacityNeeded } from './utils/capacity';
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
  publishWorkspaceVersion,
  restoreWorkspace,
  saveWorkspaceVersion,
  setWorkspaceOptimizationOptions,
  setLastOpenWorkspace,
  updateWorkspaceCompany,
} from './services/workspaceService';
import { useWorkspaceStudioStore } from './stores/workspaceStudioStore';
import {
  getBlockingReasonText,
  getNextActionLabel,
  getPlanningStageLabels,
  getScopeLabel,
  getWorkspacePendingLabel,
  getWorkspaceReadinessConfig,
  getWorkspaceStatusLabel,
} from './utils/workspaceStatus';

const DAY_LABELS = { L: 'Lunes', M: 'Martes', Mc: 'Miercoles', X: 'Jueves', V: 'Viernes' };
const ALL_DAYS = ['L', 'M', 'Mc', 'X', 'V'];
const DEFAULT_OPTIMIZATION_OPTIONS = {
  balance_load: true,
  load_balance_hard_spread_limit: 2,
  load_balance_target_band: 1,
  route_load_constraints: [],
  fleet_scope_mode: 'company',
  fleet_scope_ute_id: null,
  virtual_bus_publish_policy: 'allow',
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
    fleet_scope_mode: String(source.fleet_scope_mode || 'company').toLowerCase() === 'ute' ? 'ute' : 'company',
    fleet_scope_ute_id: String(source.fleet_scope_ute_id || '').trim() || null,
    virtual_bus_publish_policy: String(source.virtual_bus_publish_policy || 'allow').toLowerCase() === 'block'
      ? 'block'
      : 'allow',
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

const formatMinuteValue = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '-';
  const normalized = Math.max(0, Math.round(numeric));
  const hours = String(Math.floor(normalized / 60)).padStart(2, '0');
  const minutes = String(normalized % 60).padStart(2, '0');
  return `${hours}:${minutes}`;
};

const buildCompanyMixFallback = (items = []) => {
  const counters = new Map();
  (Array.isArray(items) ? items : []).forEach((row) => {
    const suggestions = Array.isArray(row?.suggested_real_vehicles || row?.suggestions)
      ? (row.suggested_real_vehicles || row.suggestions)
      : [];
    if (suggestions.length === 0) return;
    const best = suggestions[0] || {};
    const companyId = String(best.company_id || 'unassigned');
    const companyName = String(best.company_name || 'Empresa sin identificar');
    const current = counters.get(companyId) || {
      company_id: best.company_id || null,
      company_name: companyName,
      recommended_count: 0,
      coverable_assignments: 0,
      candidate_vehicle_count: 0,
      vehicle_codes: [],
    };
    current.recommended_count += 1;
    current.coverable_assignments += 1;
    if (best.vehicle_code && !current.vehicle_codes.includes(best.vehicle_code)) {
      current.vehicle_codes.push(best.vehicle_code);
    }
    current.candidate_vehicle_count = Math.max(current.candidate_vehicle_count, current.vehicle_codes.length);
    counters.set(companyId, current);
  });
  return {
    total_pending_buses: Array.isArray(items) ? items.length : 0,
    recommended_companies: Array.from(counters.values()).sort((a, b) => b.recommended_count - a.recommended_count),
    companies_with_options: counters.size,
    uncovered_buses: Math.max(0, (Array.isArray(items) ? items.length : 0) - counters.size),
  };
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
  title = 'Reglas de optimizacion',
  initialValue = DEFAULT_OPTIMIZATION_OPTIONS,
  uteOptions = [],
  workspaceCompanies = [],
  workspaceCompanyId = null,
  workspaceCompanyChanging = false,
  onWorkspaceCompanyChange = null,
  onCancel,
  onSave,
}) {
  const [value, setValue] = useState(normalizeOptimizationOptions(initialValue));
  const isUteMode = String(value.fleet_scope_mode || 'company') === 'ute';
  const selectedWorkspaceCompany = Array.isArray(workspaceCompanies)
    ? workspaceCompanies.find((company) => String(company.id) === String(workspaceCompanyId || ''))
    : null;
  const selectedUte = Array.isArray(uteOptions)
    ? uteOptions.find((ute) => String(ute.id) === String(value.fleet_scope_ute_id || ''))
    : null;

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

  const applyPreset = (presetId) => {
    if (presetId === 'balanced') {
      setValue((prev) => normalizeOptimizationOptions({
        ...prev,
        balance_load: true,
        load_balance_hard_spread_limit: 2,
        load_balance_target_band: 1,
      }));
      return;
    }
    if (presetId === 'conservative') {
      setValue((prev) => normalizeOptimizationOptions({
        ...prev,
        balance_load: true,
        load_balance_hard_spread_limit: 1,
        load_balance_target_band: 0,
        virtual_bus_publish_policy: 'block',
      }));
      return;
    }
    setValue((prev) => normalizeOptimizationOptions({
      ...prev,
      balance_load: false,
      load_balance_hard_spread_limit: 4,
      load_balance_target_band: 2,
    }));
  };

  return (
    <div className="fixed inset-0 z-[1200] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/85 backdrop-blur-[2px]" onClick={onCancel} />
      <div className="relative w-full max-w-2xl rounded-xl border border-[#2a4057] bg-[#0b141f] p-4 shadow-2xl">
        <h3 className="text-[16px] font-semibold text-white">{title}</h3>
        <p className="mt-1 text-[12px] text-[#8ba3bd]">
          Ajusta como se optimiza la operacion. Lo avanzado sigue disponible, pero aqui queda explicado por categorias.
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => applyPreset('balanced')} className="rounded-full border border-cyan-500/35 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-cyan-100 hover:bg-cyan-500/10">
            Equilibrado
          </button>
          <button type="button" onClick={() => applyPreset('conservative')} className="rounded-full border border-amber-500/35 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-amber-100 hover:bg-amber-500/10">
            Mas conservador
          </button>
          <button type="button" onClick={() => applyPreset('efficient')} className="rounded-full border border-emerald-500/35 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-emerald-100 hover:bg-emerald-500/10">
            Mas eficiencia
          </button>
        </div>

        <div className="mt-4 rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-3">
          <p className="text-[11px] uppercase tracking-[0.1em] text-cyan-300">Empresa principal del workspace</p>
          <div className="mt-2 grid gap-3 md:grid-cols-[1.4fr_0.8fr]">
            <label className="text-[12px] text-slate-200">
              Empresa usada cuando el ambito esta en modo `Empresa`
              <select
                value={workspaceCompanyId || ''}
                onChange={(event) => onWorkspaceCompanyChange?.(event.target.value || null)}
                disabled={workspaceCompanyChanging || workspaceCompanies.length === 0}
                className="mt-1 w-full rounded border border-[#35506a] bg-[#09101d] px-2 py-1.5 text-[12px] text-white disabled:opacity-60"
              >
                <option value="">Selecciona empresa</option>
                {workspaceCompanies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name} ({company.active_vehicle_count || 0} buses activos)
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[10px] text-slate-400">
                Si aqui apuntas a una empresa sin buses, la asignacion real no encontrara candidatos.
              </p>
            </label>
            <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[11px] text-slate-300">
              <p className="uppercase tracking-[0.08em] text-slate-500">Consejo</p>
              <p className="mt-2 leading-5">
                Si vas a trabajar con socios, cambia el ambito a `UTE`. Si trabajas solo con una empresa, asegurate de elegir aqui la que tenga la flota cargada.
              </p>
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] uppercase tracking-[0.1em] text-cyan-300">Como quieres trabajar esta optimizacion</p>
              <p className="mt-1 text-[12px] text-slate-300">
                Elige una opcion simple: solo tu empresa o toda la UTE.
              </p>
            </div>
            <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[11px] text-slate-300">
              Ahora mismo: {isUteMode ? 'Toda la UTE' : 'Solo mi empresa'}
            </div>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <button
              type="button"
              onClick={() => setValue((prev) => ({
                ...normalizeOptimizationOptions(prev),
                fleet_scope_mode: 'company',
                fleet_scope_ute_id: null,
              }))}
              className={`rounded-xl border px-4 py-4 text-left transition ${
                !isUteMode
                  ? 'border-cyan-400/60 bg-cyan-500/10'
                  : 'border-[#2a4057] bg-[#09101d] hover:border-cyan-500/30'
              }`}
            >
              <p className="text-[14px] font-semibold text-white">Solo mi empresa</p>
              <p className="mt-1 text-[12px] text-slate-300">
                Usar solo los buses de mi empresa principal.
              </p>
              <p className="mt-2 text-[11px] text-slate-400">
                Empresa actual: {selectedWorkspaceCompany
                  ? `${selectedWorkspaceCompany.name} (${selectedWorkspaceCompany.active_vehicle_count || 0} buses activos)`
                  : 'Selecciona una empresa principal arriba'}
              </p>
            </button>

            <button
              type="button"
              onClick={() => setValue((prev) => ({
                ...normalizeOptimizationOptions(prev),
                fleet_scope_mode: 'ute',
                fleet_scope_ute_id: prev.fleet_scope_ute_id || (uteOptions[0]?.id || null),
              }))}
              className={`rounded-xl border px-4 py-4 text-left transition ${
                isUteMode
                  ? 'border-emerald-400/60 bg-emerald-500/10'
                  : 'border-[#2a4057] bg-[#09101d] hover:border-emerald-500/30'
              }`}
            >
              <p className="text-[14px] font-semibold text-white">Toda la UTE</p>
              <p className="mt-1 text-[12px] text-slate-300">
                Usar AAV y tambien las empresas socias de la UTE.
              </p>
              <p className="mt-2 text-[11px] text-slate-400">
                UTE seleccionada: {selectedUte?.name || (uteOptions[0]?.name || 'Selecciona una UTE abajo')}
              </p>
            </button>
          </div>
          <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[11px] text-slate-300">
            {!isUteMode
              ? 'Usa esta opcion si quieres optimizar solo con los buses de AAV.'
              : 'Usa esta opcion si quieres mezclar buses de AAV con AUTNA, ESTEVEZ, MELYTOUR y el resto de socios.'}
          </div>
        </div>

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
            Diferencia maxima entre buses
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
            <p className="mt-1 text-[10px] text-slate-400">
              Ejemplo: 2 = el bus con mas rutas solo puede tener 2 rutas mas que el bus con menos rutas.
            </p>
          </label>
          <label className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
            Margen alrededor del reparto ideal (+/-)
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
            <p className="mt-1 text-[10px] text-slate-400">
              Cuanto puede alejarse cada bus del numero ideal de rutas.
            </p>
          </label>
        </div>

        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
            Grupo UTE a usar
            <select
              value={value.fleet_scope_ute_id || ''}
              disabled={!isUteMode}
              onChange={(event) => setValue((prev) => ({
                ...normalizeOptimizationOptions(prev),
                fleet_scope_ute_id: event.target.value || null,
              }))}
              className="mt-1 w-full rounded border border-[#35506a] bg-[#09101d] px-2 py-1 text-[12px] text-white disabled:opacity-60"
            >
              <option value="">Selecciona UTE</option>
              {uteOptions.map((ute) => (
                <option key={ute.id} value={ute.id}>{ute.name}</option>
              ))}
            </select>
            <p className="mt-1 text-[10px] text-slate-400">
              Solo hace falta cuando eliges "Toda la UTE".
            </p>
          </label>
          <label className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
            Politica de publicacion
            <select
              value={value.virtual_bus_publish_policy || 'allow'}
              onChange={(event) => setValue((prev) => ({
                ...normalizeOptimizationOptions(prev),
                virtual_bus_publish_policy: event.target.value === 'block' ? 'block' : 'allow',
              }))}
              className="mt-1 w-full rounded border border-[#35506a] bg-[#09101d] px-2 py-1 text-[12px] text-white"
            >
              <option value="allow">Permitir con aviso</option>
              <option value="block">Bloquear hasta reconciliar</option>
            </select>
            <p className="mt-1 text-[10px] text-slate-400">
              Recomendado en produccion: bloquear y reasignar virtuales a buses reales antes de publicar.
            </p>
          </label>
        </div>

        <div className="mt-4 rounded-lg border border-[#2a4057] bg-[#0a1324] p-3">
          <div className="flex items-center justify-between">
            <p className="text-[11px] uppercase tracking-[0.1em] text-cyan-300">Limites horarios</p>
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
                Sin limites horarios extra. Puedes usar por ejemplo 07:30-09:30 max 3 rutas.
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
            Guardar reglas
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
          Quieres revisar las reglas de optimizacion para <span className="text-white font-semibold">{label}</span> antes de generar la planificacion?
        </p>
        <p className="mt-1 text-[11px] text-slate-400">
          Si guardas reglas ahora, esta corrida se ejecuta directamente con esa configuracion.
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
            Revisar reglas
          </button>
        </div>
      </div>
    </div>
  );
}

function PublicationStatusCard({ title, value, tone = 'neutral', helper = '', compact = false }) {
  const toneClass = {
    success: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100',
    warning: 'border-amber-500/25 bg-amber-500/10 text-amber-100',
    danger: 'border-rose-500/25 bg-rose-500/10 text-rose-100',
    neutral: 'border-white/10 bg-white/[0.03] text-slate-100',
  }[tone] || 'border-white/10 bg-white/[0.03] text-slate-100';

  return (
    <div className={`rounded-xl border ${compact ? 'px-3 py-2.5' : 'px-3 py-3'} ${toneClass}`}>
      <p className="text-[10px] uppercase tracking-[0.1em] opacity-80">{title}</p>
      <p className={`mt-1 font-semibold data-mono ${compact ? 'text-[16px]' : 'text-[18px]'}`}>{value}</p>
      {helper ? <p className={`mt-1 opacity-80 ${compact ? 'text-[10px]' : 'text-[11px]'}`}>{helper}</p> : null}
    </div>
  );
}

function PlanningOverviewBar({
  workspace = null,
  activeDay = 'L',
  stats = null,
  scheduleByDay = null,
  onOpenReconciliation,
  onOpenRules,
  optimizationOptions = null,
  workspaceCompanies = [],
}) {
  if (!workspace) return null;

  const [isExpanded, setIsExpanded] = useState(false);
  const readiness = getWorkspaceReadinessConfig(workspace.readiness_state);
  const pendingLabel = getWorkspacePendingLabel(workspace);
  const nextActionLabel = getNextActionLabel(workspace.next_recommended_action);
  const blockingText = getBlockingReasonText(workspace.blocking_reason);
  const stageItems = getPlanningStageLabels(workspace);
  const activeDaySchedule = Array.isArray(scheduleByDay?.[activeDay]?.schedule)
    ? scheduleByDay[activeDay].schedule
    : [];
  const activeDayFleetReal = activeDaySchedule.filter((bus) => String(bus?.fleet_assignment_type || '').toLowerCase() === 'real').length;
  const activeDayFleetVirtual = activeDaySchedule.filter((bus) => String(bus?.fleet_assignment_type || '').toLowerCase() !== 'real').length;
  const fleetReal = activeDayFleetReal;
  const fleetVirtual = activeDayFleetVirtual;
  const weekFleetVirtual = Number(workspace?.pending_virtual_count ?? workspace?.summary_metrics?.fleet_virtual_created ?? 0);
  const scopeLabel = getScopeLabel(workspace.scope_summary);
  const hasConflict = Number(workspace?.conflict_count || 0) > 0;
  const routeRulesCount = Array.isArray(optimizationOptions?.route_load_constraints)
    ? optimizationOptions.route_load_constraints.filter((row) => row?.enabled !== false).length
    : 0;
  const currentCompany = Array.isArray(workspaceCompanies)
    ? workspaceCompanies.find((company) => String(company.id) === String(workspace?.company_id || ''))
    : null;
  const companyScopeWithoutFleet = (
    String(optimizationOptions?.fleet_scope_mode || 'company') !== 'ute'
    && currentCompany
    && Number(currentCompany.active_vehicle_count || 0) === 0
  );
  const primaryActionLabel = fleetVirtual > 0 ? 'Reconciliar flota' : 'Abrir reglas';
  const primaryActionHandler = fleetVirtual > 0 ? onOpenReconciliation : onOpenRules;

  return (
    <div className="mb-2 rounded-[18px] border border-[#304a62] bg-[#0d1623]/95 px-3 py-2.5">
      <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[10px] uppercase tracking-[0.16em] text-cyan-300/90 data-mono">Planificacion</p>
            <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] ${readiness.chipClass}`}>
              {readiness.label}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] text-slate-200">
              {scopeLabel}
            </span>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px]">
            <span className="text-[22px] font-semibold text-white leading-none" style={{ fontFamily: 'Sora, IBM Plex Sans, Segoe UI, sans-serif' }}>
              {workspace.name || 'Optimizacion activa'}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-slate-200">
              {DAY_LABELS[activeDay] || activeDay}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-slate-200">
              {stats?.buses ?? 0} buses
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-slate-200">
              {stats?.routes ?? 0} rutas
            </span>
            <span className={`rounded-full border px-2.5 py-1 ${fleetVirtual > 0 ? 'border-amber-500/25 bg-amber-500/10 text-amber-100' : 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100'}`}>
              {fleetVirtual} provisionales hoy
            </span>
            {hasConflict ? (
              <span className="rounded-full border border-rose-500/25 bg-rose-500/10 px-2.5 py-1 text-rose-100">
                {workspace?.conflict_count ?? 0} conflictos
              </span>
            ) : null}
            <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 text-cyan-100">
              Siguiente: {nextActionLabel}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400 truncate">
            Pendiente principal: {pendingLabel.toLowerCase()}.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 xl:justify-end">
          <button
            type="button"
            onClick={primaryActionHandler}
            className={`rounded-md px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] ${
              fleetVirtual > 0
                ? 'border border-amber-500/35 text-amber-100 hover:bg-amber-500/10'
                : 'border border-cyan-500/35 text-cyan-100 hover:bg-cyan-500/10'
            }`}
          >
            {primaryActionLabel}
          </button>
          <button
            type="button"
            onClick={() => setIsExpanded((prev) => !prev)}
            className="rounded-md border border-white/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-100 hover:bg-white/5"
          >
            {isExpanded ? 'Ocultar' : 'Detalle'}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="mt-3 rounded-xl border border-white/10 bg-[#09111b] p-3 space-y-3">
          {blockingText ? (
            <p className="text-[12px] text-amber-100">{blockingText}</p>
          ) : null}
          {companyScopeWithoutFleet ? (
            <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-100">
              La empresa principal actual del workspace es <span className="font-semibold">{currentCompany?.name}</span> y tiene 0 buses activos. Cambia la empresa principal o usa modo UTE para que la flota real aparezca en la asignacion.
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {stageItems.map((item) => (
              <div key={item.key} className="flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${item.done ? 'bg-emerald-400' : (item.active ? 'bg-cyan-300' : 'bg-slate-600')}`} />
                <span className={`text-[11px] ${item.done ? 'text-slate-100' : (item.active ? 'text-cyan-100' : 'text-slate-500')}`}>
                  {item.label}
                </span>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onOpenRules}
              className="rounded-md border border-cyan-500/35 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-cyan-100 hover:bg-cyan-500/10"
            >
              Reglas de optimizacion
            </button>
            {fleetVirtual > 0 && (
              <button
                type="button"
                onClick={onOpenReconciliation}
                className="rounded-md border border-amber-500/35 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-100 hover:bg-amber-500/10"
              >
                Reconciliar flota
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 xl:grid-cols-4">
            <PublicationStatusCard title="Flota real hoy" value={fleetReal} tone="success" helper="Buses reales del dia activo." compact />
            <PublicationStatusCard title="Estado de publicacion" value={readiness.label} helper="Resumen del estado operativo actual." compact />
            <PublicationStatusCard title="Provisionales hoy" value={fleetVirtual} tone={fleetVirtual > 0 ? 'warning' : 'success'} helper={weekFleetVirtual > fleetVirtual ? `Semana completa: ${weekFleetVirtual}` : (fleetVirtual > 0 ? 'Requieren asignacion real antes de publicar.' : 'No quedan pendientes.')} compact />
            <PublicationStatusCard title="Conflictos reales" value={workspace?.conflict_count ?? 0} tone={hasConflict ? 'danger' : 'success'} helper={hasConflict ? 'Hay una colision real con otra publicacion.' : 'No hay bloqueos detectados.'} compact />
          </div>

          <div className="rounded-xl border border-white/10 bg-[#0d1623]/70 p-3">
            <p className="text-[10px] uppercase tracking-[0.1em] text-slate-500">Reglas activas</p>
            <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Ambito: {optimizationOptions?.fleet_scope_mode === 'ute' ? 'UTE' : 'Empresa'}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Balanceo: {optimizationOptions?.balance_load === false ? 'Flexible' : 'Activo'}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Diferencia max: {optimizationOptions?.load_balance_hard_spread_limit ?? 2}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Ventanas: {routeRulesCount}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-slate-200">
                Publicacion: {optimizationOptions?.virtual_bus_publish_policy === 'block' ? 'Bloquear provisionales' : 'Permitir con aviso'}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
            <span className="rounded-md border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-cyan-100">Ruta</span>
            <span className="rounded-md border border-slate-500/20 bg-slate-500/10 px-2 py-1 text-slate-200">Posicionamiento</span>
            <span className="rounded-md border border-rose-500/20 bg-rose-500/10 px-2 py-1 text-rose-100">Conflicto</span>
            <span className="rounded-md border border-amber-500/20 bg-amber-500/10 px-2 py-1 text-amber-100">Bus provisional</span>
            <span className="rounded-md border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-cyan-100">Bus publicado</span>
          </div>
        </div>
      )}
    </div>
  );
}

function FleetConflictModal({
  open = false,
  conflicts = [],
  onClose,
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[1260] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/85 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative w-full max-w-2xl rounded-xl border border-rose-500/35 bg-[#0b141f] p-4 shadow-2xl">
        <h3 className="text-[16px] font-semibold text-white">Publicacion bloqueada por conflicto de flota</h3>
        <p className="mt-2 text-[12px] text-[#8ba3bd]">
          Hay autobuses reales reservados en otras optimizaciones publicadas en el mismo tramo horario.
        </p>
        <div className="mt-3 max-h-[320px] overflow-auto rounded-md border border-[#2a4057]">
          <table className="w-full text-[11px]">
            <thead className="bg-[#101a26] text-slate-400">
              <tr>
                <th className="px-2 py-1.5 text-left">Dia</th>
                <th className="px-2 py-1.5 text-left">Vehiculo</th>
                <th className="px-2 py-1.5 text-left">Ruta candidata</th>
                <th className="px-2 py-1.5 text-left">Planificacion en conflicto</th>
              </tr>
            </thead>
            <tbody>
              {conflicts.map((conflict, idx) => (
                <tr key={`${conflict?.vehicle_id || 'v'}-${idx}`} className="border-t border-[#253a4f]">
                  <td className="px-2 py-1.5 text-slate-200">{conflict?.day || '-'}</td>
                  <td className="px-2 py-1.5 text-rose-200 data-mono">{conflict?.vehicle_id || '-'}</td>
                  <td className="px-2 py-1.5 text-slate-200 data-mono">{conflict?.candidate_route_id || '-'}</td>
                  <td className="px-2 py-1.5 text-slate-400 data-mono">{conflict?.conflicting_workspace_id || '-'}</td>
                </tr>
              ))}
              {conflicts.length === 0 && (
                <tr>
                  <td className="px-2 py-3 text-center text-slate-500" colSpan={4}>Sin detalle de conflictos.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-[#2a4057] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9eb2c8] transition hover:bg-white/5"
          >
            Entendido
          </button>
        </div>
      </div>
    </div>
  );
}

function FleetReconciliationModal({
  open = false,
  items = [],
  companyMix = null,
  requiredBusCount = 0,
  realBoundCount = 0,
  pendingRealReconciliationCount = 0,
  availableRealVehicleCount = 0,
  companiesAvailable = 0,
  estimatedVirtualRemaining = 0,
  reconciliationSnapshot = null,
  dayLabel = '',
  scopeLabel = '',
  scopeVehicleCount = 0,
  scopeMode = 'company',
  busId = null,
  applying = false,
  onApply = null,
  onClose,
}) {
  const effectiveCompanyMix = useMemo(() => (
    companyMix && typeof companyMix === 'object'
      ? companyMix
      : buildCompanyMixFallback(items)
  ), [companyMix, items]);
  const recommendedCompanies = useMemo(() => (
    Array.isArray(effectiveCompanyMix?.recommended_companies)
      ? effectiveCompanyMix.recommended_companies
      : []
  ), [effectiveCompanyMix]);
  const totalPendingBuses = Number(
    pendingRealReconciliationCount
    || effectiveCompanyMix?.total_pending_buses
    || items.length
    || 0
  );
  const uncoveredBuses = Number(
    estimatedVirtualRemaining
    || effectiveCompanyMix?.uncovered_buses
    || 0
  );
  const modalTitle = busId
    ? `Asignacion recomendada para ${busId}`
    : 'Asignacion recomendada de buses reales';
  const [allocationByCompany, setAllocationByCompany] = useState({});
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [preferredCompanyByBus, setPreferredCompanyByBus] = useState({});
  const [selectedVehicleByBus, setSelectedVehicleByBus] = useState({});
  const [excludedVehicleIdsByBus, setExcludedVehicleIdsByBus] = useState({});

  useEffect(() => {
    if (!open) return;
    const nextState = {};
    const snapshotAllocations = Array.isArray(reconciliationSnapshot?.company_allocations)
      ? reconciliationSnapshot.company_allocations
      : [];
    snapshotAllocations.forEach((company) => {
      const key = String(company?.company_id || 'unassigned');
      nextState[key] = Number(company?.count || 0);
    });
    recommendedCompanies.forEach((company) => {
      const key = String(company?.company_id || 'unassigned');
      if (typeof nextState[key] === 'undefined') {
        nextState[key] = Number(company?.recommended_count || 0);
      }
    });
    setAllocationByCompany(nextState);
    setPreferredCompanyByBus({});
    setSelectedVehicleByBus({});
    setExcludedVehicleIdsByBus({});
    setDetailsOpen(Boolean(busId));
  }, [busId, open, recommendedCompanies, reconciliationSnapshot]);

  if (!open) return null;

  const totalAssigned = Object.values(allocationByCompany).reduce((sum, value) => sum + Math.max(0, Number(value) || 0), 0);
  const remainingToDistribute = Math.max(0, totalPendingBuses - totalAssigned);
  const primaryRecommendation = recommendedCompanies[0] || null;
  const handleAllocationChange = (companyId, nextValue) => {
    const normalizedKey = String(companyId || 'unassigned');
    const parsed = Number.parseInt(nextValue, 10);
    setAllocationByCompany((prev) => ({
      ...prev,
      [normalizedKey]: Number.isFinite(parsed) ? Math.max(0, parsed) : 0,
    }));
  };
  const handlePreferredCompanyChange = (rowKey, companyId) => {
    setPreferredCompanyByBus((prev) => ({
      ...prev,
      [rowKey]: companyId || '',
    }));
    setSelectedVehicleByBus((prev) => ({
      ...prev,
      [rowKey]: '',
    }));
  };
  const handleVehicleSelectionChange = (rowKey, vehicleId, candidates = []) => {
    const normalizedVehicleId = String(vehicleId || '').trim();
    setSelectedVehicleByBus((prev) => ({
      ...prev,
      [rowKey]: normalizedVehicleId,
    }));
    if (!normalizedVehicleId) return;
    const selectedCandidate = (Array.isArray(candidates) ? candidates : []).find(
      (candidate) => String(candidate?.vehicle_id || '') === normalizedVehicleId
    );
    if (selectedCandidate?.company_id) {
      setPreferredCompanyByBus((prev) => ({
        ...prev,
        [rowKey]: String(selectedCandidate.company_id),
      }));
    }
  };
  const handleToggleExcludedVehicle = (rowKey, vehicleId) => {
    const normalizedVehicleId = String(vehicleId || '').trim();
    if (!normalizedVehicleId) return;
    setExcludedVehicleIdsByBus((prev) => {
      const current = Array.isArray(prev[rowKey]) ? prev[rowKey] : [];
      const exists = current.includes(normalizedVehicleId);
      const next = exists
        ? current.filter((value) => value !== normalizedVehicleId)
        : [...current, normalizedVehicleId];
      return {
        ...prev,
        [rowKey]: next,
      };
    });
    setSelectedVehicleByBus((prev) => (
      String(prev[rowKey] || '') === normalizedVehicleId
        ? { ...prev, [rowKey]: '' }
        : prev
    ));
  };
  const handleApply = () => {
    if (typeof onApply !== 'function') return;
    const payload = recommendedCompanies.map((company) => ({
      company_id: company?.company_id || null,
      count: Math.max(0, Number(allocationByCompany[String(company?.company_id || 'unassigned')] || 0)),
    }));
    const busSelections = (Array.isArray(items) ? items : []).map((row) => {
      const rowKey = `${row?.day || ''}::${row?.bus_id || ''}`;
      const companyId = String(preferredCompanyByBus[rowKey] || '').trim();
      const vehicleId = String(selectedVehicleByBus[rowKey] || '').trim();
      const excludedVehicleIds = Array.isArray(excludedVehicleIdsByBus[rowKey])
        ? excludedVehicleIdsByBus[rowKey].filter(Boolean)
        : [];
      if (!companyId && !vehicleId && excludedVehicleIds.length === 0) return null;
      return {
        day: row?.day || null,
        bus_id: row?.bus_id || '',
        company_id: companyId || null,
        vehicle_id: vehicleId || null,
        excluded_vehicle_ids: excludedVehicleIds,
      };
    }).filter(Boolean);
    onApply(payload, busSelections);
  };

  return (
    <div className="fixed inset-0 z-[1265] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/85 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative flex max-h-[92vh] w-full max-w-5xl flex-col rounded-xl border border-amber-500/35 bg-[#0b141f] p-4 shadow-2xl">
        <h3 className="text-[16px] font-semibold text-white">{modalTitle}</h3>
        <p className="mt-2 text-[12px] text-[#8ba3bd]">
          {busId
            ? 'Este bus provisional necesita una propuesta de empresa y un candidato real para cerrar la operacion.'
            : `La operacion del ${dayLabel ? dayLabel.toLowerCase() : 'dia'} usa ${Number(requiredBusCount || 0)} buses. Aqui decides cuantos cubres con flota real y de que empresa salen${scopeLabel ? ` dentro de ${scopeLabel}` : ''}.`}
        </p>
        {scopeMode === 'company' && Number(scopeVehicleCount || 0) === 0 && (
          <div className="mt-3 rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-100">
            Esta optimizacion esta en modo Empresa, pero la empresa principal actual no tiene buses activos dentro del ambito usado. Cambia la empresa principal del workspace o pasa a modo UTE.
          </div>
        )}
        <div className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
          <section className="rounded-xl border border-[#2a4057] bg-[#0d1724] p-4">
            <div className="grid gap-3 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.06] p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-cyan-200">Lectura rapida</p>
                <p className="mt-3 text-[22px] font-semibold text-white">
                  La operacion usa {Number(requiredBusCount || 0)} buses
                </p>
                <p className="mt-2 text-[13px] leading-6 text-slate-300">
                  {totalPendingBuses > 0
                    ? (
                      primaryRecommendation
                        ? `Ya hay ${Number(realBoundCount || 0)} cubiertos con real. Te falta decidir ${totalPendingBuses} buses y la propuesta inicial empieza por ${primaryRecommendation.company_name || 'la empresa principal'}.`
                        : `Ya hay ${Number(realBoundCount || 0)} cubiertos con real. Te falta decidir ${totalPendingBuses} buses y no hay una empresa claramente dominante.`
                    )
                    : `No quedan pendientes de asignacion real. Puedes revisar el reparto o cerrar la reconciliacion.`}
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-2">
                <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-slate-400">Operacion del dia</p>
                  <p className="mt-1 text-[26px] font-semibold text-white">{Number(requiredBusCount || 0)}</p>
                </div>
                <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-slate-400">Ya cubiertos con real</p>
                  <p className="mt-1 text-[26px] font-semibold text-emerald-200">{Number(realBoundCount || 0)}</p>
                </div>
                <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-slate-400">Pendientes de asignar</p>
                  <p className="mt-1 text-[26px] font-semibold text-white">{totalPendingBuses}</p>
                </div>
                <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-slate-400">Flota disponible en alcance</p>
                  <p className="mt-1 text-[26px] font-semibold text-cyan-200">{Number(availableRealVehicleCount || scopeVehicleCount || 0)}</p>
                </div>
                <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-slate-400">Empresas disponibles</p>
                  <p className="mt-1 text-[26px] font-semibold text-cyan-200">{Number(companiesAvailable || effectiveCompanyMix?.companies_with_options || 0)}</p>
                </div>
                <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-slate-400">Provisionales si no completas</p>
                  <p className="mt-1 text-[26px] font-semibold text-amber-200">{uncoveredBuses}</p>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-[#2a4057] bg-[#0d1724] p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8ba3bd]">Reparto por empresa</p>
                <p className="mt-1 text-[12px] text-slate-400">
                  Indica cuantos buses reales quieres sacar de cada empresa. El sistema intentara respetar este reparto en los pendientes.
                </p>
                <p className="mt-1 text-[11px] text-slate-500">
                  Operacion total: {Number(requiredBusCount || 0)}. Ya cubiertos: {Number(realBoundCount || 0)}. Te falta repartir: {totalPendingBuses}.
                </p>
              </div>
              <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[11px] text-slate-300">
                Total configurado: {totalAssigned}
              </div>
            </div>
            {totalPendingBuses > 0 && totalAssigned !== totalPendingBuses && (
              <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-100">
                {totalAssigned < totalPendingBuses
                  ? `Todavia faltan ${totalPendingBuses - totalAssigned} buses por repartir entre empresas.`
                  : `Hay ${totalAssigned - totalPendingBuses} buses de mas en el reparto. Ajusta los conteos si quieres un reparto exacto.`}
              </div>
            )}
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {recommendedCompanies.length > 0 ? recommendedCompanies.map((company) => (
                <div key={`${company.company_id || company.company_name}`} className="rounded-xl border border-[#2a4057] bg-[#0a1320] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[15px] font-semibold text-white">{company.company_name || 'Empresa sin identificar'}</p>
                      <p className="mt-1 text-[12px] text-slate-400">
                        Recomendacion inicial: {company.recommended_count || 0} bus{Number(company.recommended_count || 0) === 1 ? '' : 'es'}
                      </p>
                    </div>
                    <div className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold text-cyan-200">
                      {company.recommended_count || 0}
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-400">
                    <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
                      Cubre {company.coverable_assignments || 0} asignaciones
                    </div>
                    <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
                      {company.candidate_vehicle_count || 0} vehiculos candidatos
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between gap-3">
                    <label className="text-[12px] text-slate-300">
                      Buses a tomar de esta empresa
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={allocationByCompany[String(company.company_id || 'unassigned')] ?? 0}
                      onChange={(event) => handleAllocationChange(company.company_id, event.target.value)}
                      className="w-24 rounded-lg border border-[#2a4057] bg-[#08111b] px-3 py-2 text-right text-[13px] text-white outline-none focus:border-cyan-400"
                    />
                  </div>
                  {Array.isArray(company.vehicle_codes) && company.vehicle_codes.length > 0 && (
                    <p className="mt-3 text-[11px] text-slate-400">
                      Ejemplos de apoyo: {company.vehicle_codes.join(', ')}
                    </p>
                  )}
                </div>
              )) : (
                <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-[12px] text-amber-100 md:col-span-2">
                  No hay una recomendacion clara por empresa porque no se encontraron candidatos reales libres.
                </div>
              )}
            </div>
          </section>

          <section className="rounded-xl border border-[#2a4057] bg-[#0d1724] p-4">
            <button
              type="button"
              onClick={() => setDetailsOpen((prev) => !prev)}
              className="flex w-full items-center justify-between gap-3 text-left"
            >
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8ba3bd]">Detalle por bus</p>
                <p className="mt-1 text-[12px] text-slate-400">
                  {detailsOpen
                    ? 'Oculta el detalle tecnico si ya tienes clara la decision.'
                    : `Ver detalle de los ${items.length} buses pendientes de asignacion real.`}
                </p>
              </div>
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[11px] text-slate-300">
                {detailsOpen ? 'Ocultar' : 'Ver detalle'}
              </span>
            </button>
            {detailsOpen && (
              <div className="mt-4 grid gap-3">
                {items.map((row, idx) => {
                  const candidates = Array.isArray(row?.suggested_real_vehicles || row?.suggestions)
                    ? (row?.suggested_real_vehicles || row?.suggestions)
                    : [];
                  const rowKey = `${row?.day || ''}::${row?.bus_id || ''}`;
                  const preferredCompanyId = String(preferredCompanyByBus[rowKey] || '').trim();
                  const excludedVehicleIds = Array.isArray(excludedVehicleIdsByBus[rowKey])
                    ? excludedVehicleIdsByBus[rowKey]
                    : [];
                  const companyOptions = Array.from(new Map(
                    candidates.map((candidate) => [
                      String(candidate?.company_id || 'unassigned'),
                      {
                        company_id: candidate?.company_id || null,
                        company_name: candidate?.company_name || 'Empresa sin identificar',
                      },
                    ])
                  ).values());
                  const filteredCandidates = candidates.filter((candidate) => {
                    const candidateVehicleId = String(candidate?.vehicle_id || '');
                    if (excludedVehicleIds.includes(candidateVehicleId)) return false;
                    if (preferredCompanyId && String(candidate?.company_id || 'unassigned') !== preferredCompanyId) return false;
                    return true;
                  });
                  const bestCandidate = candidates[0] || null;
                  return (
                    <div key={`${row?.day || 'D'}-${row?.bus_id || 'BUS'}-${idx}`} className="rounded-xl border border-[#2a4057] bg-[#0a1320] p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-amber-100">
                          {row?.bus_id || '-'}
                        </span>
                        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] text-slate-300">
                          {row?.day || '-'}
                        </span>
                        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] text-slate-300">
                          {formatMinuteValue(row?.time_window?.start_minute ?? row?.start_minute)} - {formatMinuteValue(row?.time_window?.end_minute ?? row?.end_minute)}
                        </span>
                        <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 text-[10px] text-cyan-100">
                          {row?.required_capacity ?? row?.required_seats ?? '-'} plazas
                        </span>
                      </div>
                      <p className="mt-3 text-[12px] text-slate-300">
                        Empresa recomendada: <span className="font-semibold text-white">{bestCandidate?.company_name || 'Sin recomendacion'}</span>
                      </p>
                      <p className="mt-1 text-[11px] text-slate-400">
                        Candidatos: {candidates.length > 0
                          ? candidates.slice(0, 3).map((candidate) => `${candidate.vehicle_code || candidate.vehicle_id} / ${candidate.company_name || 'Empresa'} (${candidate.seats_max}P)`).join(', ')
                          : 'Sin sugerencias libres'}
                      </p>
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <label className="text-[11px] text-slate-300">
                          Empresa preferida para este provisional
                          <select
                            value={preferredCompanyId}
                            onChange={(event) => handlePreferredCompanyChange(rowKey, event.target.value)}
                            className="mt-1 w-full rounded-lg border border-[#2a4057] bg-[#08111b] px-3 py-2 text-[12px] text-white outline-none focus:border-cyan-400"
                          >
                            <option value="">Automatico segun recomendacion</option>
                            {companyOptions.map((company) => (
                              <option key={`${rowKey}-${company.company_id || 'unassigned'}`} value={company.company_id || 'unassigned'}>
                                {company.company_name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="text-[11px] text-slate-300">
                          Bus real exacto
                          <select
                            value={String(selectedVehicleByBus[rowKey] || '')}
                            onChange={(event) => handleVehicleSelectionChange(rowKey, event.target.value, filteredCandidates)}
                            className="mt-1 w-full rounded-lg border border-[#2a4057] bg-[#08111b] px-3 py-2 text-[12px] text-white outline-none focus:border-cyan-400"
                          >
                            <option value="">Que el sistema lo elija</option>
                            {filteredCandidates.map((candidate) => (
                              <option key={`${rowKey}-${candidate.vehicle_id}`} value={candidate.vehicle_id}>
                                {(candidate.vehicle_code || candidate.vehicle_id)} · {candidate.company_name || 'Empresa'} · {candidate.seats_max}P
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      {candidates.length > 0 && (
                        <div className="mt-4">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">Candidatos visibles</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {candidates.map((candidate) => {
                              const candidateVehicleId = String(candidate?.vehicle_id || '');
                              const blocked = excludedVehicleIds.includes(candidateVehicleId);
                              return (
                                <button
                                  key={`${rowKey}-${candidateVehicleId}-toggle`}
                                  type="button"
                                  onClick={() => handleToggleExcludedVehicle(rowKey, candidateVehicleId)}
                                  className={`rounded-full border px-2.5 py-1 text-[10px] transition ${
                                    blocked
                                      ? 'border-rose-500/30 bg-rose-500/10 text-rose-100'
                                      : 'border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]'
                                  }`}
                                >
                                  {blocked ? 'Descartado' : 'Disponible'}: {candidate.vehicle_code || candidate.vehicle_id}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
                {items.length === 0 && (
                  <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 text-[12px] text-slate-500">
                    No hay buses pendientes de asignacion real en este dia.
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/10 pt-3">
          <div className="text-[11px] text-slate-400">
            {totalPendingBuses > 0
              ? (
                remainingToDistribute > 0
                  ? `Quedan ${remainingToDistribute} buses sin repartir. Si aplicas ahora, el sistema intentara completar el resto con la mejor opcion disponible.`
                  : 'La propuesta queda lista para aplicarse en el workspace.'
              )
              : 'No quedan pendientes. Puedes cerrar o revisar el detalle de lo ya asignado.'}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-[#2a4057] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9eb2c8] transition hover:bg-white/5"
              disabled={applying}
            >
              Cerrar
            </button>
            <button
              type="button"
              onClick={handleApply}
              disabled={applying || (items.length === 0 && totalPendingBuses > 0)}
              className="rounded-md border border-cyan-500/35 bg-cyan-500/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {applying ? 'Aplicando...' : (totalPendingBuses > 0 ? 'Aplicar propuesta' : 'Revisar reparto')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function FleetScopeChoiceModal({
  open = false,
  workspaceCompany = null,
  fleetCompanies = [],
  uteOptions = [],
  applying = false,
  onChooseCompany = null,
  onChooseUte = null,
  onClose = null,
}) {
  if (!open) return null;
  const firstUte = Array.isArray(uteOptions) && uteOptions.length > 0 ? uteOptions[0] : null;
  const canInferUte = !firstUte && Array.isArray(fleetCompanies) && fleetCompanies.length > 1 && workspaceCompany;
  return (
    <div className="fixed inset-0 z-[1264] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/85 backdrop-blur-[2px]" onClick={applying ? undefined : onClose} />
      <div className="relative w-full max-w-3xl rounded-xl border border-cyan-500/25 bg-[#0b141f] p-5 shadow-2xl">
        <p className="text-[11px] uppercase tracking-[0.1em] text-cyan-300">Reconciliar flota</p>
        <h3 className="mt-2 text-[24px] font-semibold text-white">Elige con que flota quieres trabajar</h3>
        <p className="mt-2 text-[13px] text-slate-300">
          Antes de asignar buses reales, dime si esta optimizacion debe usar solo tu empresa o toda la UTE.
        </p>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <button
            type="button"
            onClick={onChooseCompany}
            disabled={applying}
            className="rounded-xl border border-cyan-500/35 bg-cyan-500/10 px-4 py-4 text-left transition hover:bg-cyan-500/15 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <p className="text-[15px] font-semibold text-white">Solo mi empresa</p>
            <p className="mt-1 text-[12px] text-slate-300">
              Usar solo la flota propia para esta reconciliacion.
            </p>
            <p className="mt-2 text-[11px] text-slate-400">
              Empresa actual: {workspaceCompany
                ? `${workspaceCompany.name} (${workspaceCompany.active_vehicle_count || 0} buses activos)`
                : 'No hay empresa principal seleccionada'}
            </p>
          </button>
          <button
            type="button"
            onClick={onChooseUte}
            disabled={applying || (!firstUte && !canInferUte)}
            className="rounded-xl border border-emerald-500/35 bg-emerald-500/10 px-4 py-4 text-left transition hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <p className="text-[15px] font-semibold text-white">Toda la UTE</p>
            <p className="mt-1 text-[12px] text-slate-300">
              Usar la flota de tu empresa y tambien la de los socios.
            </p>
            <p className="mt-2 text-[11px] text-slate-400">
              {firstUte
                ? `UTE disponible: ${firstUte.name}`
                : (canInferUte
                  ? 'No existe aun, pero se creara automaticamente con las empresas cargadas'
                  : 'No hay ninguna UTE disponible todavia')}
            </p>
          </button>
        </div>
        {!firstUte && canInferUte && (
          <div className="mt-4 rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3">
            <p className="text-[12px] text-amber-100">
              Ya tienes varias empresas cargadas. Si eliges "Toda la UTE", el sistema tomara tu empresa actual como principal y creara la UTE automaticamente con el resto como socios.
            </p>
          </div>
        )}
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={applying}
            className="rounded-md border border-[#2a4057] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9eb2c8] transition hover:bg-white/5 disabled:opacity-60"
          >
            Cerrar
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
  const [fleetReconciliationModal, setFleetReconciliationModal] = useState({
    open: false,
    items: [],
    companyMix: null,
    requiredBusCount: 0,
    realBoundCount: 0,
    pendingRealReconciliationCount: 0,
    availableRealVehicleCount: 0,
    companiesAvailable: 0,
    estimatedVirtualRemaining: 0,
    reconciliationSnapshot: null,
    dayLabel: '',
    scopeLabel: '',
    scopeVehicleCount: 0,
    scopeMode: 'company',
    busId: null,
    applying: false,
  });
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
      'Pulsa "Generar planificacion". Antes te preguntaremos si quieres revisar las reglas.'
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
      setActiveWorkspaceDetail(null);
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
          const fleetPreview = await getWorkspaceFleetPreview(activeWorkspaceId, payload.day).catch(() => null);
          if (fleetPreview?.blocked && Array.isArray(fleetPreview?.conflicts) && fleetPreview.conflicts.length > 0) {
            setFleetConflictModal({
              open: true,
              conflicts: fleetPreview.conflicts,
            });
            throw new Error('Publicacion bloqueada por conflictos de flota');
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
            setFleetReconciliationModal({
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
              dayLabel: DAY_LABELS[payload.day || activeDay] || payload.day || activeDay,
              scopeLabel: fleetPreview?.scope_label || '',
              scopeVehicleCount: Number(fleetPreview?.scope_vehicle_count || 0),
              scopeMode: String(fleetPreview?.scope_mode || 'company'),
              busId: null,
              applying: false,
            });
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
                dayLabel: DAY_LABELS[payload.day || activeDay] || payload.day || activeDay,
                scopeLabel: publication?.scope_label || '',
                scopeVehicleCount: Number(publication?.scope_vehicle_count || 0),
                scopeMode: String(publication?.scope_mode || 'company'),
                busId: null,
                applying: false,
              });
            } else if (publication?.blocked) {
              setFleetConflictModal({
                open: true,
                conflicts: Array.isArray(publication?.conflicts) ? publication.conflicts : [],
              });
            }
            throw error;
          }
          notifications.success('Version publicada', 'La planificacion ya esta activa en Panel');
        } else {
          await saveWorkspaceVersion(activeWorkspaceId, snapshotPayload);
          notifications.success('Version guardada', 'Checkpoint guardado');
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
      const dayItems = Array.isArray(data?.reconciliation_day?.items)
        ? data.reconciliation_day.items
        : (Array.isArray(data?.pending_assignments) ? data.pending_assignments : []);
      const filteredItems = busId
        ? dayItems.filter((item) => String(item?.bus_id || '') === String(busId))
        : dayItems;
      const sourceCompanyMix = data?.reconciliation_day?.company_mix || data?.reconciliation?.company_mix || null;
      const modalCompanyMix = busId ? buildCompanyMixFallback(filteredItems) : sourceCompanyMix;
      const daySummary = data?.reconciliation_day || {};
      setFleetReconciliationModal({
        open: true,
        items: filteredItems,
        companyMix: modalCompanyMix,
        requiredBusCount: Number(daySummary?.required_bus_count || data?.required_bus_count || 0),
        realBoundCount: Number(daySummary?.real_bound_count || data?.real_bound_count || 0),
        pendingRealReconciliationCount: Number(daySummary?.pending_real_reconciliation_count || data?.pending_real_reconciliation_count || filteredItems.length || 0),
        availableRealVehicleCount: Number(daySummary?.available_real_vehicle_count || data?.available_real_vehicle_count || data?.scope_vehicle_count || 0),
        companiesAvailable: Number(daySummary?.companies_available || sourceCompanyMix?.companies_with_options || 0),
        estimatedVirtualRemaining: Number(daySummary?.estimated_virtual_remaining || sourceCompanyMix?.uncovered_buses || 0),
        reconciliationSnapshot: data?.reconciliation_snapshot?.days?.[activeDay] || null,
        dayLabel: DAY_LABELS[activeDay] || activeDay,
        scopeLabel: data?.scope_label || '',
        scopeVehicleCount: Number(data?.scope_vehicle_count || 0),
        scopeMode: String(data?.scope_mode || 'company'),
        busId: busId || null,
        applying: false,
      });
    } catch (error) {
      notifications.error('No se pudo abrir la reconciliacion', error?.message || 'Error cargando sugerencias');
    } finally {
      notifications.dismiss(loadingToast);
    }
  }, [activeDay, activeOptimizationOptions, activeWorkspaceId, createWorkspaceFleetUte, uteOptions]);

  const applyFleetReconciliationProposal = useCallback(async (companyAllocations = [], busSelections = []) => {
    if (!activeWorkspaceId) return;
    try {
      setFleetReconciliationModal((prev) => ({ ...prev, applying: true }));
      const result = await applyWorkspaceFleetReconciliation(activeWorkspaceId, {
        day: activeDay,
        allocation_mode: 'pending_only',
        autofill_remaining: true,
        bus_ids: fleetReconciliationModal.busId ? [fleetReconciliationModal.busId] : [],
        company_allocations: Array.isArray(companyAllocations) ? companyAllocations : [],
        bus_selections: Array.isArray(busSelections) ? busSelections : [],
      });

      if (result?.schedule_by_day && typeof result.schedule_by_day === 'object') {
        setScheduleByDay(normalizeWorkspaceScheduleByDay(result.schedule_by_day));
      }
      await refreshWorkspaces();
      const freshDetail = await getWorkspace(activeWorkspaceId).catch(() => null);
      if (freshDetail) {
        setActiveWorkspaceDetail(freshDetail);
      }
      setFleetReconciliationModal({
        open: false,
        items: [],
        companyMix: null,
        requiredBusCount: 0,
        realBoundCount: 0,
        pendingRealReconciliationCount: 0,
        availableRealVehicleCount: 0,
        companiesAvailable: 0,
        estimatedVirtualRemaining: 0,
        reconciliationSnapshot: null,
        dayLabel: '',
        scopeLabel: '',
        scopeVehicleCount: 0,
        scopeMode: 'company',
        busId: null,
        applying: false,
      });

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
  }, [activeDay, activeWorkspaceId, fleetReconciliationModal.busId, refreshWorkspaces]);

  return (
    <Layout
      stats={calculateStats()}
      scheduleByDay={scheduleByDay}
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
                <PlanningOverviewBar
                  workspace={activeWorkspaceSummary}
                  activeDay={activeDay}
                  stats={calculateStats()}
                  scheduleByDay={scheduleByDay}
                  onOpenReconciliation={() => openFleetReconciliationCenter()}
                  onOpenRules={() => openLoadOptionsModal({
                    workspaceId: activeWorkspaceId,
                    workspaceName: activeWorkspaceSummary?.name || '',
                  })}
                  optimizationOptions={activeOptimizationOptions}
                  workspaceCompanies={fleetCompanies}
                />
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
                      onOpenReconciliation={openFleetReconciliationCenter}
                    />
                  </StudioErrorBoundary>
                </div>
              </div>
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
        applying={fleetReconciliationModal.applying}
        onApply={applyFleetReconciliationProposal}
        onClose={() => setFleetReconciliationModal({ open: false, items: [], companyMix: null, requiredBusCount: 0, realBoundCount: 0, pendingRealReconciliationCount: 0, availableRealVehicleCount: 0, companiesAvailable: 0, estimatedVirtualRemaining: 0, reconciliationSnapshot: null, dayLabel: '', scopeLabel: '', scopeVehicleCount: 0, scopeMode: 'company', busId: null, applying: false })}
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




