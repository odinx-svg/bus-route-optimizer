import React from 'react';

export default function PreOptimizeRestrictionsModal({
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
          Quieres revisar las reglas de optimizacion para <span className="font-semibold text-white">{label}</span> antes de generar la planificacion?
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
