import React from 'react';

export default function FleetConflictModal({
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
