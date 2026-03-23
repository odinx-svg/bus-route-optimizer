import React, { useEffect, useState } from 'react';

import {
  createEmptyRouteLoadConstraint,
  DEFAULT_OPTIMIZATION_OPTIONS,
  normalizeOptimizationOptions,
} from '../utils/optimizationOptions';
import {
  getObjectiveDisplayLabel,
  getPreferredSolverHint,
  getSolverDisplayLabel,
} from '../utils/optimizerDiagnostics';

export default function LoadOptionsModal({
  open = false,
  title = 'Reglas de optimizacion',
  initialValue = DEFAULT_OPTIMIZATION_OPTIONS,
  uteOptions = [],
  workspaceCompanies = [],
  workspaceCompanyId = null,
  workspaceCompanyChanging = false,
  onWorkspaceCompanyChange = null,
  routeCount = null,
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
  }, [initialValue, open]);

  const updateConstraint = (index, patch) => {
    setValue((prev) => {
      const next = normalizeOptimizationOptions(prev);
      const constraints = [...next.route_load_constraints];
      constraints[index] = { ...constraints[index], ...patch };
      return { ...next, route_load_constraints: constraints };
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

  const applyWindowTemplate = (templateId) => {
    const templates = {
      school_peaks: [
        { start_time: '07:30', end_time: '09:30', max_routes: 3, enabled: true, label: 'Entrada manana' },
        { start_time: '14:00', end_time: '16:10', max_routes: 3, enabled: true, label: 'Salida mediodia' },
        { start_time: '16:20', end_time: '18:40', max_routes: 2, enabled: true, label: 'Tarde' },
      ],
      morning_focus: [
        { start_time: '07:30', end_time: '09:30', max_routes: 3, enabled: true, label: 'Pico manana' },
      ],
      afternoon_focus: [
        { start_time: '14:00', end_time: '16:10', max_routes: 3, enabled: true, label: 'Pico mediodia' },
        { start_time: '16:20', end_time: '18:40', max_routes: 2, enabled: true, label: 'Pico tarde' },
      ],
    };
    const selected = templates[templateId] || [];
    setValue((prev) => normalizeOptimizationOptions({
      ...prev,
      route_load_constraints: selected,
    }));
  };

  const applyPreset = (presetId) => {
    if (presetId === 'balanced') {
      setValue((prev) => normalizeOptimizationOptions({
        ...prev,
        objective: 'min_buses_viability',
        preferred_solver: 'auto',
        balance_load: true,
        load_balance_hard_spread_limit: 2,
        load_balance_target_band: 1,
      }));
      return;
    }
    if (presetId === 'conservative') {
      setValue((prev) => normalizeOptimizationOptions({
        ...prev,
        objective: 'publishable',
        preferred_solver: 'auto',
        balance_load: true,
        load_balance_hard_spread_limit: 1,
        load_balance_target_band: 0,
        virtual_bus_publish_policy: 'block',
      }));
      return;
    }
    setValue((prev) => normalizeOptimizationOptions({
      ...prev,
      objective: 'min_deadhead',
      preferred_solver: 'cp_sat',
      balance_load: false,
      load_balance_hard_spread_limit: 4,
      load_balance_target_band: 2,
    }));
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[1200] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/85 backdrop-blur-[2px]" onClick={onCancel} />
      <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-[#2a4057] bg-[#0b141f] shadow-2xl">
        <div className="border-b border-[#203247] px-4 py-4">
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
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
              Prioridad de optimizacion
              <select
                value={value.objective || 'min_buses_viability'}
                onChange={(event) => setValue((prev) => ({
                  ...normalizeOptimizationOptions(prev),
                  objective: event.target.value || 'min_buses_viability',
                }))}
                className="mt-1 w-full rounded border border-[#35506a] bg-[#09101d] px-2 py-1 text-[12px] text-white"
              >
                <option value="min_buses_viability">Minimo numero de buses</option>
                <option value="min_km">Minimo kilometraje</option>
                <option value="min_deadhead">Minimo posicionamiento</option>
                <option value="operational_balance">Equilibrio operativo</option>
                <option value="publishable">Mas publicable</option>
              </select>
              <p className="mt-1 text-[10px] text-slate-400">
                Define que intenta optimizar primero el motor.
              </p>
            </label>
            <label className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
              Motor del solver
              <select
                value={value.preferred_solver || 'auto'}
                onChange={(event) => setValue((prev) => ({
                  ...normalizeOptimizationOptions(prev),
                  preferred_solver: ['auto', 'cp_sat', 'pulp_v6'].includes(event.target.value) ? event.target.value : 'auto',
                }))}
                className="mt-1 w-full rounded border border-[#35506a] bg-[#09101d] px-2 py-1 text-[12px] text-white"
              >
                <option value="auto">Auto inteligente</option>
                <option value="pulp_v6">PuLP V6 estable</option>
                <option value="cp_sat">CP-SAT experimental</option>
              </select>
              <p className="mt-1 text-[10px] text-slate-400">
                `PuLP V6` es la base estable. `CP-SAT` ya esta disponible para comparar y acelerar casos concretos.
              </p>
            </label>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="flex items-center gap-2 rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
              <input
                type="checkbox"
                checked={value.enable_greedy_warm_start !== false}
                onChange={(event) => setValue((prev) => ({
                  ...normalizeOptimizationOptions(prev),
                  enable_greedy_warm_start: event.target.checked,
                }))}
              />
              Arrancar con seed greedy
            </label>
            <label className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
              Limite de tiempo del solver (seg)
              <input
                type="number"
                min={1}
                max={600}
                value={value.time_limit_seconds ?? ''}
                onChange={(event) => setValue((prev) => ({
                  ...normalizeOptimizationOptions(prev),
                  time_limit_seconds: event.target.value === '' ? null : Number.parseInt(event.target.value || '30', 10),
                }))}
                className="mt-1 w-full rounded border border-[#35506a] bg-[#09101d] px-2 py-1 text-[12px] text-white"
                placeholder="Auto"
              />
              <p className="mt-1 text-[10px] text-slate-400">
                Dejalo vacio para usar el default del motor. Sube el limite solo en semanas complejas.
              </p>
            </label>
          </div>

          <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-3 py-3 text-[12px] text-cyan-50">
            <p className="text-[10px] uppercase tracking-[0.1em] text-cyan-200">Lectura del motor</p>
            <p className="mt-2">
              Objetivo activo: <span className="font-semibold">{getObjectiveDisplayLabel(value.objective)}</span>
              {' '}| Solver pedido: <span className="font-semibold">{getSolverDisplayLabel(value.preferred_solver)}</span>
              {typeof routeCount === 'number' && routeCount > 0 ? (
                <>
                  {' '}| Rutas cargadas: <span className="font-semibold">{routeCount}</span>
                </>
              ) : null}
            </p>
            <p className="mt-1 text-[11px] text-cyan-100/90">
              {getPreferredSolverHint(value, routeCount)}
            </p>
          </div>

          <div className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-3">
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

          <div className="rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-3">
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
                <p className="mt-1 text-[12px] text-slate-300">Usar solo los buses de mi empresa principal.</p>
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
                <p className="mt-1 text-[12px] text-slate-300">Usar AAV y tambien las empresas socias de la UTE.</p>
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

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className="flex items-center gap-2 rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[12px] text-slate-200">
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

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
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
              <p className="mt-1 text-[10px] text-slate-400">Solo hace falta cuando eliges "Toda la UTE".</p>
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

          <div className="rounded-lg border border-[#2a4057] bg-[#0a1324] p-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] uppercase tracking-[0.1em] text-cyan-300">Limites horarios</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={addConstraint}
                  className="rounded border border-cyan-500/40 px-2 py-1 text-[10px] uppercase tracking-[0.08em] text-cyan-200 hover:bg-cyan-500/10"
                >
                  + Anadir
                </button>
              </div>
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              Limita cuantas rutas puede acumular un mismo bus dentro de las franjas de mayor presion.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={() => applyWindowTemplate('school_peaks')} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] uppercase tracking-[0.08em] text-slate-200 hover:bg-white/[0.06]">
                Picos escolares
              </button>
              <button type="button" onClick={() => applyWindowTemplate('morning_focus')} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] uppercase tracking-[0.08em] text-slate-200 hover:bg-white/[0.06]">
                Solo manana
              </button>
              <button type="button" onClick={() => applyWindowTemplate('afternoon_focus')} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] uppercase tracking-[0.08em] text-slate-200 hover:bg-white/[0.06]">
                Solo tarde
              </button>
            </div>
            <div className="mt-2 max-h-[240px] space-y-2 overflow-auto">
              {value.route_load_constraints.length === 0 && (
                <p className="text-[12px] text-slate-400">
                  Sin limites horarios extra. Puedes usar por ejemplo 07:30-09:30 max 3 rutas.
                </p>
              )}
              {value.route_load_constraints.map((rule, index) => (
                <div key={`${rule.start_time}-${rule.end_time}-${index}`} className="grid grid-cols-12 items-center gap-2 rounded border border-[#35506a] bg-[#09101d] px-2 py-2">
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
        </div>

        <div className="border-t border-[#203247] px-4 py-3">
          <div className="hidden rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[11px] text-slate-300">
            Resumen: reparto {value.balance_load ? 'balanceado' : 'flexible'} · diferencia maxima {value.load_balance_hard_spread_limit} · margen objetivo ±{value.load_balance_target_band} · ventanas activas {value.route_load_constraints.length}
          </div>
          <div className="mb-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[11px] text-slate-300">
            Resumen: objetivo {getObjectiveDisplayLabel(value.objective)} | solver {getSolverDisplayLabel(value.preferred_solver)} | reparto {value.balance_load ? 'balanceado' : 'flexible'} | diferencia maxima {value.load_balance_hard_spread_limit} | margen objetivo +/-{value.load_balance_target_band} | ventanas activas {value.route_load_constraints.length}
          </div>
          <div className="flex justify-end gap-2">
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
    </div>
  );
}
