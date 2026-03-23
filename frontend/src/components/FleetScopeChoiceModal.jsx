import React from 'react';

export default function FleetScopeChoiceModal({
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
